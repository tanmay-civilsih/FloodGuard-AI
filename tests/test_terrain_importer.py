import json
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pyproj import Transformer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.routers.terrain import get_terrain_service
from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import DatasetVersionRead
from floodguard.harvester.repository import HarvesterRepository
from floodguard.harvester.service import HarvestAccessError, HarvestConflictError
from floodguard.harvester.vault import MemoryRawVault
from floodguard.reconstruction.contracts import DrainageReconstructionRead, ReconstructionStatus
from floodguard.registry.contracts import SourceRead
from floodguard.registry.models import Base
from floodguard.registry.seed import kolkata_seed_sources, seed_id
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.terrain import bootstrap, import_srtm
from floodguard.terrain.assessment import (
    ASSESSMENT_FILENAME,
    TerrainAssessment,
    assessment_bytes,
    assessment_template,
    decode_assessment,
)
from floodguard.terrain.contracts import TerrainPackage
from floodguard.terrain.grid import decode_package, package_bytes, sha256
from floodguard.terrain.import_srtm import select_pilot
from floodguard.terrain.importer import SrtmImportRequest, TerrainInputImporter
from floodguard.terrain.repository import TerrainRepository
from floodguard.terrain.service import TerrainConditioningError, TerrainService
from floodguard.terrain.srtm import SRTM_SIDE, SrtmTarget, convert_srtm


def completed_assessment(package: TerrainPackage) -> TerrainAssessment:
    """Synthetic review of the 42 m test raster; never real pilot evidence."""
    data = assessment_template(sha256(package_bytes(package)))
    data.update(
        reviewed_by="Synthetic benchmark reviewer",
        reviewed_at=utc_now().isoformat(),
        datum_transform_status="COMPATIBLE",
        local_vertical_datum="EGM96",
        vertical_reference_evidence="Synthetic controls share the fixture EGM96 reference.",
        surface_use_evidence="Synthetic DSM for contract tests only, not a surveyed urban surface.",
        depression_assessment="CATALOGUED",
        depression_evidence="Synthetic protected cell is declared at row 0, column 0.",
        multi_level_assessment="CATALOGUED",
        multi_level_evidence="Synthetic bridge connects two explicitly declared levels.",
        interventions=[{
            "row": 0, "column": 0, "kind": "PRESERVE_DEPRESSION",
            "source_reference": "test://protected-cell", "reason": "Preserve test storage",
        }],
        multi_level_structures=[{
            "structure_id": "synthetic-bridge", "kind": "BRIDGE",
            "bounds_working": package.grid.bounds,
            "lower_elevation_m": 42.0, "upper_elevation_m": 48.0,
            "lower_level_role": "synthetic ground", "upper_level_role": "synthetic road",
            "source_reference": "test://bridge-design", "confidence": 1.0,
        }],
        vertical_validation={
            "method": "Synthetic cell-centre benchmark",
            "control_points": [{
                "control_id": "synthetic-control", "row": 0, "column": 0,
                "reference_elevation_m": 40.0, "vertical_datum": "EGM96",
                "source_reference": "test://two-metre-residual", "measured_at": utc_now(),
            }],
            "limitations": ["Synthetic benchmark; no real survey is represented."],
        },
        limitations=["Synthetic fixture; cannot justify freezing a real pilot."],
    )
    return TerrainAssessment.model_validate(data)


def package_for(hgt_bytes, request) -> TerrainPackage:
    return convert_srtm(
        hgt_bytes, filename=request.filename, target=request.target,
        pilot_area_id=request.pilot_area_id, boundary_reference=request.boundary_reference,
    )


@pytest.fixture(scope="module")
def hgt_bytes() -> bytes:
    return np.full((SRTM_SIDE, SRTM_SIDE), 42, dtype=">i2").tobytes()


