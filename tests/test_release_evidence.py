"""Code/lock evidence must change with source bytes and ignore private runtime data."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from floodguard.common.release_evidence import (
    SOURCE_DIRECTORIES,
    SOURCE_FILES,
    lock_mismatches,
    source_fingerprint,
)


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    for name in SOURCE_DIRECTORIES:
        (tmp_path / name).mkdir(parents=True)
    for name in SOURCE_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source\n", encoding="utf-8")
    (tmp_path / "floodguard" / "example.py").write_text("value = 1\n", encoding="utf-8")
    return tmp_path


def test_source_fingerprint_is_stable_and_changes_with_code(source_root: Path) -> None:
    first = source_fingerprint(source_root)
    assert source_fingerprint(source_root) == first
    (source_root / "floodguard" / "example.py").write_text("value = 2\n", encoding="utf-8")
    assert source_fingerprint(source_root) != first


def test_private_configuration_and_bytecode_are_not_hashed(source_root: Path) -> None:
    first = source_fingerprint(source_root)
    (source_root / ".env").write_text("PRIVATE=test\n", encoding="utf-8")
    (source_root / "floodguard" / "example.pyc").write_bytes(b"compiled")
    assert source_fingerprint(source_root) == first


def test_missing_release_sources_cannot_be_certified(source_root: Path) -> None:
    (source_root / "requirements.lock").unlink()
    with pytest.raises(ValueError, match="missing"):
        source_fingerprint(source_root)


def test_symlinked_sources_are_not_certified(source_root: Path) -> None:
    path = source_root / "floodguard" / "linked.py"
    try:
        path.symlink_to(source_root / ".env")
    except OSError:
        pytest.skip("platform does not permit symlink creation")
    with pytest.raises(ValueError, match="symlink"):
        source_fingerprint(source_root)


def test_installed_versions_are_compared_with_lock(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("numpy==2.5.2\n", encoding="utf-8")
    assert lock_mismatches(lock, lambda _: "2.5.2") == []
    assert "2.3.5" in lock_mismatches(lock, lambda _: "2.3.5")[0]


def test_inactive_environment_markers_do_not_require_distribution(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text('not-installed==1.0; python_version < "2.0"\n', encoding="utf-8")
    assert lock_mismatches(lock, lambda _: "0") == []


def test_missing_distribution_is_a_blocker(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("missing-package==1.0\n", encoding="utf-8")

    def unavailable(name: str) -> str:
        raise PackageNotFoundError(name)

    assert lock_mismatches(lock, unavailable) == ["missing-package: not installed"]
