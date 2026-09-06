"""Select the latest recorded and approved reconstruction for a terrain pilot."""

from floodguard.reconstruction.contracts import DrainageReconstructionRead, ReconstructionStatus


def select_pilot(
    records: list[DrainageReconstructionRead], city_id: str, ward_id: str, working_crs: str
) -> DrainageReconstructionRead:
    candidates = [item for item in records if item.city_id == city_id and item.ward_id == ward_id]
    if not candidates:
        raise ValueError("no reconstruction exists for this pilot ward")
    latest = max(candidates, key=lambda item: (item.created_at, str(item.reconstruction_id)))
    if latest.status is not ReconstructionStatus.APPROVED:
        raise ValueError("the latest pilot reconstruction requires recorded human QA approval")
    if latest.working_crs != working_crs:
        raise ValueError("pilot reconstruction does not use the configured working CRS")
    return latest
