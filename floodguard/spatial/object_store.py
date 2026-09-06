"""Immutable object-store access for the Sequence 4 spatial domain."""

from __future__ import annotations

from typing import Any, Protocol, cast

from minio import Minio
from minio.error import S3Error
from minio.versioningconfig import VersioningConfig

from floodguard.common.conditional_storage import (
    ConditionalObjectExistsError,
    ConditionalObjectWriter,
)
from floodguard.common.config import get_settings


class SpatialObjectExistsError(RuntimeError):
    pass


class SpatialObjectStore(Protocol):
    raw_bucket: str
    spatial_bucket: str

    def ensure_ready(self) -> None: ...

    def read_raw(self, object_key: str) -> bytes: ...

    def read_spatial(self, object_key: str) -> bytes: ...

    def put_spatial_once(
        self,
        object_key: str,
        payload: bytes,
        *,
        content_type: str,
    ) -> None: ...


class MinioSpatialObjectStore:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        raw_bucket: str,
        spatial_bucket: str,
        secure: bool,
    ) -> None:
        self.raw_bucket = raw_bucket
        self.spatial_bucket = spatial_bucket
        self.max_read_bytes = get_settings().spatial_max_object_bytes
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._writer = ConditionalObjectWriter(self.client, self.spatial_bucket)

    def ensure_ready(self) -> None:
        if not self.client.bucket_exists(self.raw_bucket):
            raise RuntimeError(f"raw bucket does not exist: {self.raw_bucket}")
        if not self.client.bucket_exists(self.spatial_bucket):
            self.client.make_bucket(self.spatial_bucket)
        self.client.set_bucket_versioning(
            self.spatial_bucket,
            VersioningConfig("Enabled"),
        )

    def _read(self, bucket: str, object_key: str) -> bytes:
        try:
            response = cast(Any, self.client.get_object(bucket, object_key))
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise FileNotFoundError(object_key) from exc
            raise
        try:
            payload = bytes(response.read(self.max_read_bytes + 1))
            if len(payload) > self.max_read_bytes:
                raise RuntimeError("stored object exceeds the configured spatial read limit")
            return payload
        finally:
            response.close()
            response.release_conn()

    def read_raw(self, object_key: str) -> bytes:
        return self._read(self.raw_bucket, object_key)

    def read_spatial(self, object_key: str) -> bytes:
        return self._read(self.spatial_bucket, object_key)

    def put_spatial_once(
        self,
        object_key: str,
        payload: bytes,
        *,
        content_type: str,
    ) -> None:
        try:
            self._writer.put(object_key, payload, length=len(payload), content_type=content_type)
        except ConditionalObjectExistsError as exc:
            raise SpatialObjectExistsError(object_key) from exc


class MemorySpatialObjectStore:
    def __init__(
        self,
        *,
        raw_objects: dict[str, bytes] | None = None,
        raw_bucket: str = "raw",
        spatial_bucket: str = "spatial",
    ) -> None:
        self.raw_bucket = raw_bucket
        self.spatial_bucket = spatial_bucket
        self.raw_objects = dict(raw_objects or {})
        self.spatial_objects: dict[str, bytes] = {}

    def ensure_ready(self) -> None:
        return

    def read_raw(self, object_key: str) -> bytes:
        try:
            return self.raw_objects[object_key]
        except KeyError as exc:
            raise FileNotFoundError(object_key) from exc

    def read_spatial(self, object_key: str) -> bytes:
        try:
            return self.spatial_objects[object_key]
        except KeyError as exc:
            raise FileNotFoundError(object_key) from exc

    def put_spatial_once(
        self,
        object_key: str,
        payload: bytes,
        *,
        content_type: str,
    ) -> None:
        del content_type
        if object_key in self.spatial_objects:
            raise SpatialObjectExistsError(object_key)
        self.spatial_objects[object_key] = payload
