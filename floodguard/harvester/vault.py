"""Write-once raw object vault backed by MinIO/S3-compatible storage."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.versioningconfig import VersioningConfig

from floodguard.common.conditional_storage import (
    ConditionalObjectExistsError,
    ConditionalObjectWriter,
)


class ImmutableObjectExistsError(RuntimeError):
    pass


class RawVault(Protocol):
    bucket: str

    def ensure_ready(self) -> None: ...

    def put_file_once(
        self, object_key: str, path: Path, *, content_type: str | None = None
    ) -> None: ...

    def put_bytes_once(
        self, object_key: str, payload: bytes, *, content_type: str
    ) -> None: ...


class MinioRawVault:
    """Atomic create-only writer; bucket versioning remains an extra safeguard."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        self.bucket = bucket
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._writer = ConditionalObjectWriter(self.client, self.bucket)

    def ensure_ready(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self.client.set_bucket_versioning(self.bucket, VersioningConfig("Enabled"))

    def put_file_once(
        self, object_key: str, path: Path, *, content_type: str | None = None
    ) -> None:
        try:
            with path.open("rb") as stream:
                self._writer.put(object_key, stream, length=path.stat().st_size,
                                 content_type=content_type or "application/octet-stream")
        except ConditionalObjectExistsError as exc:
            raise ImmutableObjectExistsError(object_key) from exc

    def put_bytes_once(
        self, object_key: str, payload: bytes, *, content_type: str
    ) -> None:
        try:
            self._writer.put(object_key, payload, length=len(payload), content_type=content_type)
        except ConditionalObjectExistsError as exc:
            raise ImmutableObjectExistsError(object_key) from exc


class MemoryRawVault:
    """Deterministic write-once vault used by unit tests."""

    def __init__(self, bucket: str = "test-raw") -> None:
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}

    def ensure_ready(self) -> None:
        return

    def _store(self, object_key: str, payload: bytes) -> None:
        if object_key in self.objects:
            raise ImmutableObjectExistsError(object_key)
        self.objects[object_key] = payload

    def put_file_once(
        self, object_key: str, path: Path, *, content_type: str | None = None
    ) -> None:
        del content_type
        self._store(object_key, path.read_bytes())

    def put_bytes_once(
        self, object_key: str, payload: bytes, *, content_type: str
    ) -> None:
        del content_type
        self._store(object_key, payload)
