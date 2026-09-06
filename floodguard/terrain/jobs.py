"""Bounded, single-process acquisition jobs for the local pilot API.

Progress is ephemeral. Completed terrain and source bytes remain in the database/vault.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Literal
from uuid import UUID, uuid4

from floodguard.common.config import get_settings
from floodguard.contracts.time import UtcDateTime, utc_now
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService
from floodguard.terrain.acquisition import (
    TerrainAcquisitionPlan,
    TerrainAcquisitionResult,
    plan_acquisition,
)
from floodguard.terrain.contracts import TerrainInput
from floodguard.terrain.factory import build_terrain_acquirer

JobStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
logger = logging.getLogger("floodguard.terrain.acquisition")


class TerrainAcquisitionJob(TerrainInput):
    job_id: UUID
    plan: TerrainAcquisitionPlan
    status: JobStatus
    stage: str
    created_at: UtcDateTime
    updated_at: UtcDateTime
    result: TerrainAcquisitionResult | None = None


class AcquisitionBusyError(RuntimeError):
    pass


class TerrainJobStore:
    def __init__(self, *, max_jobs: int = 32) -> None:
        if max_jobs < 1:
            raise ValueError("at least one acquisition job must be retained")
        self.max_jobs = max_jobs
        self._jobs: dict[UUID, TerrainAcquisitionJob] = {}
        self._lock = Lock()

    def reserve(self, plan: TerrainAcquisitionPlan) -> tuple[TerrainAcquisitionJob, bool]:
        with self._lock:
            for job in self._jobs.values():
                if job.status in {"QUEUED", "RUNNING"}:
                    if job.plan == plan:
                        return job.model_copy(deep=True), False
                    raise AcquisitionBusyError(
                        "Another terrain acquisition is running; retry later"
                    )
            while len(self._jobs) >= self.max_jobs:
                del self._jobs[next(iter(self._jobs))]
            now = utc_now()
            job = TerrainAcquisitionJob(
                job_id=uuid4(), plan=plan.model_copy(deep=True), status="QUEUED",
                stage="Waiting for terrain acquisition", created_at=now, updated_at=now,
            )
            self._jobs[job.job_id] = job
            return job.model_copy(deep=True), True

    def get(self, job_id: UUID) -> TerrainAcquisitionJob:
        with self._lock:
            if job_id not in self._jobs:
                raise LookupError(
                    "Acquisition progress expired or the API restarted; retry acquisition"
                )
            return self._jobs[job_id].model_copy(deep=True)

    def update(
        self, job_id: UUID, *, status: JobStatus, stage: str,
        result: TerrainAcquisitionResult | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={
                "status": status, "stage": stage, "updated_at": utc_now(), "result": result,
            }, deep=True)


def run_acquisition(job_id: UUID, jobs: TerrainJobStore) -> None:
    """Runs after the HTTP response, with its own database session."""
    plan = jobs.get(job_id).plan
    try:
        jobs.update(job_id, status="RUNNING", stage="Checking the approved pilot")
        settings = get_settings()
        with get_session_factory()() as session:
            def check_pilot() -> None:
                session.expire_all()
                current = plan_acquisition(session, plan.request, working_crs=settings.working_crs)
                if current != plan:
                    raise ValueError("The approved pilot changed during acquisition; retry")

            check_pilot()
            result = build_terrain_acquirer(session).acquire(
                RegistryService(session).get_source(plan.source_id), plan,
                check_pilot=check_pilot,
                progress=lambda stage: jobs.update(job_id, status="RUNNING", stage=stage),
            )
        jobs.update(job_id, status="SUCCEEDED", stage="Terrain is available for QA", result=result)
    except (ValueError, RuntimeError, LookupError, OSError) as exc:
        jobs.update(job_id, status="FAILED", stage=str(exc)[:500])
    except Exception:
        logger.exception("Terrain acquisition job %s failed", job_id)
        jobs.update(
            job_id, status="FAILED", stage="Acquisition failed; check API logs and retry",
        )
