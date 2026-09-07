"""R2 independent historical-data gate; inherited hydraulic blockers stay explicit."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import Table, create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from floodguard.common.release_evidence import lock_mismatches, source_fingerprint  # noqa: E402
from floodguard.drainage.serialization import canonical_bytes, sha256  # noqa: E402
from floodguard.forcing.contracts import Manifest  # noqa: E402
from floodguard.forcing.models import ForcingRecord  # noqa: E402
from floodguard.forcing.service import ForcingService  # noqa: E402
from floodguard.history.factory import build_history_service  # noqa: E402
from floodguard.history.models import HistoricalEventRecord  # noqa: E402
from floodguard.history.service import HistoryService  # noqa: E402
from floodguard.registry.database import get_session_factory  # noqa: E402
from scripts.sequence8_development_gate import drain_readiness_blockers  # noqa: E402
from scripts.sequence9_development_gate import (  # noqa: E402
    twin_readiness_blockers,
    validate_base_url,
)
from scripts.sequence10_development_gate import read, readiness_errors  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", required=True, type=UUID)
    parser.add_argument("--base-url", default="http://api:8000")
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--run-checks", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.repository_commit):
        parser.error("--repository-commit must be the checked-out source commit")
    base = validate_base_url(args.base_url)
    fingerprint = source_fingerprint(ROOT)
    report: dict[str, object] = {
        "sequence": 11,
        "release": "1.1.0",
        "roadmap": "ROADMAP-R2-2026-09-07",
        "created_at": datetime.now(UTC).isoformat(),
        "repository_commit": args.repository_commit,
        "source_fingerprint": fingerprint,
        "measured_flood_validation": False,
        "strict_backtest_eligible": False,
        "final_human_acceptance_pending": True,
    }
    errors = []
    checks = {}
    if args.run_checks:
        for name, command in {
            "ruff": ["-m", "ruff", "check", "."],
            "mypy": ["-m", "mypy", "floodguard", "apps", "scripts"],
            "pytest": ["-m", "pytest"],
        }.items():
            result = subprocess.run([sys.executable, *command], cwd=ROOT, check=False)
            checks[name] = result.returncode == 0
    if set(checks) != {"ruff", "mypy", "pytest"} or not all(checks.values()):
        errors.append("Complete Python 3.12 static and regression checks have not passed.")
    report["software_checks"] = checks
    if sys.version_info[:2] != (3, 12) or lock_mismatches(ROOT / "requirements.lock"):
        errors.append("Pinned runtime mismatch.")
    try:
        version = json.loads(read(base, "/version"))
        report["deployed_version"] = version
        if (
            version["version"] != "1.1.0"
            or version["sequence"] != 11
            or version["source_fingerprint"] != fingerprint
            or version["dependency_lock_mismatches"]
        ):
            errors.append("Deployed source/runtime differs from checked source.")
        readiness = json.loads(read(base, "/ready"))
        if readiness.get("status") != "ready":
            errors.append("Platform dependencies not ready.")
        drain = json.loads(read(base, "/drainage/readiness"))
        twin = json.loads(read(base, "/twins/readiness"))
        forcing = json.loads(read(base, "/forcing/readiness"))
        errors.extend(drain_readiness_blockers(drain))
        errors.extend(readiness_errors(forcing))
        report["inherited_twin_freeze_blockers"] = twin_readiness_blockers(twin)
        report["inherited_readiness"] = {"drainage": drain, "twin": twin, "forcing": forcing}
        with get_session_factory()() as session:
            service = build_history_service(session)
            event = service.get(args.event_id)
            report["manifest"] = event.model_dump(mode="json")
            if event.software_source_sha256 != fingerprint:
                errors.append("Event was prepared by different source.")
            if event.availability.availability_status != "UNKNOWN":
                errors.append("POWER historical availability must remain unknown.")
            view = service.view(args.event_id)
            if (
                view["request"]["selection"]["longitude"] != 88.3639
                or view["request"]["selection"]["latitude"] != 22.5726
                or view["coverage"]["valid"] != 24
                or view["coverage"]["total"] != 24
                or len(event.windows) != 8
                or any(w.forcing_package_id is None for w in event.windows)
            ):
                errors.append("Required complete real Kolkata rainfall demonstration missing.")
            report["rainfall_total_mm"] = view["intervals"][-1]["accumulation_mm"]
            report["rainfall_coverage"] = view["coverage"]
            http_event = json.loads(read(base, f"/history/events/{args.event_id}"))
            if http_event != event.model_dump(mode="json"):
                errors.append("HTTP event and validated catalogue differ.")
            http_view = json.loads(read(base, f"/history/events/{args.event_id}/view"))
            if http_view != view:
                errors.append("HTTP preview and verified observations differ.")
            if b"Rainfall preview only" not in read(base, "/history/preview"):
                errors.append("Preview lacks scientific label.")
            # Rebuild from exact retained inputs: timestamps are not new source versions.
            from floodguard.history.contracts import EventRequest

            request = EventRequest.model_validate_json(
                service.forcing.read_blob(event.artifacts["request.json"])
            )
            if service.build(request).historical_event_id != args.event_id:
                errors.append("Repeated build changes event identity.")
            legacy = (ROOT / "tests/fixtures/history/sequence10-manifest.json").read_bytes()
            old = Manifest.model_validate_json(legacy)
            prefix = f"/forcing/products/{old.forcing_package_id}/"
            if read(base, prefix + "manifest") != legacy:
                errors.append("Retained Sequence 10 manifest bytes changed.")
            for name, ref in old.artifacts.items():
                content = read(base, prefix + name)
                if sha256(content) != ref.sha256 or len(content) != ref.byte_size:
                    errors.append(f"Retained v1 artifact mismatch: {name}")
            engine = create_engine("sqlite://")
            cast(Table, ForcingRecord.__table__).create(engine)
            cast(Table, HistoricalEventRecord.__table__).create(engine)
            with Session(engine) as replica_session:
                replica = ForcingService(replica_session, service.forcing.twins)
                if not replica.recreate(legacy).created:
                    errors.append("Fresh catalogue failed to recreate known v1 forcing.")
                history_replica = HistoryService(
                    replica_session,
                    service.forcing,
                    service.harvester,
                )
                restored = history_replica.recreate(canonical_bytes(event.model_dump(mode="json")))
                if restored != event:
                    errors.append("Fresh event catalogue recreation differs.")
            report["legacy_compatibility"] = {
                "forcing_package_id": str(old.forcing_package_id),
                "verified_artifacts_including_manifest": 1 + len(old.artifacts),
                "fresh_catalogue_recreation_passed": True,
            }
            report["migration_revision"] = session.execute(
                text("select version_num from alembic_version")
            ).scalar_one()
            if report["migration_revision"] != "0010_sequence_11_history":
                errors.append("Additive history migration is not current.")
    except (OSError, ValueError, LookupError, KeyError, TypeError) as exc:
        errors.append(f"Evidence verification failed: {type(exc).__name__}: {exc}")
    if source_fingerprint(ROOT) != fingerprint:
        errors.append("Source changed during verification.")
    report["data_gate_errors"] = errors
    report["historical_data_gate"] = "PASSED" if not errors else "BLOCKED"
    report["freeze_status"] = (
        "ELIGIBLE_FOR_R2_DATA_INTERFACE_FREEZE" if not errors else "NOT_FROZEN"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: report[k] for k in ("historical_data_gate", "data_gate_errors")}, indent=2)
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