@pytest.fixture
def import_context():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        vault = MemoryRawVault()
        store = MemorySpatialObjectStore()
        store.raw_objects = vault.objects
        terrain = TerrainService(
            TerrainRepository(session),
            store,
            working_crs="EPSG:32645",
            max_object_bytes=32 * 1024 * 1024,
        )
        repository = HarvesterRepository(session)
        importer = TerrainInputImporter(
            repository, vault, terrain, max_total_bytes=40 * 1024 * 1024
        )
        source_config = next(
            item for item in kolkata_seed_sources() if item.source_id == seed_id("nasa-srtmgl1")
        )
        source = SourceRead(
            **source_config.model_dump(), created_at=utc_now(), updated_at=utc_now()
        )
        x, y = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True).transform(
            88.37, 22.60
        )
        request = SrtmImportRequest(
            filename="N22E088.hgt",
            pilot_area_id="kolkata-ward-7-test",
            target=SrtmTarget(working_crs="EPSG:32645", bounds_working=[x, y, x + 100, y + 100]),
            boundary_reference="test://approved-reconstruction",
            imported_by="Test operator",
            access_reference="Synthetic test fixture, not a real NASA download",
        )
        yield importer, repository, vault, terrain, source, request


def test_dry_run_validates_without_creating_versions_or_objects(import_context, hgt_bytes) -> None:
    importer, repository, vault, terrain, source, request = import_context
    preview = importer.import_srtm(source, hgt_bytes, request, dry_run=True)
    assert preview.dry_run
    assert preview.width > 0 and preview.height > 0
    assert preview.raw_sha256 == sha256(hgt_bytes)
    assert preview.dataset_version_id is preview.terrain is None
    assert repository.list_for_source(source.source_id) == []
    assert vault.objects == {}
    assert terrain.list_products() == []


def test_import_is_immutable_idempotent_and_serves_original_hgt(import_context, hgt_bytes) -> None:
    importer, repository, vault, terrain, source, request = import_context
    result = importer.import_srtm(source, hgt_bytes, request)
    unchanged = dict(vault.objects)
    reused = importer.import_srtm(source, hgt_bytes, request)
    assert result.raw_version_created and result.terrain.created
    assert not reused.raw_version_created and not reused.terrain.created
    assert reused.dataset_version_id == result.dataset_version_id
    assert vault.objects == unchanged
    assert len(repository.list_for_source(source.source_id)) == 1
    version = DatasetVersionRead.model_validate(repository.get_version(result.dataset_version_id))
    assert version.status.value == "COMPLETE" and version.object_count == 3
    assert version.source_snapshot["access_class"] == "AUTHORIZATION_REQUIRED"
    receipt = next(item for item in version.objects if item.filename == "import-receipt.json")
    audit_input = json.loads(vault.objects[receipt.object_key])
    assert audit_input["network_acquisition_performed"] is False
    assert audit_input["request"]["access_reference"] == request.access_reference
    assert audit_input["source_sha256"] == sha256(hgt_bytes)
    built = result.terrain
    assert built.readiness_status.value == "VISUAL_READY"
    assert terrain.read_artifact(built.terrain_id, "RAW_ELEVATION") == hgt_bytes
    audit = json.loads(terrain.read_artifact(built.terrain_id, "AUDIT"))
    assert audit["original_elevation"]["sha256"] == sha256(hgt_bytes)
    assert audit["derivation"]["boundary_reference"] == request.boundary_reference
    record = terrain.get(built.terrain_id)
    assert record.raw_elevation_object_key.endswith(".hgt")
    assert record.source_object_key.endswith(".terrain.json")
    assert not terrain.readiness(city_id="kolkata").completion_gate_passed

    app.dependency_overrides[get_terrain_service] = lambda: terrain
    try:
        response = TestClient(app).get(f"/terrain/products/{built.terrain_id}/raw")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert sha256(response.content) == sha256(hgt_bytes)
    finally:
        app.dependency_overrides.clear()


def test_changed_access_receipt_creates_a_new_version_without_overwriting(
    import_context, hgt_bytes
) -> None:
    importer, repository, vault, _, source, request = import_context
    initial = importer.import_srtm(source, hgt_bytes, request)
    originals = dict(vault.objects)
    changed = request.model_copy(
        update={"access_reference": "Updated synthetic provenance documentation"}
    )
    result = importer.import_srtm(source, hgt_bytes, changed)
    assert initial.dataset_version_id != result.dataset_version_id
    assert all(vault.objects[key] == payload for key, payload in originals.items())
    version = repository.get_version(result.dataset_version_id)
    assert version.previous_version_id == initial.dataset_version_id


