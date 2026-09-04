from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import pytest

from floodguard.contracts.time import utc_now
from floodguard.harvester.acquisition import (
    AcquisitionParametersRequired,
    AcquisitionPlanner,
    DownloadedObject,
    RemoteRequest,
)
from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceRead,
    SourceStatus,
)


class PlanningTransport:
    def get_json(self, url: str, *, headers: Mapping[str, str]) -> dict[str, object]:
        del headers
        assert "/api/3/action/package_show?" in url
        return {
            "success": True,
            "result": {
                "resources": [
                    {
                        "url": "https://files.example.test/wards.kml",
                        "name": "Kolkata wards",
                        "format": "KML",
                    },
                    {
                        "url": "https://files.example.test/drainage.pdf",
                        "name": "Drainage map.pdf",
                        "format": "PDF",
                    },
                ]
            },
        }

    def download(
        self,
        request: RemoteRequest,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> DownloadedObject:
        raise AssertionError("download is not used in planning tests")


def source(method: AccessMethod, endpoint: str) -> SourceRead:
    now = utc_now()
    return SourceRead(
        source_id=uuid4(),
        provider="Test",
        dataset_name="Test",
        city_id="kolkata",
        category=SourceCategory.DRAINAGE_MAP,
        endpoint=endpoint,
        access_method=method,
        format="mixed",
        licence="Open",
        redistribution_policy="Attribute",
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.COMMUNITY,
        refresh_policy="On demand",
        fallback_strategy="Last immutable version",
        status=SourceStatus.AVAILABLE,
        created_at=now,
        updated_at=now,
    )


def test_ckan_package_resources_are_discovered() -> None:
    planner = AcquisitionPlanner(PlanningTransport())
    planned = planner.plan(
        source(AccessMethod.CKAN, "https://data.example.test/dataset/kolkata-drainage")
    )
    assert len(planned) == 2
    assert planned[0].url == "https://files.example.test/wards.kml"
    assert planned[1].filename == "Drainage_map.pdf"


def test_overpass_requires_explicit_bounded_query() -> None:
    planner = AcquisitionPlanner(PlanningTransport())
    target = source(AccessMethod.OVERPASS, "https://overpass.example.test/api/interpreter")
    with pytest.raises(AcquisitionParametersRequired):
        planner.plan(target)

    planned = planner.plan(target, parameters={"query": "[out:xml];way(1,2,3,4);out;"})
    assert len(planned) == 1
    assert planned[0].method == "POST"
    assert planned[0].filename == "overpass.osm"
