import io
import json
import zipfile
from contextlib import nullcontext
from dataclasses import replace
from types import SimpleNamespace
from typing import ClassVar
from uuid import uuid4

import pytest
from pyproj import Transformer

from floodguard.contracts.time import utc_now
from floodguard.harvester.acquisition import AcquisitionParametersRequired, AcquisitionPlanner
from floodguard.harvester.contracts import DatasetVersionRead
from floodguard.harvester.service import HarvestAccessError
from floodguard.reconstruction.contracts import DrainageReconstructionRead, ReconstructionStatus
from floodguard.registry.contracts import SourceRead
from floodguard.registry.seed import ESA_SRTM_ID, kolkata_seed_sources
from floodguard.terrain import acquire_srtm, acquisition, download
from floodguard.terrain.acquisition import (
    TerrainAcquirer,
    TerrainAcquisitionPlan,
    TerrainAcquisitionRequest,
)
from floodguard.terrain.download import SrtmArchive, archive_url, unpack_srtm
from floodguard.terrain.grid import package_bytes, sha256
from floodguard.terrain.srtm import SrtmTarget, required_srtm_tiles
from tests import test_terrain_importer as importer_fixtures
from tests.test_terrain_importer import completed_assessment, package_for

hgt_bytes = importer_fixtures.hgt_bytes
import_context = importer_fixtures.import_context


def archive_with(files: dict[str, bytes]) -> SrtmArchive:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, payload in files.items():
            zipped.writestr(name, payload)
    return SrtmArchive(
        archive_url("N22E088"), "N22E088.SRTMGL1.hgt.zip", buffer.getvalue(), utc_now(),
        etag='"test-etag"', last_modified="Mon, 01 Sep 2025 00:00:00 GMT",
    )


@pytest.fixture(scope="module")
def archive(hgt_bytes):
    return archive_with({"N22E088.hgt": hgt_bytes})


@pytest.fixture
def acquisition_context(import_context, archive):
    importer, repository, vault, terrain, _, request = import_context
    config = next(item for item in kolkata_seed_sources() if item.source_id == ESA_SRTM_ID)
    source = SourceRead(**config.model_dump(), created_at=utc_now(), updated_at=utc_now())
    plan = TerrainAcquisitionPlan(
        request=TerrainAcquisitionRequest(), source_id=source.source_id,
        reconstruction_id=uuid4(), boundary_reference=request.boundary_reference,
        pilot_area_id=request.pilot_area_id, target=request.target, tile="N22E088",
        source_url=archive.source_url,
    )
    calls = []

    def downloader(tile, **kwargs):
        calls.append((tile, kwargs))
        return archive

    worker = TerrainAcquirer(importer, timeout_seconds=10, downloader=downloader)
    return SimpleNamespace(
        worker=worker, source=source, plan=plan, calls=calls, repository=repository,
        vault=vault, terrain=terrain, request=request,
    )


def test_download_build_and_retry_reuse_original_bytes(acquisition_context, hgt_bytes, archive):
    ctx = acquisition_context
    first = ctx.worker.acquire(ctx.source, ctx.plan)
    original_objects = dict(ctx.vault.objects)
    second = ctx.worker.acquire(ctx.source, ctx.plan)
    assert first.downloaded and not second.downloaded and len(ctx.calls) == 1
    assert first.result.dataset_version_id == second.result.dataset_version_id
    assert first.result.base_package_sha256 == second.result.base_package_sha256
    assert not second.result.raw_version_created and not second.result.terrain.created
    assert ctx.vault.objects == original_objects
    version = DatasetVersionRead.model_validate(
        ctx.repository.get_version(first.result.dataset_version_id)
    )
    assert version.object_count == 4 and version.status.value == "COMPLETE"
    assert version.source_snapshot["access_class"] == "OPEN_AUTOMATED"
    stored_zip = next(item for item in version.objects if item.filename.endswith(".zip"))
    assert ctx.vault.objects[stored_zip.object_key] == archive.payload
    receipt_object = next(
        item for item in version.objects if item.filename == "import-receipt.json"
    )
    receipt = json.loads(ctx.vault.objects[receipt_object.object_key])
    assert receipt["network_acquisition_performed"] is True
    assert receipt["acquisition"] == archive.provenance()
    assert first.result.terrain.readiness_status.value == "VISUAL_READY"
    terrain_id = first.result.terrain.terrain_id
    assert ctx.terrain.read_artifact(terrain_id, "RAW_ELEVATION") == hgt_bytes
    audit = json.loads(ctx.terrain.read_artifact(terrain_id, "AUDIT"))
    assert audit["source_archive"]["sha256"] == sha256(archive.payload)
    assert not ctx.terrain.readiness(city_id="kolkata").completion_gate_passed


