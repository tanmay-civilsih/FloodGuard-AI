import pytest

from floodguard.contracts.jobs import JobRecord, JobState, transition_job


def test_job_lifecycle_queued_to_running_to_succeeded() -> None:
    queued = JobRecord(job_type="sequence1.test")
    running = transition_job(queued, JobState.RUNNING)
    assert running.started_at is not None
    assert running.heartbeat is not None

    succeeded = transition_job(running, JobState.SUCCEEDED)
    assert succeeded.completed_at is not None
    assert succeeded.progress == 1.0


def test_failed_transition_requires_error_code() -> None:
    running = transition_job(JobRecord(job_type="sequence1.test"), JobState.RUNNING)
    with pytest.raises(ValueError, match="requires error_code"):
        transition_job(running, JobState.FAILED)


def test_terminal_job_cannot_restart() -> None:
    running = transition_job(JobRecord(job_type="sequence1.test"), JobState.RUNNING)
    succeeded = transition_job(running, JobState.SUCCEEDED)
    with pytest.raises(ValueError, match="illegal job transition"):
        transition_job(succeeded, JobState.RUNNING)
