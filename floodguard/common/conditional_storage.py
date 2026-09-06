"""Atomic create-only S3 writes through the public presigned-PUT API.

No unconditional fallback, redirects or automatic retries are permitted. A private,
unique capability probe rejects a backend that ignores If-None-Match before any
scientific object is written. This is not WORM protection against administrators.
"""

from __future__ import annotations

from datetime import timedelta
from threading import Lock
from typing import BinaryIO, Protocol
from uuid import uuid4

from urllib3 import PoolManager, Timeout
from urllib3.exceptions import HTTPError


class PutSigner(Protocol):
    def presigned_put_object(
        self, bucket_name: str, object_name: str, expires: timedelta,
    ) -> str: ...


class ConditionalObjectExistsError(RuntimeError):
    pass


class ConditionalWriteError(RuntimeError):
    pass


def conditional_put(
    client: PutSigner, bucket: str, key: str, payload: bytes | BinaryIO, *,
    length: int, content_type: str,
) -> None:
    if not 0 <= length <= 512 * 1024 * 1024:
        raise ConditionalWriteError("single-object writes are limited to 512 MiB")
    if isinstance(payload, bytes) and length != len(payload):
        raise ConditionalWriteError("payload length does not match declared length")
    pool = PoolManager(timeout=Timeout(connect=5, read=120), retries=False)
    try:
        url = client.presigned_put_object(bucket, key, expires=timedelta(minutes=10))
        response = pool.request(
            "PUT", url, body=payload,
            headers={"If-None-Match": "*", "Content-Length": str(length),
                     "Content-Type": content_type},
            retries=False, redirect=False, preload_content=False, chunked=False,
        )
        try:
            status = response.status
        finally:
            response.close()
            response.release_conn()
    except HTTPError:
        # urllib3 errors can contain the signed URL; do not expose it in job logs.
        raise ConditionalWriteError("conditional upload transport failed") from None
    finally:
        pool.clear()
    if status == 412:
        raise ConditionalObjectExistsError("object already exists")
    if status not in {200, 201}:
        raise ConditionalWriteError(f"conditional upload rejected (HTTP {status})")


class ConditionalObjectWriter:
    def __init__(self, client: PutSigner, bucket: str) -> None:
        self.client = client
        self.bucket = bucket
        self._verified = False
        self._lock = Lock()

    def ensure_supported(self) -> None:
        with self._lock:
            if self._verified:
                return
            key = f".floodguard-capability/{uuid4()}.probe"
            conditional_put(self.client, self.bucket, key, b"0", length=1,
                            content_type="application/octet-stream")
            try:
                conditional_put(self.client, self.bucket, key, b"1", length=1,
                                content_type="application/octet-stream")
            except ConditionalObjectExistsError:
                self._verified = True
                return
            raise ConditionalWriteError(
                "storage ignores conditional creation; scientific writes are disabled"
            )

    def put(self, key: str, payload: bytes | BinaryIO, *, length: int, content_type: str) -> None:
        self.ensure_supported()
        conditional_put(self.client, self.bucket, key, payload,
                        length=length, content_type=content_type)
