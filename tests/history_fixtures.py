"""Offline history services. Geometry-adjusted provider data is a test double only."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pyproj import Transformer

from floodguard.forcing.contracts import Grid
from floodguard.forcing.service import ForcingService
from floodguard.harvester.vault import MemoryRawVault
from floodguard.history.acquire import acquire_power
from floodguard.history.contracts import EventRequest, PowerSelection
from floodguard.history.service import HistoryService
from floodguard.registry.service import RegistryService
from floodguard.twin.reference import reference_snapshot
from tests.test_harvester_service import FakeTransport
from tests.test_harvester_service import service as harvest_service
from tests.twin_fixtures import twin_service

FIXTURES = Path(__file__).parent / "fixtures" / "history"


def utc(value):
    return datetime.fromisoformat(value).astimezone(UTC)


def history_context(missing=False):
    twins, session, store = twin_service()
    twin = twins.build(reference_snapshot())
    lon, lat = Transformer.from_crs("EPSG:32645", "EPSG:4326", always_xy=True).transform(
        300050, 2500030
    )
    selection = PowerSelection(
        longitude=lon, latitude=lat, start=utc("2021-09-19T00:00Z"), end=utc("2021-09-22T00:00Z")
    )
    raw = json.loads((FIXTURES / "power-hourly.json").read_bytes())
    raw["geometry"]["coordinates"][:2] = [lon, lat]  # Explicit fixture, not Kolkata evidence.
    if missing:
        raw["properties"]["parameter"]["PRECTOTCORR"]["2021091904"] = -999
    vault = MemoryRawVault()
    transport = FakeTransport(json.dumps(raw).encode())
    harvester = harvest_service(session, transport, vault)
    version = acquire_power(RegistryService(session), harvester, selection)
    store.raw_objects.update(vault.objects)
    request = EventRequest(
        event_key="synthetic-location-contract-test",
        title="TEST DOUBLE",
        catchment_id="kolkata-sequence9-reference",
        catchment_status="STUDY_AREA",
        catchment_evidence="Synthetic twin fixture",
        selection=selection,
        dataset_version_id=version.dataset_version_id,
        raw_object_id=version.objects[0].object_id,
        twin_id=twin.twin_id,
        replay_grid=Grid(
            horizontal_crs="EPSG:32645", x_edges_m=[299990, 300110], y_edges_m=[2499990, 2500070]
        ),
        event_start=utc("2021-09-19T03:00Z"),
        event_end=utc("2021-09-19T09:00Z"),
        spatial_application_reason="Explicit test uniform regional estimate",
        evidence_gaps=["Test fixture, no flood observations."],
        infrastructure_assumptions=["Synthetic event-date infrastructure."],
    )
    return HistoryService(session, ForcingService(session, twins), harvester), request, transport
