"""Dependency readiness is separate from data completeness and engineering validation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def check_dependencies(probes: dict[str, Callable[[], None]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name, probe in probes.items():
        try:
            probe()
        except Exception:
            # Never return connection strings, passwords or signed URLs to HTTP clients.
            checks[name] = False
        else:
            checks[name] = True
    return checks


def _database_and_schema() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.pool import NullPool

    from floodguard.common.config import get_settings

    url = make_url(get_settings().database_url)
    connect_args: dict[str, object] = {}
    if url.drivername.startswith("postgresql"):
        connect_args = {"connect_timeout": 2, "options": "-c statement_timeout=2000"}
    engine = create_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
            actual = set(rows)
        root = Path(__file__).resolve().parents[2]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))
        expected = set(ScriptDirectory.from_config(config).get_heads())
        if not expected or actual != expected:
            raise RuntimeError("database schema is not at the installed application heads")
    finally:
        engine.dispose()


def _object_store() -> None:
    from minio import Minio
    from urllib3 import PoolManager, Timeout

    from floodguard.common.config import get_settings

    settings = get_settings()
    pool = PoolManager(timeout=Timeout(connect=2, read=2), retries=False)
    try:
        client = Minio(
            settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key,
            secure=settings.object_store_secure,
            http_client=pool,
        )
        # Missing buckets are allowed before bootstrap. The authenticated requests
        # must succeed; data completeness remains the domain readiness endpoints' job.
        client.bucket_exists(settings.raw_bucket)
        client.bucket_exists(settings.spatial_bucket)
    finally:
        pool.clear()


def platform_readiness() -> dict[str, bool]:
    return check_dependencies({"database_and_schema": _database_and_schema,
                               "object_store": _object_store})
