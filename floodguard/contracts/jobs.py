"""Canonical asynchronous job contract and lifecycle rules."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from floodguard.contracts.time import UtcDateTime, utc_now


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobRecord(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    job_type: str = Field(min_length=1)
    state: JobState = JobState.QUEUED
    created_at: UtcDateTime = Field(default_factory=utc_now)
    started_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    correlation_id: UUID = Field(default_factory=uuid4)
    heartbeat: UtcDateTime | None = None
    retry_count: int = Field(default=0, ge=0)
    resource_requirement: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "JobRecord":
        terminal = self.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
        if self.state is JobState.RUNNING and self.started_at is None:
            raise ValueError("RUNNING jobs require started_at")
        if terminal and self.completed_at is None:
            raise ValueError("terminal jobs require completed_at")
        if self.state is JobState.SUCCEEDED and self.progress != 1.0:
            raise ValueError("SUCCEEDED jobs require progress=1.0")
        if self.state is JobState.FAILED and not self.error_code:
            raise ValueError("FAILED jobs require error_code")
        return self


def transition_job(
    record: JobRecord,
    state: JobState,
    *,
    now: datetime | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> JobRecord:
    """Return a new validated record after an allowed lifecycle transition."""
    allowed: dict[JobState, set[JobState]] = {
        JobState.QUEUED: {JobState.RUNNING, JobState.CANCELLED},
        JobState.RUNNING: {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED},
        JobState.SUCCEEDED: set(),
        JobState.FAILED: set(),
        JobState.CANCELLED: set(),
    }
    if state not in allowed[record.state]:
        raise ValueError(f"illegal job transition: {record.state} -> {state}")
    if state is JobState.FAILED and not error_code:
        raise ValueError("FAILED transition requires error_code")

    timestamp = now or utc_now()
    updates: dict[str, object] = {"state": state}
    if state is JobState.RUNNING:
        updates.update(started_at=timestamp, heartbeat=timestamp)
    if state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
        updates["completed_at"] = timestamp
    if state is JobState.SUCCEEDED:
        updates["progress"] = 1.0
    if state is JobState.FAILED:
        updates.update(error_code=error_code, error_message=error_message)

    data = record.model_dump()
    data.update(updates)
    return JobRecord.model_validate(data)
