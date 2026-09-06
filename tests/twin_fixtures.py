"""Controlled, source-independent twin test services."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore
from floodguard.twin.repository import TwinRepository
from floodguard.twin.service import TwinService


def bound_fixture_snapshot():
    """Synthetic source doubles exercise provisional-real binding paths; never deployed evidence."""
    import json
    from uuid import uuid4

    from floodguard.drainage.contracts import DrainEvidenceScope, VersionedSourceReference
    from floodguard.drainage.importer import import_sources
    from floodguard.drainage.model_contracts import DrainModelInput, ImportSourceInfo
    from floodguard.drainage.serialization import canonical_bytes, sha256
    from floodguard.twin.contracts import ComponentRole as R
    from floodguard.twin.reference import reference_snapshot
    from floodguard.twin.snapshot import assemble_parameters
    from tests.drain_model_fixtures import binding

    snapshot = reference_snapshot()
    scope = DrainEvidenceScope.REAL_PILOT_PROVISIONAL
    snapshot.evidence_scope = scope
    for source in snapshot.sources.values():
        source.evidence_scope = scope
    model = DrainModelInput.model_validate(json.loads(snapshot.evidence["drain-input"])["model"])
    model.graph.evidence_scope = scope
    model.wards.evidence_scope = scope
    model.definitions.outfalls[0].destination_kind = "DRAIN_NETWORK"
    recon_id = uuid4()
    features = [
        {
            "type": "Feature",
            "id": edge.drain_edge_id,
            "geometry": edge.geometry,
            "properties": {"feature_kind": "DRAIN", "reconstruction_id": str(recon_id)},
        }
        for edge in model.graph.edges
    ]
    features += [
        {
            "type": "Feature",
            "id": node.drain_node_id,
            "geometry": node.geometry,
            "properties": {"feature_kind": "STRUCTURE", "reconstruction_id": str(recon_id)},
        }
        for node in model.graph.nodes
    ]
    raw = canonical_bytes(
        {
            "type": "FeatureCollection",
            "crs": {"properties": {"name": "EPSG:32645"}},
            "features": features,
        }
    )
    info = ImportSourceInfo(
        city_id=snapshot.city_id,
        pilot_area_id=snapshot.pilot_area.pilot_area_id,
        working_crs=snapshot.horizontal_crs,
        reconstruction_id=recon_id,
        normalization_id=uuid4(),
        reconstruction_source=VersionedSourceReference(
            source_reference="test://explicit-linework", version=str(recon_id), sha256=sha256(raw)
        ),
        ward_source=model.wards.source,
        evidence_scope=scope,
    )
    model.graph.source_references.append(info.reconstruction_source)
    draft, _ = import_sources(info, raw, snapshot.components[R.WARD], max_bytes=1000000)
    plan = binding(model, uuid4(), "a" * 64)
    snapshot.evidence["drain-input"] = canonical_bytes(
        {"model": model.model_dump(mode="json"), "binding_plan": plan.model_dump(mode="json")}
    )
    snapshot.evidence["drain-draft"] = canonical_bytes(draft.model_dump(mode="json"))
    snapshot.evidence["drain-source-reconstruction"] = raw
    snapshot.evidence["drain-source-wards"] = snapshot.components[R.WARD]
    parameters = json.loads(snapshot.evidence["drain-parameters"])
    parameters["definitions"] = model.definitions.model_dump(mode="json")
    snapshot.evidence["drain-parameters"] = canonical_bytes(parameters)
    snapshot.add(
        R.DRAIN_GRAPH,
        canonical_bytes(model.graph.model_dump(mode="json")),
        snapshot.sources[R.DRAIN_GRAPH],
    )
    assemble_parameters(snapshot)
    return snapshot


def twin_service(store=None):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    storage = store if store is not None else MemorySpatialObjectStore()
    return (
        TwinService(
            TwinRepository(session),
            storage,
            working_crs="EPSG:32645",
            software_version="0.9.0",
            software_source_sha256="a" * 64,
        ),
        session,
        storage,
    )
