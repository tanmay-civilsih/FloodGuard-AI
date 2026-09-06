"""Reproducible source and installed-dependency evidence; not scientific validation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

SOURCE_DIRECTORIES = ("apps", "floodguard", "migrations", "scripts")
SOURCE_FILES = ("pyproject.toml", "requirements.lock", "Dockerfile", "docker-compose.yml",
                "alembic.ini", "agent.md",
                "docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md")


def source_fingerprint(root: Path) -> str:
    paths = [root / name for name in SOURCE_FILES]
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError("release source files are missing or symlinked")
    for name in SOURCE_DIRECTORIES:
        directory = root / name
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("release source directories are missing or symlinked")
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("release sources must not contain symlinks")
            if (path.is_file() and path.suffix in {".py", ".json"}
                and "__pycache__" not in path.parts):
                paths.append(path)
    digest = hashlib.sha256(b"floodguard-release-source-v1\0")
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("release sources must not escape their root")
        payload = path.read_bytes()
        name_bytes = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def lock_mismatches(
    lock: Path, get_version: Callable[[str], str] = version,
) -> list[str]:
    from packaging.requirements import Requirement

    mismatches = []
    for line in lock.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        requirement = Requirement(value)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        try:
            installed = get_version(requirement.name)
        except PackageNotFoundError:
            mismatches.append(f"{requirement.name}: not installed")
            continue
        if not requirement.specifier.contains(installed, prereleases=True):
            mismatches.append(
                f"{requirement.name}: installed {installed}, expected {requirement.specifier}"
            )
    return mismatches