@pytest.mark.parametrize("access_class", ["PUBLIC_VIEW_ONLY", "UNKNOWN", "COMMERCIAL_OPTIONAL"])
def test_blocked_governance_is_not_bypassed(import_context, hgt_bytes, access_class) -> None:
    importer, repository, vault, _, source, request = import_context
    blocked = source.model_copy(update={"access_class": access_class})
    with pytest.raises(HarvestAccessError):
        importer.import_srtm(blocked, hgt_bytes, request)
    assert vault.objects == {} and repository.list_for_source(source.source_id) == []


def test_blank_provenance_and_wrong_inputs_fail_before_writing(import_context, hgt_bytes) -> None:
    importer, repository, vault, _, source, request = import_context
    data = request.model_dump()
    data["access_reference"] = "  "
    with pytest.raises(ValidationError):
        SrtmImportRequest.model_validate(data)
    with pytest.raises(ValueError, match="exactly"):
        importer.import_srtm(source, b"fake", request)
    with pytest.raises(ValueError, match="registered NASA"):
        importer.import_srtm(source.model_copy(update={"source_id": uuid4()}), hgt_bytes, request)
    importer.max_total_bytes = 1
    with pytest.raises(ValueError, match="storage limits"):
        importer.import_srtm(source, hgt_bytes, request)
    assert vault.objects == {} and repository.list_for_source(source.source_id) == []


def test_failed_raw_write_never_marks_a_complete_version(
    import_context, hgt_bytes, monkeypatch
) -> None:
    importer, repository, vault, terrain, source, request = import_context
    original_put = vault.put_bytes_once

    def fail_package(key, payload, *, content_type):
        if key.endswith(".terrain.json"):
            raise RuntimeError("injected storage failure")
        original_put(key, payload, content_type=content_type)

    monkeypatch.setattr(vault, "put_bytes_once", fail_package)
    with pytest.raises(RuntimeError, match="injected"):
        importer.import_srtm(source, hgt_bytes, request)
    versions = repository.list_for_source(source.source_id)
    assert len(versions) == 1 and versions[0].status == "FAILED"
    assert terrain.list_products() == []
    with pytest.raises(HarvestConflictError, match="incomplete version"):
        importer.import_srtm(source, hgt_bytes, request)


@pytest.mark.parametrize(
    "change", ["missing_original", "corrupt_original", "altered_grid", "inflated_quality"]
)
def test_build_requires_reproducible_original_lineage(import_context, hgt_bytes, change) -> None:
    importer, repository, vault, terrain, source, request = import_context
    result = importer.import_srtm(source, hgt_bytes, request)
    version = DatasetVersionRead.model_validate(repository.get_version(result.dataset_version_id))
    original = next(item for item in version.objects if item.filename.endswith(".hgt"))
    package_object = next(
        item for item in version.objects if item.filename.endswith(".terrain.json")
    )
    if change == "missing_original":
        version = version.model_copy(update={"objects": [package_object]})
    elif change == "corrupt_original":
        vault.objects[original.object_key] = b"corrupt"
    else:
        package = decode_package(vault.objects[package_object.object_key])
        if change == "altered_grid":
            package.grid.elevations_m[0][0] += 1
        else:
            package = package.model_copy(update={"native_horizontal_resolution_m": 1})
        payload = package_bytes(package)
        vault.objects[package_object.object_key] = payload
        updated = package_object.model_copy(
            update={"sha256": sha256(payload), "byte_size": len(payload)}
        )
        version = version.model_copy(update={"objects": [original, updated]})
        package_object = updated
    with pytest.raises(TerrainConditioningError):
        terrain.build_from_raw(source, version, package_object)


