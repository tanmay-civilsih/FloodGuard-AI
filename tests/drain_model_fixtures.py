"""Synthetic source documents for importer tests; never real-pilot acceptance evidence."""

from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from floodguard.drainage.contracts import VersionedSourceReference
from floodguard.drainage.model_contracts import (
    DrainModelInput,
    EdgeSourceBinding,
    ImportBindingPlan,
    ImportSourceInfo,
    NodeSourceBinding,
)
from floodguard.drainage.reference import reference_model
from floodguard.drainage.repository import DrainRepository
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.drainage.service import DrainService
from floodguard.registry.models import Base
from floodguard.spatial.object_store import MemorySpatialObjectStore

RECONSTRUCTION_ID = UUID("2c3af935-2f77-4fa4-8f3e-b23153cf5fab")
WARD_ID = UUID("34fb21cb-ce3d-4211-bc52-b8c755654b9b")


def sources() -> tuple[ImportSourceInfo, bytes, bytes, DrainModelInput]:
    model = reference_model()
    graph = model.graph
    features = [
        {
            "type": "Feature",
            "id": edge.drain_edge_id,
            "geometry": edge.geometry,
            "properties": {
                "feature_kind": "DRAIN",
                "dimension_m": None,
                "reconstruction_id": str(RECONSTRUCTION_ID),
            },
        }
        for edge in graph.edges
    ]
    features += [
        {
            "type": "Feature",
            "id": node.drain_node_id,
            "geometry": node.geometry,
            "properties": {
                "feature_kind": "STRUCTURE",
                "reconstruction_id": str(RECONSTRUCTION_ID),
            },
        }
        for node in graph.nodes
    ]
    features += [
        {
            "type": "Feature",
            "id": "label",
            "geometry": graph.nodes[0].geometry,
            "properties": {
                "feature_kind": "LABEL",
                "raw_text": "IVL=5M",
                "reconstruction_id": str(RECONSTRUCTION_ID),
            },
        }
    ]
    reconstruction = canonical_bytes(
        {
            "type": "FeatureCollection",
            "crs": {"properties": {"name": graph.working_crs}},
            "features": features,
        }
    )
    wards = canonical_bytes(
        {
            "type": "FeatureCollection",
            "floodguard_crs": graph.working_crs,
            "features": [
                {"type": "Feature", "geometry": w.geometry, "properties": {"WARD": w.ward_id}}
                for w in model.wards.boundaries
            ],
        }
    )
    info = ImportSourceInfo(
        city_id=graph.city_id,
        pilot_area_id=graph.pilot_area_id,
        working_crs=graph.working_crs,
        reconstruction_id=RECONSTRUCTION_ID,
        normalization_id=WARD_ID,
        reconstruction_source=VersionedSourceReference(
            source_reference="test://reconstruction",
            version=str(RECONSTRUCTION_ID),
            sha256=sha256(reconstruction),
        ),
        ward_source=VersionedSourceReference(
            source_reference="test://wards", version=str(WARD_ID), sha256=sha256(wards)
        ),
        evidence_scope=graph.evidence_scope,
    )
    model.wards.source = info.ward_source
    model.graph.source_references += [info.reconstruction_source, info.ward_source]
    return info, reconstruction, wards, model


def binding(model: DrainModelInput, draft_id: UUID, fingerprint: str) -> ImportBindingPlan:
    return ImportBindingPlan(
        draft_id=draft_id,
        draft_fingerprint=fingerprint,
        graph=model.graph,
        definitions=model.definitions,
        node_bindings=[
            NodeSourceBinding(
                drain_node_id=n.drain_node_id, source_feature_id=n.drain_node_id, location="POINT"
            )
            for n in model.graph.nodes
        ],
        edge_bindings=[
            EdgeSourceBinding(drain_edge_id=e.drain_edge_id, source_feature_ids=[e.drain_edge_id])
            for e in model.graph.edges
        ],
    )


def service_fixture() -> tuple[DrainService, Session, MemorySpatialObjectStore]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    store = MemorySpatialObjectStore()
    return (DrainService(DrainRepository(session), store, working_crs="EPSG:32645"), session, store)
