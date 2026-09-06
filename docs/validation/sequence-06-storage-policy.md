# Create-only storage policy

The raw and spatial MinIO adapters now send `If-None-Match: *` with a single PUT through the
SDK's public presigned-PUT API. This removes the former stat-then-put race. HTTP 412 maps to
the existing immutable-object exception; redirects, conflicts and other failures never trigger
an unconditional retry. Signed URLs are not returned in transport failure messages.

Before scientific writes, each writer tests the backend with a unique one-byte object under
`.floodguard-capability/`. The second conditional write must be rejected. A backend that ignores
the condition is refused before touching a scientific key. These tiny probe objects are retained;
no source data or versions are deleted. The adapter limits single-object uploads to 512 MiB.
Spatial/raw reads through the spatial adapter are bounded by the configured spatial object limit.

This is create-only application behavior, not retention/WORM certification. Administrative
credentials can still delete objects or change bucket policy. Shared deployments need scoped
accounts and appropriate retention policy. Conditional creation checks the current version;
a delete marker is not equivalent to protected historical storage.

## Deployed acceptance

Run after raw and spatial bootstrap, inside the configured API environment:

```text
docker compose exec -T api python scripts/verify_storage.py
```

The command uses fresh `.floodguard-verification/` keys, not user artifacts. In each bucket,
eight concurrent writes must produce one winner and seven rejections, and a read must match the
winning bytes. Probe keys and hashes are printed without secrets. No data is overwritten or
removed. This must pass on the actual deployed MinIO version before release acceptance.

Eleven transport-contract regression tests passed in the isolated sandbox, including simulated
concurrency, an ignoring backend, redirects, conflicts, malformed lengths and error redaction.
The real MinIO gate was not run here because Docker/MinIO and the pinned runtime were unavailable.

## Primary protocol references

- AWS S3 conditional writes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html
- MinIO Python API: https://docs.min.io/aistor/developers/sdk/python/api/
- MinIO conditional header support: https://docs.min.io/aistor/developers/s3-api-compatibility/