def test_pilot_selection_requires_latest_approved_reconstruction() -> None:
    now = utc_now()
    approved = DrainageReconstructionRead.model_construct(
        reconstruction_id=uuid4(),
        city_id="kolkata",
        ward_id="7",
        created_at=now,
        status=ReconstructionStatus.APPROVED,
        working_crs="EPSG:32645",
    )
    assert select_pilot([approved], "kolkata", "7", "EPSG:32645") is approved
    pending = approved.model_copy(
        update={
            "created_at": now + timedelta(seconds=1),
            "status": ReconstructionStatus.PENDING_REVIEW,
        }
    )
    with pytest.raises(ValueError, match="human QA"):
        select_pilot([approved, pending], "kolkata", "7", "EPSG:32645")
    with pytest.raises(ValueError, match="no reconstruction"):
        select_pilot([approved], "kolkata", "8", "EPSG:32645")
    with pytest.raises(ValueError, match="working CRS"):
        select_pilot([approved], "kolkata", "7", "EPSG:32644")


@pytest.mark.parametrize(
    "mode", ["plan", "dry-run", "import", "template", "review-dry-run", "review-import"]
)
def test_import_cli_end_to_end(
    import_context, hgt_bytes, tmp_path, monkeypatch, capsys, mode
) -> None:
    importer, repository, vault, terrain, source, request = import_context
    pilot = DrainageReconstructionRead.model_construct(
        reconstruction_id=uuid4(),
        city_id="kolkata",
        ward_id="7",
        created_at=utc_now(),
        status=ReconstructionStatus.APPROVED,
        working_crs="EPSG:32645",
        working_sha256="a" * 64,
        bounds_working=request.target.bounds_working,
        bounds_wgs84=[88.37, 22.60, 88.371, 22.601],
    )
    monkeypatch.setattr(
        import_srtm,
        "get_settings",
        lambda: SimpleNamespace(
            working_crs="EPSG:32645",
            harvest_max_total_bytes=40 * 1024 * 1024,
            harvest_max_object_bytes=32 * 1024 * 1024,
        ),
    )
    monkeypatch.setattr(
        import_srtm, "get_session_factory", lambda: lambda: nullcontext(repository.session)
    )
    monkeypatch.setattr(
        import_srtm,
        "RegistryService",
        lambda session: SimpleNamespace(get_source=lambda source_id: source),
    )
    monkeypatch.setattr(
        import_srtm,
        "ReconstructionRepository",
        lambda session: SimpleNamespace(
            reads=lambda records: records,
            list_reconstructions=lambda **kwargs: [pilot],
        ),
    )
    monkeypatch.setattr(
        import_srtm, "build_harvester_service", lambda session: SimpleNamespace(vault=vault)
    )
    monkeypatch.setattr(import_srtm, "build_terrain_service", lambda session: terrain)
    args = ["import_srtm"]
    if mode == "plan":
        args.append("--plan")
    else:
        path = tmp_path / "N22E088.hgt"
        path.write_bytes(hgt_bytes)
        args.extend(
            [
                "--file",
                str(path),
                "--imported-by",
                "Test operator",
                "--access-reference",
                "Synthetic test fixture only",
            ]
        )
        if mode in {"dry-run", "review-dry-run"}:
            args.append("--dry-run")
        if mode == "template":
            args.extend(["--assessment-template", str(tmp_path / "assessment.json")])
        if mode.startswith("review-"):
            cli_request = request.model_copy(update={
                "pilot_area_id": "kolkata-ward-7",
                "boundary_reference": (
                    f"reconstruction://{pilot.reconstruction_id}"
                    f"#working_sha256={pilot.working_sha256}"
                ),
            })
            review = completed_assessment(package_for(hgt_bytes, cli_request))
            review_path = tmp_path / "assessment.json"
            review_path.write_bytes(assessment_bytes(review))
            args.extend(["--assessment", str(review_path)])
    monkeypatch.setattr("sys.argv", args)
    import_srtm.main()
    output = capsys.readouterr().out
    if mode == "plan":
        plan = json.loads(output)
        assert plan["required_tiles"] == ["N22E088.hgt"]
        assert plan["supported"] and not plan["writes_performed"]
    elif mode in {"dry-run", "template", "review-dry-run"}:
        assert '"dry_run": true' in output
        if mode == "template":
            with pytest.raises(ValidationError):
                decode_assessment((tmp_path / "assessment.json").read_bytes())
    elif mode == "review-import":
        assert '"readiness_status": "HYDRAULIC_SCENARIO_READY"' in output
    else:
        assert '"readiness_status": "VISUAL_READY"' in output
    written = mode in {"import", "review-import"}
    assert len(repository.list_for_source(source.source_id)) == int(written)
    assert bool(vault.objects) == written


