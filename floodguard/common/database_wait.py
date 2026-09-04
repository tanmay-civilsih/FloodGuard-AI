"""Bounded database readiness wait used during service startup."""

from __future__ import annotations

import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from floodguard.common.config import get_settings


def wait_for_database(
    database_url: str,
    *,
    attempts: int = 30,
    delay_seconds: float = 2.0,
) -> None:
    """Wait until the configured database accepts a simple query.

    The retry is deliberately bounded so container startup cannot hang forever.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be non-negative")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        for attempt in range(1, attempts + 1):
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                print(f"database ready after attempt {attempt}/{attempts}")
                return
            except OperationalError as exc:
                if attempt == attempts:
                    raise SystemExit(
                        f"database unavailable after {attempts} attempts"
                    ) from exc
                print(
                    f"database not ready (attempt {attempt}/{attempts}); "
                    f"retrying in {delay_seconds:g}s"
                )
                time.sleep(delay_seconds)
    finally:
        engine.dispose()


def main() -> None:
    settings = get_settings()
    wait_for_database(settings.database_url)


if __name__ == "__main__":
    main()
