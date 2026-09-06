"""Read existing domain metadata and immutable bytes for a bounded pilot import."""

from uuid import UUID

from floodguard.common.integrity import verified_payload
from floodguard.drainage.contracts import DrainEvidenceScope, VersionedSourceReference
from floodguard.drainage.model_contracts import ImportSourceInfo
from floodguard.reconstruction.contracts import ReconstructionStatus
from floodguard.reconstruction.service import ReconstructionService
from floodguard.spatial.service import SpatialService


def load_pilot_sources(
    reconstruction: ReconstructionService,
    spatial: SpatialService,
    *,
    city_id: str,
    ward_id: str,
    max_bytes: int,
    reconstruction_id: UUID | None = None,
    normalization_id: UUID | None = None,
) -> tuple[ImportSourceInfo, bytes, bytes]:
    maps = [
        item
        for item in reconstruction.list_reconstructions(city_id=city_id)
        if item.ward_id == ward_id
        and item.status is ReconstructionStatus.APPROVED
        and (reconstruction_id is None or item.reconstruction_id == reconstruction_id)
    ]
    if not maps:
        raise ValueError("No approved reconstruction is available for this exact city/ward.")
    selected = maps[0]
    # Verify every predecessor reconstruction artifact and raw PDF before accepting its lineage.
    for key, digest, raw in (
        (selected.source_object_key, selected.source_sha256, True),
        (selected.working_object_key, selected.working_sha256, False),
        (selected.qa_object_key, selected.qa_sha256, False),
        (selected.audit_object_key, selected.audit_sha256, False),
    ):
        payload = (
            reconstruction.object_store.read_raw(key)
            if raw
            else reconstruction.object_store.read_spatial(key)
        )
        verified_payload(payload, expected_sha256=digest, max_bytes=max_bytes)
    layers = [
        item
        for item in spatial.list_layers(city_id=city_id)
        if item.source_category == "WARD_BOUNDARY"
        and item.working_crs == selected.working_crs
        and (normalization_id is None or item.normalization_id == normalization_id)
    ]
    for layer in layers:
        try:
            spatial.qa_geojson(layer.normalization_id)
        except (ValueError, RuntimeError, FileNotFoundError):
            continue
        working = spatial.object_store.read_spatial(layer.normalized_object_key)
        verified_payload(working, expected_sha256=layer.normalized_sha256, max_bytes=max_bytes)
        return (
            ImportSourceInfo(
                city_id=city_id,
                pilot_area_id=f"{city_id}-ward-{ward_id}",
                working_crs=selected.working_crs,
                reconstruction_id=selected.reconstruction_id,
                normalization_id=layer.normalization_id,
                reconstruction_source=VersionedSourceReference(
                    source_reference=selected.working_object_key,
                    version=str(selected.reconstruction_id),
                    sha256=selected.working_sha256,
                ),
                ward_source=VersionedSourceReference(
                    source_reference=layer.normalized_object_key,
                    version=str(layer.normalization_id),
                    sha256=layer.normalized_sha256,
                ),
                evidence_scope=DrainEvidenceScope.REAL_PILOT_PROVISIONAL,
            ),
            reconstruction.object_store.read_spatial(selected.working_object_key),
            working,
        )
    raise ValueError("No current, integrity-verified normalized ward layer is available.")