def test_import_respects_raw_vault_object_limit(import_context, hgt_bytes) -> None:
    importer, repository, vault, terrain, source, request = import_context
    limited = TerrainInputImporter(
        repository, vault, terrain, max_total_bytes=40 * 1024 * 1024, max_object_bytes=1024
    )
    with pytest.raises(ValueError, match="object size limit"):
        limited.import_srtm(source, hgt_bytes, request)
    assert vault.objects == {}


def test_empty_bootstrap_fails_with_actionable_import_instruction(
    import_context, monkeypatch
) -> None:
    _, repository, vault, terrain, source, _ = import_context
    monkeypatch.setattr(
        bootstrap, "get_session_factory", lambda: lambda: nullcontext(repository.session)
    )
    monkeypatch.setattr(
        bootstrap,
        "RegistryService",
        lambda session: SimpleNamespace(
            list_sources=lambda **kwargs: [source],
        ),
    )
    monkeypatch.setattr(bootstrap, "build_terrain_service", lambda session: terrain)
    monkeypatch.setattr("sys.argv", ["bootstrap", "--city-id", "kolkata"])
    with pytest.raises(SystemExit, match="import_srtm --plan"):
        bootstrap.main()
    assert vault.objects == {} and terrain.list_products() == []


def test_assessed_import_retains_original_and_computes_two_metre_residual(
    import_context, hgt_bytes
) -> None:
    importer, repository, vault, terrain, source, request = import_context
    initial = importer.import_srtm(source, hgt_bytes, request)
    originals = dict(vault.objects)
    review = completed_assessment(package_for(hgt_bytes, request))
    preview = importer.import_srtm(source, hgt_bytes, request, assessment=review, dry_run=True)
    assert preview.base_package_sha256 == review.base_package_sha256
    assert vault.objects == originals
    result = importer.import_srtm(source, hgt_bytes, request, assessment=review)
    assert result.dataset_version_id != initial.dataset_version_id
    assert result.terrain.readiness_status.value == "HYDRAULIC_SCENARIO_READY"
    record = terrain.get(result.terrain.terrain_id)
    assert record.vertical_rmse_m == 2.0 and record.control_point_count == 1
    assert record.preserved_depression_count == record.multi_level_structure_count == 1
    assert terrain.read_artifact(record.terrain_id, "RAW_ELEVATION") == hgt_bytes
    visual = json.loads(terrain.read_artifact(record.terrain_id, "VISUAL_TERRAIN"))
    hydraulic = json.loads(terrain.read_artifact(record.terrain_id, "HYDRAULIC_TERRAIN"))
    assert visual["grid"] == hydraulic["grid"]
    assert hydraulic["grid"]["elevations_m"][0][0] == 42.0
    assert all(vault.objects[key] == value for key, value in originals.items())
    audit = json.loads(terrain.read_artifact(record.terrain_id, "AUDIT"))
    assert audit["terrain_assessment"] == review.model_dump(mode="json")
    assert audit["assessment_evidence_verification"].startswith("OPERATOR_ASSERTED")
    version = repository.get_version(result.dataset_version_id)
    assert version.object_count == 4
    reviewed_objects = dict(vault.objects)
    reused = importer.import_srtm(source, hgt_bytes, request, assessment=review)
    assert reused.dataset_version_id == result.dataset_version_id
    assert not reused.terrain.created and vault.objects == reviewed_objects
    assert terrain.readiness(city_id="kolkata").completion_gate_passed

    failed = review.model_dump(mode="json")
    failed["vertical_validation"]["road_sag_validation"] = "FAILED"
    downgraded = importer.import_srtm(
        source, hgt_bytes, request, assessment=TerrainAssessment.model_validate(failed)
    )
    assert downgraded.terrain.readiness_status.value == "VISUAL_READY"
    assert not terrain.readiness(city_id="kolkata").completion_gate_passed


