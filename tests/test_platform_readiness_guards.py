"""Readiness probe failures are explicit and do not expose connection secrets."""

from floodguard.common.readiness import check_dependencies


def test_every_dependency_must_pass() -> None:
    checks = check_dependencies({"database_and_schema": lambda: None, "object_store": lambda: None})
    assert all(checks.values())


def test_failure_is_reported_without_skipping_other_checks() -> None:
    calls = []

    def unavailable() -> None:
        raise OSError("connection password must not be returned")

    result = check_dependencies({"database_and_schema": unavailable,
                                 "object_store": lambda: calls.append(True)})
    assert result == {"database_and_schema": False, "object_store": True}
    assert calls == [True]
    assert "password" not in str(result)