def test_retry_preserves_completed_assessment(acquisition_context, hgt_bytes):
    ctx = acquisition_context
    baseline = ctx.worker.acquire(ctx.source, ctx.plan)
    package = package_for(hgt_bytes, ctx.request)
    reviewed = ctx.worker.acquire(ctx.source, ctx.plan, assessment=completed_assessment(package))
    again = ctx.worker.acquire(ctx.source, ctx.plan)
    assert len(ctx.calls) == 1 and not reviewed.downloaded and not again.downloaded
    assert baseline.result.dataset_version_id != reviewed.result.dataset_version_id
    assert again.result.dataset_version_id == reviewed.result.dataset_version_id
    assert again.result.base_package_sha256 == sha256(package_bytes(package))
    assert again.result.terrain.readiness_status.value == "HYDRAULIC_SCENARIO_READY"
    assert len(ctx.repository.list_for_source(ctx.source.source_id)) == 2


def test_new_pilot_extent_reuses_download_but_creates_new_version(acquisition_context):
    ctx = acquisition_context
    first = ctx.worker.acquire(ctx.source, ctx.plan)
    new_plan = ctx.plan.model_copy(update={"boundary_reference": "test://new-approved-extent"})
    second = ctx.worker.acquire(ctx.source, new_plan)
    assert len(ctx.calls) == 1 and not second.downloaded
    assert first.result.dataset_version_id != second.result.dataset_version_id


@pytest.mark.parametrize("mode", ["dry_run", "changed_pilot"])
def test_preflight_leaves_no_partial_inputs(acquisition_context, mode):
    ctx = acquisition_context

    def changed_pilot():
        raise ValueError("pilot was rejected during download")

    if mode == "dry_run":
        result = ctx.worker.acquire(ctx.source, ctx.plan, dry_run=True)
        assert result.result.dry_run and result.result.terrain is None
    else:
        with pytest.raises(ValueError, match="pilot was rejected"):
            ctx.worker.acquire(ctx.source, ctx.plan, check_pilot=changed_pilot)
    assert len(ctx.calls) == 1
    assert ctx.vault.objects == {} and ctx.terrain.list_products() == []
    assert ctx.repository.list_for_source(ctx.source.source_id) == []


@pytest.mark.parametrize("change", [
    {"automation_allowed": False}, {"access_class": "AUTHORIZATION_REQUIRED"},
    {"authentication_type": "EARTHDATA_LOGIN"}, {"endpoint": "https://example.invalid/"},
])
def test_source_governance_blocks_network_before_download(acquisition_context, change):
    ctx = acquisition_context
    with pytest.raises(HarvestAccessError):
        ctx.worker.acquire(ctx.source.model_copy(update=change), ctx.plan)
    assert ctx.calls == [] and ctx.vault.objects == {}


@pytest.mark.parametrize("change", ["corrupt", "missing"])
def test_build_requires_verified_original_archive(acquisition_context, change):
    ctx = acquisition_context
    result = ctx.worker.acquire(ctx.source, ctx.plan)
    version = DatasetVersionRead.model_validate(
        ctx.repository.get_version(result.result.dataset_version_id)
    )
    archive = next(item for item in version.objects if item.filename.endswith(".zip"))
    package = next(item for item in version.objects if item.filename.endswith(".terrain.json"))
    if change == "corrupt":
        ctx.vault.objects[archive.object_key] = b"tampered"
    else:
        version = version.model_copy(update={
            "objects": [item for item in version.objects if item != archive],
        })
    with pytest.raises((ValueError, RuntimeError), match="ZIP"):
        ctx.terrain.build_from_raw(ctx.source, version, package)


@pytest.mark.parametrize("files", [
    {"../N22E088.hgt": b"bad"}, {"N22E089.hgt": b"bad"},
    {"N22E088.hgt": b"bad"}, {"N22E088.hgt": b"bad", "extra.txt": b"bad"},
])
def test_unexpected_zip_contents_are_rejected(files):
    with pytest.raises(ValueError, match="HGT|one original"):
        unpack_srtm(archive_with(files), "N22E088")


def test_html_and_wrong_tile_are_rejected(archive):
    with pytest.raises(ValueError, match="valid original"):
        unpack_srtm(replace(archive, payload=b"<html>Unavailable</html>"), "N22E088")
    with pytest.raises(ValueError, match="requested public tile"):
        unpack_srtm(archive, "N22E089")


