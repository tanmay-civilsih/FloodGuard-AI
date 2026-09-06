"""Hash-bound reconstruction import and explicit graph binding; no automatic inference."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from floodguard.common.integrity import verified_payload
from floodguard.drainage.assessment import shape
from floodguard.drainage.contracts import DrainGraphPackage
from floodguard.drainage.model_contracts import (
    DrainImportDraft,
    DrainModelInput,
    ImportBindingPlan,
    ImportFeature,
    ImportSourceInfo,
    WardBoundary,
    WardBoundarySet,
)
from floodguard.drainage.serialization import decode_object
from floodguard.spatial.geometry_validation import validate_geometry


def import_sources(
    info: ImportSourceInfo,
    reconstruction_bytes: bytes,
    ward_bytes: bytes,
    *,
    max_bytes: int,
) -> tuple[DrainImportDraft, WardBoundarySet]:
    for payload, source in (
        (reconstruction_bytes, info.reconstruction_source),
        (ward_bytes, info.ward_source),
    ):
        verified_payload(payload, expected_sha256=source.sha256, max_bytes=max_bytes)
    reconstruction = decode_object(reconstruction_bytes, max_bytes)
    ward_document = decode_object(ward_bytes, max_bytes)
    reconstruction_crs = reconstruction.get("crs", {}).get("properties", {}).get("name")
    if (
        reconstruction_crs != info.working_crs
        or ward_document.get("floodguard_crs") != info.working_crs
    ):
        raise ValueError("source geometry CRS differs from the import working CRS")
    boundaries = []
    for feature in _features(ward_document):
        properties = feature.get("properties", {})
        ward_id = properties.get("WARD")
        if not isinstance(ward_id, str) or not ward_id.strip():
            raise ValueError("normalized ward feature requires an explicit WARD identifier")
        boundaries.append(WardBoundary(ward_id=ward_id, geometry=feature["geometry"]))
    wards = WardBoundarySet(
        working_crs=info.working_crs,
        evidence_scope=info.evidence_scope,
        source=info.ward_source,
        boundaries=boundaries,
    )
    ward_shapes = [(ward.ward_id, shape(ward.geometry)) for ward in wards.boundaries]
    features = []
    seen: set[str] = set()
    for feature in _features(reconstruction):
        properties = feature.get("properties", {})
        feature_id = feature.get("id")
        if not isinstance(feature_id, str) or not feature_id or feature_id in seen:
            raise ValueError("reconstruction features require unique explicit string IDs")
        seen.add(feature_id)
        if properties.get("reconstruction_id") != str(info.reconstruction_id):
            raise ValueError(
                "reconstruction feature lineage differs from the selected reconstruction"
            )
        kind = properties.get("feature_kind")
        if kind not in {"DRAIN", "STRUCTURE", "LABEL"}:
            raise ValueError("unsupported reconstruction feature kind")
        geometry = feature["geometry"]
        validate_geometry(geometry, geographic=False)
        expected_kind = "LineString" if kind == "DRAIN" else "Point"
        if geometry.get("type") != expected_kind:
            raise ValueError("source feature kind and geometry disagree")
        current_shape = shape(geometry)
        features.append(
            ImportFeature(
                source_feature_id=feature_id,
                feature_kind=kind,
                geometry=geometry,
                source_properties=properties,
                intersecting_ward_ids=sorted(
                    ward for ward, polygon in ward_shapes if polygon.intersects(current_shape)
                ),
            )
        )
    if not any(item.feature_kind == "DRAIN" for item in features):
        raise ValueError("reconstruction has no drain features")
    unresolved = [
        "Drain connectivity and nominal direction require an explicit source-bound binding plan.",
        "Candidate structures and source labels are not accepted hydraulic node/parameter values.",
        "Outfall, cross-ward continuation and physical exchange coverage require evidence.",
        "Missing engineering values remain unassigned; source bytes are retained unchanged.",
    ]
    outside = sum(not item.intersecting_ward_ids for item in features)
    if outside:
        unresolved.append(f"{outside} reconstruction features do not intersect any source ward.")
    return DrainImportDraft(source_info=info, features=features, unresolved_items=unresolved), wards


def _features(document: dict[str, Any]) -> list[dict[str, Any]]:
    value = document.get("features")
    if document.get("type") != "FeatureCollection" or not isinstance(value, list) or not value:
        raise ValueError("source must be a nonempty FeatureCollection")
    if any(not isinstance(item, dict) or item.get("type") != "Feature" for item in value):
        raise ValueError("invalid source feature")
    return value


def bind_graph(
    draft: DrainImportDraft,
    wards: WardBoundarySet,
    plan: ImportBindingPlan,
) -> DrainModelInput:
    graph = DrainGraphPackage.model_validate(plan.graph.model_dump(mode="json"))
    info = draft.source_info
    if (graph.city_id, graph.pilot_area_id, graph.working_crs, graph.evidence_scope) != (
        info.city_id,
        info.pilot_area_id,
        info.working_crs,
        info.evidence_scope,
    ):
        raise ValueError("binding graph identity differs from its import draft")
    if any(
        source not in graph.source_references
        for source in (info.reconstruction_source, info.ward_source)
    ):
        raise ValueError("binding graph must retain exact reconstruction and ward source lineage")
    features = {item.source_feature_id: item for item in draft.features}
    nodes = {item.drain_node_id: item for item in graph.nodes}
    edges = {item.drain_edge_id: item for item in graph.edges}
    node_ids = [item.drain_node_id for item in plan.node_bindings]
    edge_ids = [item.drain_edge_id for item in plan.edge_bindings]
    if len(set(node_ids)) != len(node_ids) or set(node_ids) != set(nodes):
        raise ValueError("every graph node requires exactly one source binding")
    if len(set(edge_ids)) != len(edge_ids) or set(edge_ids) != set(edges):
        raise ValueError("every graph edge requires exactly one source binding")
    tolerance = graph.endpoint_tolerance_m
    for binding in plan.node_bindings:
        source = features.get(binding.source_feature_id)
        if source is None or source.feature_kind == "LABEL":
            raise ValueError("node binding must reference source drain/structure geometry")
        geometry = source.geometry
        if binding.location == "POINT":
            if geometry["type"] != "Point":
                raise ValueError("POINT node binding requires a source point")
            target = shape(geometry)
        elif geometry["type"] != "LineString":
            raise ValueError("line node binding requires a source drain")
        elif binding.location == "ON_LINE":
            target = shape(geometry)
        else:
            index = 0 if binding.location == "START" else -1
            target = shape({"type": "Point", "coordinates": geometry["coordinates"][index]})
        if target.distance(shape(nodes[binding.drain_node_id].geometry)) > tolerance:
            raise ValueError("node geometry moved beyond the source-binding tolerance")
    for edge_binding in plan.edge_bindings:
        selected = [features.get(item) for item in edge_binding.source_feature_ids]
        if any(item is None or item.feature_kind != "DRAIN" for item in selected):
            raise ValueError("edge binding must reference source drain geometry")
        lines = [shape(item.geometry) for item in selected if item is not None]
        union = import_module("shapely.ops").unary_union(lines)
        line = shape(edges[edge_binding.drain_edge_id].geometry)
        if not union.buffer(tolerance).covers(line):
            raise ValueError("edge geometry is not covered by its source drain linework")
        if line.length <= tolerance or not line.is_simple:
            raise ValueError("bound edge geometry must be nondegenerate and simple")
    # A subset is permitted; the persisted binding coverage must disclose unbound candidates.
    return DrainModelInput(graph=graph, wards=wards, definitions=plan.definitions)
