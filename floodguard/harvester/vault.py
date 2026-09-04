"""Write-once raw object vault backed by MinIO/S3-compatible storage."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Protocol

from minio import Minio
from minio.error import S3Error
from minio.versioningconfig import VersioningConfig


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
    """Application-enforced immutable object writer.

    Each dataset version receives a unique prefix. Existing keys are never overwritten.
    Bucket versioning is enabled as an additional development safeguard.
    """

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

    def ensure_ready(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        self.client.set_bucket_versioning(self.bucket, VersioningConfig("Enabled"))

    def _assert_absent(self, object_key: str) -> None:
        try:
            self.client.stat_object(self.bucket, object_key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return
            raise
        raise ImmutableObjectExistsError(
            f"immutable raw object already exists: {self.bucket}/{object_key}"
        )

    def put_file_once(
        self, object_key: str, path: Path, *, content_type: str | None = None
    ) -> None:
        self._assert_absent(object_key)
        self.client.fput_object(
            self.bucket,
            object_key,
            str(path),
            content_type=content_type or "application/octet-stream",
        )

    def put_bytes_once(
        self, object_key: str, payload: bytes, *, content_type: str
    ) -> None:
        self._assert_absent(object_key)
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(payload),
            length=len(payload),
            content_type=content_type,
        )


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
