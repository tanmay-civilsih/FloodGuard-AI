"""Canonical JSON and bounded, unambiguous input decoding."""

import hashlib
import json
from typing import Any


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_object(payload: bytes, max_bytes: int) -> dict[str, Any]:
    if not payload or len(payload) > max_bytes:
        raise ValueError("JSON input is empty or exceeds the configured size limit")

    def reject_constant(value: str) -> object:
        raise ValueError(f"non-finite JSON constant: {value}")

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("duplicate JSON object key")
            output[key] = value
        return output

    result: Any = json.loads(
        payload, parse_constant=reject_constant, object_pairs_hook=unique_pairs
    )
    if not isinstance(result, dict):
        raise ValueError("JSON input must be an object")
    return result
