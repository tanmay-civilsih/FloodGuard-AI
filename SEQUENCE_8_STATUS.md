# Sequence 8 - Implementation complete; deployed gate pending

Date: 6 September 2026
Branch: `sequence-8-drain-model`
Release: `0.8.0`
Predecessor technical freeze: `11ed8fc`; Sequence 7 validated source `318ec92`.

The full Sequence 8 implementation is ready for its clean-commit deployed development gate.
It is not yet technically frozen at this checkpoint.

Implemented: typed graph/direction/parameter/exchange contracts; exact stored-source import and
explicit geometry bindings; polygon-based cross-ward checks; pump/storage/outfall definitions;
conservative readiness; immutable product/audit storage; additive migration; operator CLI and
reference bootstrap; read-only API and QA viewer; full development gate with HTTP hash readback.
See `docs/architecture/sequence-08-drain-model.md` for the interface and scientific limitations.

Initial full software verification: Python 3.12.10, Ruff passed, strict mypy 122 source files,
563 passed and one Windows symlink-permission skip. Additional gate tests will be included in the
final pinned run. The local API runs Sequence 8 / v0.8.0 with the additive migration applied.
The existing-source bootstrap passed and repeated products reused their exact immutable identity.

| Product | ID | State |
|---|---|---|
| Real Ward 7 import | 30c05f00-2ab5-5aea-a640-5275711ce127 | VISUAL_ONLY; 104 drains, 84 structure candidates, 98 labels |
| Controlled directed reference | 898df152-6437-55ba-9ff4-bcdb430a4a00 | HYDRAULIC_SCENARIO_READY; 6 nodes, 5 edges, 2 exchanges |

Reference readiness is never counted as real hydraulic validation. Real source features intersect
wards 7, 8, 10 and 12; three intersect no source ward. No nominal real connectivity/direction or
engineering values are inferred from those intersections. There is no source-bound real directed
graph and no verified real cross-ward path yet. Genuine adjacent-ward continuation to a defensible
destination is mandatory before Sequence 9 closes. Final engineering/human acceptance remains
pending Sequence 20 under the existing policy. No Sequence 9 implementation has begun.

Next: run the full clean-commit gate, retain its exact source/product evidence, then record the
technical freeze. No remote publication or merge-to-main is implied by this local checkpoint.
