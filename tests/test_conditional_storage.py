"""S3 transport-contract tests; not a substitute for deployed MinIO acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Lock
from typing import ClassVar

import pytest
from urllib3.exceptions import HTTPError

from floodguard.common import conditional_storage as storage


class Signer:
    def presigned_put_object(self, bucket_name, object_name, expires):
        assert expires == timedelta(minutes=10)
        return f"https://storage.invalid/{bucket_name}/{object_name}?signature=PRIVATE"


class Response:
    def __init__(self, status):
        self.status = status
        self.closed = False
        self.released = False

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


@pytest.fixture
def transport(monkeypatch):
    class Pool:
        objects: ClassVar[dict[str, bytes]] = {}
        requests: ClassVar[list[tuple[str, dict[str, object]]]] = []
        responses: ClassVar[list[Response]] = []
        lock = Lock()
        forced_status = None
        ignore_condition = False
        failure = False
        cleared = 0

        def __init__(self, **kwargs):
            assert kwargs["retries"] is False

        def request(self, method, url, **kwargs):
            assert method == "PUT"
            assert kwargs["headers"]["If-None-Match"] == "*"
            assert kwargs["retries"] is False and kwargs["redirect"] is False
            assert kwargs["chunked"] is False and kwargs["preload_content"] is False
            if self.failure:
                raise HTTPError("signed URL signature=PRIVATE")
            body = kwargs["body"]
            payload = body if isinstance(body, bytes) else body.read()
            assert len(payload) == int(kwargs["headers"]["Content-Length"])
            with self.lock:
                self.requests.append((url, kwargs))
                if self.forced_status is not None:
                    status = self.forced_status
                elif url in self.objects and not self.ignore_condition:
                    status = 412
                else:
                    self.objects[url] = payload
                    status = 200
                response = Response(status)
                self.responses.append(response)
                return response

        def clear(self):
            type(self).cleared += 1

    monkeypatch.setattr(storage, "PoolManager", Pool)
    return Pool


def test_concurrent_writers_create_once_and_do_not_overwrite(transport):
    writer = storage.ConditionalObjectWriter(Signer(), "test-bucket")

    def write(index):
        try:
            writer.put("scientific-key", str(index).encode(), length=1, content_type="text/plain")
        except storage.ConditionalObjectExistsError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))
    assert sum(results) == 1
    assert len(transport.objects) == 2  # One unique capability probe plus one data object.
    assert len(transport.requests) == 10  # Probe creation/rejection plus eight writes.
    assert all(response.closed and response.released for response in transport.responses)
    assert transport.cleared == 10


def test_ignoring_backend_is_refused_before_scientific_write(transport):
    transport.ignore_condition = True
    writer = storage.ConditionalObjectWriter(Signer(), "test-bucket")
    with pytest.raises(storage.ConditionalWriteError, match="ignores"):
        writer.put("scientific-key", b"a", length=1, content_type="text/plain")
    assert all(".floodguard-capability/" in key for key in transport.objects)
    assert not writer._verified


@pytest.mark.parametrize("status", [301, 307, 403, 409, 500, 501])
def test_failures_never_retry_or_fall_back_to_unconditional_write(transport, status):
    transport.forced_status = status
    with pytest.raises(storage.ConditionalWriteError, match=str(status)):
        storage.conditional_put(Signer(), "test-bucket", "key", b"a", length=1,
                                content_type="text/plain")
    assert len(transport.requests) == 1


def test_signed_urls_are_not_exposed_by_transport_errors(transport):
    transport.failure = True
    with pytest.raises(storage.ConditionalWriteError) as failure:
        storage.conditional_put(Signer(), "bucket", "key", b"a", length=1,
                                content_type="text/plain")
    assert "PRIVATE" not in str(failure.value)
    assert failure.value.__suppress_context__ is True
    assert transport.cleared == 1


def test_stream_payloads_preserve_length_and_content(transport):
    writer = storage.ConditionalObjectWriter(Signer(), "test-bucket")
    writer.put("stream", BytesIO(b"payload"), length=7, content_type="application/octet-stream")
    key = "https://storage.invalid/test-bucket/stream?signature=PRIVATE"
    assert transport.objects[key] == b"payload"


def test_invalid_lengths_fail_before_signing_or_transmitting(transport):
    with pytest.raises(storage.ConditionalWriteError, match="length"):
        storage.conditional_put(Signer(), "bucket", "key", b"a", length=2,
                                content_type="text/plain")
    with pytest.raises(storage.ConditionalWriteError, match="limited"):
        storage.conditional_put(Signer(), "bucket", "key", b"a", length=513 * 1024 * 1024,
                                content_type="text/plain")
    assert not transport.requests
