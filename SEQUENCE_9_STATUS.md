# Sequence 9 - IMPLEMENTED; FINAL DEPLOYED GATE PENDING

Date: 6 September 2026
Branch: `sequence-9-twin-builder`
Release: `0.9.0`
Predecessor: Sequence 8 technical freeze `8412eb7`, validated source `de6cce9`.

The versioned twin builder, immutable manifest/component snapshots, exact-source adapters,
conservative readiness, independent manifest recreation, additive migration, read-only API/QA,
operator CLI, examples and full gate are implemented.

Local full verification passed on Python 3.12.10: Ruff clean, strict mypy 136 source files,
671 tests passed and one Windows symlink-permission skip. The deployed development bootstrap
created reference and provisional real twins and recreated each in an empty metadata database.
The final clean-commit deployed gate and exact source/component evidence remain to be recorded.

**Sequence 9 is NOT FROZEN.** The inherited DATA-08-01 requirement remains open: no real source-bound
adjacent-ward drainage path to a defensible downstream destination exists among the available
products. Human-only deferral to Sequence 20 does not waive this requirement. The gate separates
successful assembly validation from sequence freeze, and it fails freeze explicitly when real
cross-ward evidence is absent. No Sequence 10 work or HYDRAULIC_VALIDATED claim is authorized by
successful reference assembly.

See `docs/architecture/sequence-09-twin-builder.md` for the interface, checks and commands;
`docs/examples/sequence-09-pilot-selection.json` for exact live pilot component selections;
and `docs/validation/final-human-review-register.md` for human/data requirements.

Next: commit the implementation, rebuild the exact local API and run the complete gate. Retain the
report even if its sole blocker remains DATA-08-01. Close the source-bound real drainage requirement
before marking this sequence technically frozen.
