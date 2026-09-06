"""Verify scientific payload bytes against trusted manifest metadata before use."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class PayloadIntegrityError(ValueError):
    pass


def verified_payload(
    payload: bytes, *, expected_sha256: str, max_bytes: int,
    expected_size: int | None = None,
) -> bytes:
    if max_bytes < 1 or len(payload) > max_bytes:
        raise PayloadIntegrityError("payload exceeds the configured size limit")
    if expected_size is not None and (expected_size < 0 or len(payload) != expected_size):
        raise PayloadIntegrityError("payload length differs from its manifest")
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise PayloadIntegrityError("a valid expected SHA-256 is required")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise PayloadIntegrityError("payload SHA-256 differs from its manifest")
    return payload


def verified_spatial_pair(
    working: bytes, qa: bytes, *, working_sha256: str, pipeline_version: str, max_bytes: int,
) -> dict[str, Any]:
    verified_payload(working, expected_sha256=working_sha256, max_bytes=max_bytes)
    try:
        document: Any = json.loads(working)
    except (ValueError, UnicodeError) as exc:
        raise PayloadIntegrityError("working artifact is not valid JSON") from exc
    if not isinstance(document, dict):
        raise PayloadIntegrityError("working artifact must be an object")
    metadata = document.get("floodguard_integrity")
    if not isinstance(metadata, dict) or metadata.get("pipeline_version") != pipeline_version:
        raise PayloadIntegrityError("historical spatial policy: rebuild from the original source")
    digest, size = metadata.get("qa_sha256"), metadata.get("qa_byte_size")
    if not isinstance(digest, str) or not isinstance(size, int) or isinstance(size, bool):
        raise PayloadIntegrityError("working artifact lacks QA integrity metadata")
    verified_payload(qa, expected_sha256=digest, expected_size=size, max_bytes=max_bytes)
    return document
