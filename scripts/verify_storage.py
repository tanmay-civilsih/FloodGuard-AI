"""Verify create-only semantics on the deployed store using fresh, isolated probe keys."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

# Support the documented `python scripts/verify_storage.py` invocation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from minio import Minio

    from floodguard.common.conditional_storage import (
        ConditionalObjectExistsError,
        ConditionalObjectWriter,
    )
    from floodguard.common.config import get_settings

    settings = get_settings()
    client = Minio(settings.object_store_endpoint,
                   access_key=settings.object_store_access_key,
                   secret_key=settings.object_store_secret_key,
                   secure=settings.object_store_secure)
    results = []
    for bucket in (settings.raw_bucket, settings.spatial_bucket):
        if not client.bucket_exists(bucket):
            raise SystemExit("Storage verification needs the bootstrapped raw and spatial buckets")
        writer = ConditionalObjectWriter(client, bucket)
        key = f".floodguard-verification/{uuid4()}.probe"

        def attempt(
            index: int, current_writer: ConditionalObjectWriter = writer, current_key: str = key,
        ) -> bytes | None:
            payload = f"writer-{index}".encode("ascii")
            try:
                current_writer.put(
                    current_key, payload, length=len(payload),
                    content_type="application/octet-stream",
                )
            except ConditionalObjectExistsError:
                return None
            return payload

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, range(8)))
        winners = [payload for payload in outcomes if payload is not None]
        if len(winners) != 1:
            raise SystemExit("Conditional storage gate failed: expected exactly one writer")
        response = cast(Any, client.get_object(bucket, key))
        try:
            stored = bytes(response.read(1024))
        finally:
            response.close()
            response.release_conn()
        if stored != winners[0]:
            raise SystemExit("Conditional storage gate failed: winning bytes were replaced")
        results.append({"bucket": bucket, "key": key, "writers": 8, "created": 1,
                        "rejected": 7, "sha256": hashlib.sha256(stored).hexdigest()})
    print(json.dumps({"status": "PASSED", "conditional_storage": results}, indent=2))


if __name__ == "__main__":
    main()
