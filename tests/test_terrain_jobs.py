import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.routers import terrain as terrain_api
from floodguard.common.auth import require_write_access
from floodguard.harvester.service import HarvestAccessError
from floodguard.registry.database import get_db_session
from floodguard.terrain import jobs as job_worker
from floodguard.terrain.jobs import AcquisitionBusyError, TerrainJobStore
from tests import test_terrain_acquisition as acquisition_fixtures

hgt_bytes = acquisition_fixtures.hgt_bytes
import_context = acquisition_fixtures.import_context
archive = acquisition_fixtures.archive
acquisition_context = acquisition_fixtures.acquisition_context


@pytest.fixture
def job_context(acquisition_context, monkeypatch):
    ctx = acquisition_context
    ctx.jobs = TerrainJobStore()
    sessions = []

    def new_session():
        session = SimpleNamespace(expire_all=lambda: None)
        sessions.append(session)
        return nullcontext(session)

    monkeypatch.setattr(job_worker, "get_session_factory", lambda: new_session)
    monkeypatch.setattr(job_worker, "plan_acquisition", lambda *args, **kwargs: ctx.plan)
    monkeypatch.setattr(job_worker, "build_terrain_acquirer", lambda _: ctx.worker)
    monkeypatch.setattr(job_worker, "RegistryService", lambda _: SimpleNamespace(
        get_source=lambda _: ctx.source,
    ))
    monkeypatch.setattr(terrain_api, "plan_acquisition", lambda *args, **kwargs: ctx.plan)
    # Authorization is tested independently; this fixture exercises worker behavior.
    app.dependency_overrides[require_write_access] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: None
    app.dependency_overrides[terrain_api.get_terrain_jobs] = lambda: ctx.jobs
    app.dependency_overrides[terrain_api.get_terrain_service] = lambda: ctx.terrain
    ctx.sessions = sessions
    try:
        yield ctx
    finally:
        app.dependency_overrides.clear()


def test_http_handler_defers_download_and_build_to_background(job_context):
    ctx = job_context
    background = BackgroundTasks()
    job = terrain_api.acquire_terrain(ctx.plan.request, background, session=None, jobs=ctx.jobs)
    assert job.status == "QUEUED" and len(background.tasks) == 1
    assert ctx.calls == [] and ctx.sessions == [] and ctx.vault.objects == {}
    asyncio.run(background())
    finished = ctx.jobs.get(job.job_id)
    assert finished.status == "SUCCEEDED" and len(ctx.sessions) == 1 and len(ctx.calls) == 1
    assert finished.result.result.terrain.readiness_status.value == "VISUAL_READY"
    assert not ctx.terrain.readiness(city_id="kolkata").completion_gate_passed


def test_api_plan_acquire_poll_and_retry(job_context):
    ctx = job_context
    client = TestClient(app)
    plan = client.get("/terrain/acquisition/plan?city_id=kolkata&ward_id=7")
    assert plan.status_code == 200 and plan.json()["tile"] == "N22E088"
    assert ctx.calls == [] and ctx.sessions == []
    response = client.post("/terrain/acquisitions", json={"city_id": "kolkata"})
    assert response.status_code == 202 and response.json()["status"] == "QUEUED"
    # TestClient waits for the response's background task before returning.
    first = client.get("/terrain/acquisitions/" + response.json()["job_id"]).json()
    assert first["status"] == "SUCCEEDED" and first["result"]["downloaded"]
    product = first["result"]["result"]["terrain"]
    assert client.get(f"/terrain/products/{product['terrain_id']}/qa").status_code == 200
    retry = client.post("/terrain/acquisitions", json={}).json()
    second = client.get("/terrain/acquisitions/" + retry["job_id"]).json()
    assert second["status"] == "SUCCEEDED" and not second["result"]["downloaded"]
    assert len(ctx.calls) == 1 and len(ctx.sessions) == 2
    missing = client.get(f"/terrain/acquisitions/{uuid4()}")
    assert missing.status_code == 404 and "restarted" in missing.json()["detail"]


