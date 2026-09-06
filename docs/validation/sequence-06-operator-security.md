# Sequence 6 operator access and deployment boundaries

This checkpoint protects API writes. It does not establish a Sequence 6 engineering freeze.

## Local setup after updating

Use the declared Python 3.12 environment and install `requirements.lock` (which now includes
Shapely 2.1.2 for explicit geometry topology validation). Then run:

```text
python scripts/setup_operator.py
docker compose up -d --build
python scripts/verify.py --services
```

The setup helper preserves other `.env` settings and other operator accounts. It creates
`local-operator` with `reviewer` and `operator` roles. It prints a random bearer token once and
stores only its SHA-256 digest. Keep the token private; do not include its terminal output in
shared validation logs. Existing accounts are not silently rotated. Explicit rotation uses
`python scripts/setup_operator.py --rotate` and invalidates that subject's previous token.

Open the operator-credentials section on `/reconstruction/qa` or `/terrain/qa`. Enter the subject
and token. They remain in page memory only, are sent only with same-origin writes, and are not
saved to browser storage. Read-only QA remains available without credentials.

## Authorization contract

`FLOODGUARD_OPERATORS_JSON` is a subject-keyed JSON object. Each record has `token_sha256` and
`roles`, selected from `reviewer` and `operator`. Duplicate subjects/tokens, unexpected fields,
invalid digests and unknown roles disable writes. Both environment and `.env` configuration
are supported. Missing configuration returns HTTP 503 for mutations; missing/incorrect bearer
credentials return 401; insufficient roles or a mismatched review subject return 403.

The API's global dependency protects non-GET/HEAD/OPTIONS routes. Review requests require the
reviewer role and a reviewer field matching the authenticated subject. Existing human-vs-automated
and engineering checklist rules remain intact. A credential is authorization, not proof that
someone inspected a map or that survey evidence is authentic. Old approval records are not
retroactively authenticated by this change; a freeze review must inspect their provenance.

## Readiness and network scope

`/health` stays a process liveness check. `/ready` checks database connectivity, installed Alembic
heads, and authenticated object-store requests. It returns 503 if any probe fails. Missing buckets
before bootstrap do not certify data readiness; that belongs to the domain readiness endpoints.
Probe errors never return credentials or signed URLs.

Compose now binds published ports to `127.0.0.1` and disables Traefik's insecure dashboard.
This is a local-development profile, not a production security certification. Shared deployment
still requires non-default credentials, scoped storage/database accounts, TLS and an appropriate
network policy. Acquisition jobs remain explicitly single-process and ephemeral.

## Verification scope

The isolated sandbox ran 13 operator-authorization/QA tests, two dependency-probe tests and two
operator-setup tests. Tests for the actual application's global guard and readiness wiring were
added for the full pinned-runtime suite. Existing domain integration fixtures explicitly override
only the authorization dependency; their worker and human-review assertions are retained.

The sandbox could not install Python 3.12/MinIO/Ruff/mypy or run Docker. Therefore no full
application, pinned-runtime, migration, storage or browser acceptance pass is claimed here.
