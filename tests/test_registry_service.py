from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.registry.models import Base
from floodguard.registry.repository import RegistryRepository
from floodguard.registry.seed import PROTOTYPE_REQUIRED_CATEGORIES, kolkata_seed_sources
from floodguard.registry.service import RegistryService


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seed_is_idempotent_and_catalogue_complete() -> None:
    session = make_session()
    repository = RegistryRepository(session)
    seeds = kolkata_seed_sources()

    assert repository.seed_if_missing(seeds) == len(seeds)
    assert repository.seed_if_missing(seeds) == 0

    readiness = RegistryService(session).readiness()
    assert readiness.catalogue_complete
    assert set(readiness.required_categories) == set(PROTOTYPE_REQUIRED_CATEGORIES)
    assert readiness.missing_categories == []


def test_every_seed_documents_access_and_fallback_strategy() -> None:
    source_ids = {source.source_id for source in kolkata_seed_sources()}
    for source in kolkata_seed_sources():
        assert source.licence.strip()
        assert source.redistribution_policy.strip()
        assert source.fallback_strategy.strip()
        assert source.endpoint.startswith("https://")
        if source.fallback_source_id is not None:
            assert source.fallback_source_id in source_ids