def test_api_duplicate_submission_queues_one_worker(job_context, monkeypatch):
    ctx = job_context
    queued = []
    monkeypatch.setattr(terrain_api, "run_acquisition", lambda *args: queued.append(args))
    client = TestClient(app)
    first = client.post("/terrain/acquisitions", json={})
    second = client.post("/terrain/acquisitions", json={})
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"] and len(queued) == 1
    monkeypatch.setattr(terrain_api, "plan_acquisition", lambda *args, **kwargs: (
        ctx.plan.model_copy(update={"boundary_reference": "test://another-approved-pilot"})
    ))
    assert client.post("/terrain/acquisitions", json={}).status_code == 409
    assert ctx.calls == []


@pytest.mark.parametrize("failure, expected", [
    (HarvestAccessError("Automation is disabled"), 403),
    (ValueError("Pilot requires approval"), 409),
    (LookupError("Source missing"), 404),
])
def test_api_preflight_returns_actionable_failure_without_worker(job_context, monkeypatch,
                                                                failure, expected):
    ctx = job_context

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(terrain_api, "plan_acquisition", fail)
    response = TestClient(app).post("/terrain/acquisitions", json={})
    assert response.status_code == expected and response.json()["detail"] == str(failure)
    assert ctx.sessions == [] and ctx.calls == []


def test_api_rejects_custom_urls_and_invalid_geometry(job_context):
    client = TestClient(app)
    assert client.post("/terrain/acquisitions", json={
        "source_url": "http://example.invalid/arbitrary-data",
    }).status_code == 422
    assert client.post("/terrain/acquisitions", json={"cell_size_m": 0}).status_code == 422
    assert client.get("/terrain/acquisition/plan?cell_size_m=NaN").status_code == 422
    assert job_context.calls == []


@pytest.mark.parametrize("when", ["before_download", "after_download"])
def test_worker_rechecks_pilot_before_persisting(job_context, monkeypatch, when):
    ctx = job_context
    checks = []

    def changing_plan(*args, **kwargs):
        checks.append(True)
        if when == "before_download" or len(checks) > 1:
            raise ValueError("Pilot approval was revoked")
        return ctx.plan

    monkeypatch.setattr(job_worker, "plan_acquisition", changing_plan)
    job, _ = ctx.jobs.reserve(ctx.plan)
    job_worker.run_acquisition(job.job_id, ctx.jobs)
    failed = ctx.jobs.get(job.job_id)
    assert failed.status == "FAILED" and "revoked" in failed.stage
    assert len(ctx.calls) == (when == "after_download")
    assert ctx.vault.objects == {} and ctx.terrain.list_products() == []


def test_unexpected_worker_failure_is_reported_and_retry_is_possible(job_context, monkeypatch):
    ctx = job_context

    def fail(tile, **kwargs):
        raise ArithmeticError("internal failure")

    monkeypatch.setattr(ctx.worker, "downloader", fail)
    job, _ = ctx.jobs.reserve(ctx.plan)
    job_worker.run_acquisition(job.job_id, ctx.jobs)
    assert ctx.jobs.get(job.job_id).status == "FAILED"
    assert "check API logs" in ctx.jobs.get(job.job_id).stage
    _, created = ctx.jobs.reserve(ctx.plan)
    assert created and ctx.vault.objects == {}


def test_job_store_serializes_duplicate_requests_and_bounds_retention(acquisition_context):
    plan = acquisition_context.plan
    store = TerrainJobStore(max_jobs=2)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: store.reserve(plan), range(8)))
    assert sum(created for _, created in responses) == 1
    first = responses[0][0]
    assert len({job.job_id for job, _ in responses}) == 1
    first.stage = "mutated response"
    assert store.get(first.job_id).stage != first.stage
    with pytest.raises(AcquisitionBusyError):
        store.reserve(plan.model_copy(update={"boundary_reference": "test://different-pilot"}))
    store.update(first.job_id, status="FAILED", stage="test failure")
    second, _ = store.reserve(plan)
    store.update(second.job_id, status="FAILED", stage="test failure")
    third, created = store.reserve(plan)
    assert created and store.get(third.job_id).status == "QUEUED"
    with pytest.raises(LookupError, match="expired"):
        store.get(first.job_id)
