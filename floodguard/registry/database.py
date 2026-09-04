"""Database session wiring owned by the registry domain."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from floodguard.common.config import get_settings


def build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    engine = build_engine(get_settings().database_url)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