@pytest.mark.parametrize("change", ["source", "pilot", "grid", "intervention", "rmse"])
def test_stale_or_invalid_assessment_fails_before_writing(
    import_context, hgt_bytes, change
) -> None:
    importer, repository, vault, _, source, request = import_context
    review = completed_assessment(package_for(hgt_bytes, request))
    if change == "source":
        hgt_bytes = np.full((SRTM_SIDE, SRTM_SIDE), 43, dtype=">i2").tobytes()
    elif change == "pilot":
        request = request.model_copy(update={"boundary_reference": "test://new-pilot-extent"})
    elif change == "grid":
        request = request.model_copy(update={
            "target": request.target.model_copy(update={"cell_size_m": 60.0}),
        })
    else:
        data = review.model_dump(mode="json")
        if change == "intervention":
            data["interventions"][0]["row"] = 99999
        else:
            data["vertical_validation"]["rmse_m"] = 0.0
        review = TerrainAssessment.model_validate(data)
    for dry_run in (True, False):
        with pytest.raises(ValueError):
            importer.import_srtm(source, hgt_bytes, request, assessment=review, dry_run=dry_run)
    assert vault.objects == {} and repository.list_for_source(source.source_id) == []


@pytest.mark.parametrize("change", ["missing", "corrupt", "other_version", "duplicate"])
def test_terrain_build_rechecks_immutable_assessment(import_context, hgt_bytes, change) -> None:
    importer, repository, vault, terrain, source, request = import_context
    review = completed_assessment(package_for(hgt_bytes, request))
    built = importer.import_srtm(source, hgt_bytes, request, assessment=review)
    version = DatasetVersionRead.model_validate(repository.get_version(built.dataset_version_id))
    package = next(item for item in version.objects if item.filename == "pilot.terrain.json")
    evidence = next(item for item in version.objects if item.filename == ASSESSMENT_FILENAME)
    objects = [item for item in version.objects if item != evidence]
    if change == "corrupt":
        vault.objects[evidence.object_key] = b"{}"
        objects.append(evidence)
    elif change == "other_version":
        objects.append(evidence.model_copy(update={"dataset_version_id": uuid4()}))
    elif change == "duplicate":
        objects.extend([evidence, evidence])
    version = version.model_copy(update={"objects": objects})
    with pytest.raises(TerrainConditioningError):
        terrain.build_from_raw(source, version, package)


@pytest.mark.parametrize(
    "change", ["blank", "naive_time", "wrong_datum", "invented_controls", "unknown_field"]
)
def test_assessment_requires_explicit_valid_evidence(import_context, hgt_bytes, change) -> None:
    *_, request = import_context
    data = completed_assessment(package_for(hgt_bytes, request)).model_dump(mode="json")
    if change == "blank":
        data["depression_evidence"] = "  "
    elif change == "naive_time":
        data["reviewed_at"] = "2026-09-05T12:00:00"
    elif change == "wrong_datum":
        data["local_vertical_datum"] = "local datum unknown"
    elif change == "invented_controls":
        data["vertical_validation"]["control_points"] = []
        data["vertical_validation"]["control_point_count"] = 100
    else:
        data["force_ready"] = True
    with pytest.raises(ValidationError):
        TerrainAssessment.model_validate(data)


def test_assessment_decoder_accepts_utf8_bom_and_rejects_duplicate_keys(
    import_context, hgt_bytes
) -> None:
    *_, request = import_context
    review = completed_assessment(package_for(hgt_bytes, request))
    encoded = assessment_bytes(review)
    assert decode_assessment(b"\xef\xbb\xbf" + encoded) == review
    with pytest.raises(ValueError, match="duplicate"):
        decode_assessment(b'{"reviewed_by":"first",' + encoded[1:])


def test_assessment_schema_does_not_require_a_database(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["import_srtm", "--assessment-schema"])
    import_srtm.main()
    schema = json.loads(capsys.readouterr().out)
    assert "reviewed_at" in schema["required"]
    assert schema["additionalProperties"] is False