def test_downloader_bounds_streams_and_rejects_redirects(monkeypatch):
    requests = []

    class Response(io.BytesIO):
        status = 200
        headers: ClassVar[dict[str, str]] = {}

        def geturl(self):
            return archive_url("N22E088")

    def open_request(request, **kwargs):
        requests.append(request)
        return Response(b"12345")

    monkeypatch.setattr(download, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    result = download.download_srtm("N22E088", max_bytes=5, timeout_seconds=10)
    assert result.payload == b"12345" and not requests[0].has_header("Authorization")
    with pytest.raises(ValueError, match="byte limit"):
        download.download_srtm("N22E088", max_bytes=4, timeout_seconds=10)
    Response.headers = {"Content-Length": "20"}
    with pytest.raises(ValueError, match="byte limit"):
        download.download_srtm("N22E088", max_bytes=5, timeout_seconds=10)
    Response.headers = {}
    Response.geturl = lambda self: "https://example.invalid/redirect"
    with pytest.raises(ValueError, match="requested tile"):
        download.download_srtm("N22E088", max_bytes=5, timeout_seconds=10)
    with pytest.raises(ValueError, match="redirected"):
        download.NoRedirects().redirect_request(None, None, 302, "", {}, "https://example.invalid")


def test_downloader_enforces_total_deadline(monkeypatch):
    clock = iter([0.0, 121.0])
    response = SimpleNamespace(status=200, headers={}, geturl=lambda: archive_url("N22E088"))
    monkeypatch.setattr(download.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(download, "build_opener", lambda *args: SimpleNamespace(
        open=lambda *args, **kwargs: nullcontext(response),
    ))
    with pytest.raises(ValueError, match="total time limit"):
        download.download_srtm("N22E088", max_bytes=100, timeout_seconds=10)


def test_tile_selection_uses_snapped_grid_centres():
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform(89, 22.6)
    target = SrtmTarget(working_crs="EPSG:3857", bounds_working=[x + .1, y, x + 1, y + 1])
    assert required_srtm_tiles(target) == ["N22E088"]
    crossing = target.model_copy(update={"bounds_working": [x - 1, y, x + 40, y + 1]})
    assert required_srtm_tiles(crossing) == ["N22E088", "N22E089"]


def test_plan_traces_approved_boundary_without_network(acquisition_context, monkeypatch):
    ctx = acquisition_context
    pilot = DrainageReconstructionRead.model_construct(
        reconstruction_id=ctx.plan.reconstruction_id, city_id="kolkata", ward_id="7",
        status=ReconstructionStatus.APPROVED, working_crs="EPSG:32645",
        bounds_working=ctx.plan.target.bounds_working, working_sha256="a" * 64,
        created_at=utc_now(),
    )
    monkeypatch.setattr(acquisition, "RegistryService", lambda _: SimpleNamespace(
        get_source=lambda _: ctx.source,
    ))
    monkeypatch.setattr(acquisition, "ReconstructionRepository", lambda _: SimpleNamespace(
        list_reconstructions=lambda **kwargs: [pilot], reads=lambda records: records,
    ))
    plan = acquisition.plan_acquisition(None, ctx.plan.request, working_crs="EPSG:32645")
    assert plan.tile == "N22E088" and plan.reconstruction_id == pilot.reconstruction_id
    assert plan.boundary_reference.endswith("#working_sha256=" + "a" * 64)
    assert plan.pilot_area_id == "kolkata-ward-7" and ctx.calls == []
    pilot.status = ReconstructionStatus.PENDING_REVIEW
    with pytest.raises(ValueError, match="human QA approval"):
        acquisition.plan_acquisition(None, ctx.plan.request, working_crs="EPSG:32645")


@pytest.mark.parametrize("mode", ["plan", "dry-run", "import", "template", "review"])
def test_automatic_cli_uses_approved_plan(acquisition_context, hgt_bytes, monkeypatch, tmp_path,
                                        capsys, mode):
    ctx = acquisition_context
    session = SimpleNamespace(expire_all=lambda: None)
    monkeypatch.setattr(acquire_srtm, "get_session_factory", lambda: lambda: nullcontext(session))
    monkeypatch.setattr(acquire_srtm, "plan_acquisition", lambda *args, **kwargs: ctx.plan)
    monkeypatch.setattr(acquire_srtm, "build_terrain_acquirer", lambda _: ctx.worker)
    monkeypatch.setattr(acquire_srtm, "RegistryService", lambda _: SimpleNamespace(
        get_source=lambda _: ctx.source,
    ))
    args = ["acquire_srtm"]
    path = tmp_path / "assessment.json"
    if mode in {"plan", "dry-run"}:
        args.append("--" + mode)
    elif mode == "template":
        args.extend(["--assessment-template", str(path)])
    elif mode == "review":
        path.write_text(completed_assessment(package_for(hgt_bytes, ctx.request)).model_dump_json())
        args.extend(["--assessment", str(path)])
    monkeypatch.setattr("sys.argv", args)
    acquire_srtm.main()
    output = capsys.readouterr().out
    if mode == "plan":
        assert json.loads(output)["tile"] == "N22E088" and ctx.calls == []
    else:
        assert len(ctx.calls) == 1 and "does not approve" in output
    if mode in {"plan", "dry-run", "template"}:
        assert ctx.vault.objects == {}
    else:
        assert len(ctx.terrain.list_products()) == 1
    if mode == "template":
        assert json.loads(path.read_text())["base_package_sha256"] == sha256(
            package_bytes(package_for(hgt_bytes, ctx.request))
        )


def test_generic_harvester_does_not_import_mirror_index(acquisition_context):
    source = acquisition_context.source
    planner = AcquisitionPlanner(None)
    with pytest.raises(AcquisitionParametersRequired):
        planner.plan(source, parameters={})
    plan = planner.plan(source, parameters={"tile": "N22E088"})
    assert len(plan) == 1 and plan[0].url == archive_url("N22E088")
