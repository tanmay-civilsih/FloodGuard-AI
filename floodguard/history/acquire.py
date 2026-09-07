"""Explicit bounded POWER acquisition with governed reuse and whole-response retry."""

import time

from floodguard.harvester.acquisition import AcquisitionError
from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus
from floodguard.harvester.service import HarvesterService
from floodguard.history.contracts import PowerSelection
from floodguard.history.power import source_definition
from floodguard.registry.service import RegistryService, SourceNotFoundError


def acquire_power(
    registry: RegistryService,
    harvester: HarvesterService,
    selection: PowerSelection,
    city_id: str = "kolkata",
    *,
    refresh: bool = False,
) -> DatasetVersionRead:
    definition = source_definition(selection, city_id)
    try:
        source = registry.get_source(definition.source_id)
    except SourceNotFoundError:
        source = registry.create_source(definition)
    # Preserve current operator policy, including revocation. Never overwrite it to enable access.
    harvester._enforce_governance(source, include_authorized=False)
    if source.endpoint != definition.endpoint:
        raise ValueError("registered endpoint differs from exact POWER selection")
    if not refresh:
        for version in harvester.list_source_versions(source.source_id):
            if version.status is DatasetVersionStatus.COMPLETE:
                return version
    for attempt in range(3):
        try:
            result = harvester.harvest_source(source)
            if result.dataset_version_id is None:
                raise ValueError("acquisition did not retain a dataset version")
            return harvester.get_version(result.dataset_version_id)
        except AcquisitionError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable retry state")
