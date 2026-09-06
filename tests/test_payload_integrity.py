"""Checksums are verified against actual bytes, not merely copied into lineage."""

import hashlib
import json

import pytest

from floodguard.common.integrity import (
    PayloadIntegrityError,
    verified_payload,
    verified_spatial_pair,
)


def test_correct_manifest_bytes_pass_unchanged() -> None:
    payload = b"scientific source"
    assert verified_payload(
        payload, expected_sha256=hashlib.sha256(payload).hexdigest(),
        expected_size=len(payload), max_bytes=100,
    ) is payload


@pytest.mark.parametrize("size, digest, limit", [
    (10, "a" * 64, 100), (9, hashlib.sha256(b"0123456789").hexdigest(), 100),
    (10, hashlib.sha256(b"0123456789").hexdigest(), 9),
    (10, "invalid", 100), (10, "a" * 64, 0),
])
def test_bad_manifest_or_limit_is_rejected(size: int, digest: str, limit: int) -> None:
    with pytest.raises(PayloadIntegrityError):
        verified_payload(b"0123456789", expected_sha256=digest,
                         expected_size=size, max_bytes=limit)


def make_pair() -> tuple[bytes, bytes, str]:
    qa = b'{"type":"FeatureCollection","features":[]}'
    working = json.dumps({"floodguard_integrity": {
        "pipeline_version": "sequence-4-v2", "qa_sha256": hashlib.sha256(qa).hexdigest(),
        "qa_byte_size": len(qa),
    }}).encode()
    return working, qa, hashlib.sha256(working).hexdigest()


def test_working_hash_anchors_qa_hash() -> None:
    working, qa, digest = make_pair()
    assert verified_spatial_pair(working, qa, working_sha256=digest,
                                 pipeline_version="sequence-4-v2", max_bytes=1024)


@pytest.mark.parametrize("corrupt", ["working", "qa", "policy"])
def test_pair_tampering_or_historical_policy_is_rejected(corrupt: str) -> None:
    working, qa, digest = make_pair()
    if corrupt == "working":
        working += b" "
    if corrupt == "qa":
        qa = qa.replace(b"features", b"modified")
    with pytest.raises(PayloadIntegrityError):
        verified_spatial_pair(working, qa, working_sha256=digest,
                             pipeline_version="old" if corrupt == "policy" else "sequence-4-v2",
                             max_bytes=1024)


def test_historical_missing_integrity_metadata_is_not_silently_trusted() -> None:
    working = b'{"type":"FeatureCollection"}'
    with pytest.raises(PayloadIntegrityError, match="historical"):
        verified_spatial_pair(working, b"{}", working_sha256=hashlib.sha256(working).hexdigest(),
                             pipeline_version="sequence-4-v2", max_bytes=1024)
