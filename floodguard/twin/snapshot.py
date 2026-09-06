"""Snapshot validation and conservative readiness, independent of live source services."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

from floodguard.drainage.assessment import assess, shape
from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.importer import bind_graph, import_sources
from floodguard.drainage.model_contracts import DrainModelInput, ImportBindingPlan
from floodguard.drainage.serialization import canonical_bytes, decode_object, sha256
from floodguard.spatial.geometry_validation import validate_geometry
from floodguard.terrain.contracts import TerrainGrid
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.contracts import PilotArea, SourceVersion
from floodguard.urban_gis.contracts import HydraulicFeature, RoofRunoffRule, VisualFeature


@dataclass
class Snapshot:
    city_id: str
    pilot_area: PilotArea
    horizontal_crs: str
    evidence_scope: DrainEvidenceScope
    components: dict[R, bytes] = field(default_factory=dict)
    sources: dict[R, SourceVersion] = field(default_factory=dict)
    missing: dict[R, str] = field(default_factory=dict)
    evidence: dict[str, bytes] = field(default_factory=dict)

    def add(self, role: R, payload: bytes, source: SourceVersion) -> None:
        self.components[role] = payload
        self.sources[role] = source.model_copy(update={"source_sha256": sha256(payload)})


def object_data(payload: bytes) -> dict[str, Any]:
    return decode_object(payload, 128 * 1024 * 1024)


def assemble_parameters(snapshot: Snapshot) -> None:
    """One parameter identity covers drain definitions and surface hydrology policies."""
    if (
        "drain-parameters" not in snapshot.evidence
        or R.HYDRAULIC_SURFACE not in snapshot.components
    ):
        snapshot.missing[R.PARAMETERS] = (
            "Both drainage parameters and surface policies are required."
        )
        return
    surface = object_data(snapshot.components[R.HYDRAULIC_SURFACE])
    payload = canonical_bytes(
        {
            "drainage": object_data(snapshot.evidence["drain-parameters"]),
            "surface_hydrology": [
                {"feature_id": f["id"], "hydrology": f["properties"].get("hydrology")}
                for f in surface["features"]
            ],
            "drain_source": snapshot.sources[R.DRAIN_GRAPH].model_dump(mode="json"),
            "surface_source": snapshot.sources[R.HYDRAULIC_SURFACE].model_dump(mode="json"),
        }
    )
    snapshot.add(
        R.PARAMETERS,
        payload,
        SourceVersion(
            domain="ASSEMBLY",
            product_id=sha256(payload),
            pipeline_version="sequence-9-parameters-v1",
            evidence_scope=snapshot.evidence_scope,
            source_sha256=sha256(payload),
        ),
    )


def evaluate(snapshot: Snapshot) -> tuple[list[str], bool, bool]:
    """Return scenario blockers, compatible vertical frame, and real cross-ward evidence."""
    if set(snapshot.components) | set(snapshot.missing) != set(R):
        raise ValueError("every manifest component must have an explicit state")
    if set(snapshot.components) & set(snapshot.missing) or set(snapshot.sources) != set(
        snapshot.components
    ):
        raise ValueError("component state/source identities are inconsistent")
    data = {role: object_data(payload) for role, payload in snapshot.components.items()}
    for role, source in snapshot.sources.items():
        if source.evidence_scope is not snapshot.evidence_scope:
            raise ValueError("reference and real source scopes cannot be mixed")
        if source.source_sha256 != sha256(snapshot.components[role]):
            raise ValueError("component bytes differ from their selected source")
    for group in (
        (R.VISUAL_TERRAIN, R.HYDRAULIC_TERRAIN),
        (R.VISUAL_CITY, R.HYDRAULIC_SURFACE, R.ROOF_RUNOFF),
        (R.DRAIN_GRAPH, R.EXCHANGE, R.PUMP),
    ):
        identities = {snapshot.sources[r].product_id for r in group if r in snapshot.sources}
        if len(identities) > 1:
            raise ValueError("related components must use the same source product version")
    blockers = [f"{role.value}: {reason}" for role, reason in sorted(snapshot.missing.items())]
    pilot = shape(snapshot.pilot_area.geometry)
    compatible = False
    real_cross = False
    terrain: dict[str, Any] | None = None
    for role in (R.VISUAL_TERRAIN, R.HYDRAULIC_TERRAIN):
        if role not in data:
            continue
        terrain = data[role]
        grid = TerrainGrid.model_validate(terrain["grid"])
        if grid.crs != snapshot.horizontal_crs:
            raise ValueError("terrain and twin CRS differ")
        box = import_module("shapely.geometry").box(*grid.bounds)
        if not box.covers(pilot):
            blockers.append(f"{role.value} does not cover the pilot area.")
        if any(value is None for row in grid.elevations_m for value in row):
            blockers.append(f"{role.value} contains nodata; hydraulic coverage is incomplete.")
    if terrain is not None:
        metadata = object_data(snapshot.evidence["terrain-metadata"])
        if R.VISUAL_TERRAIN in data and R.HYDRAULIC_TERRAIN in data:
            visual_frame = {
                k: v for k, v in data[R.VISUAL_TERRAIN].items() if k not in {"grid", "product"}
            }
            hydraulic_frame = {
                k: v for k, v in data[R.HYDRAULIC_TERRAIN].items() if k not in {"grid", "product"}
            }
            if visual_frame != hydraulic_frame:
                raise ValueError("visual and hydraulic terrain must retain the same source frame")
        if metadata["readiness_status"] not in {"HYDRAULIC_SCENARIO_READY", "HYDRAULIC_VALIDATED"}:
            blockers.append("Selected terrain is not scenario-ready.")

    wards: dict[str, Any] = {}
    for role in (R.WARD, R.CATCHMENT, R.WATERBODY):
        if role not in data:
            continue
        collection = data[role]
        if collection.get("type") != "FeatureCollection" or not collection.get("features"):
            raise ValueError("spatial twin components require nonempty FeatureCollections")
        if collection.get("floodguard_crs") != snapshot.horizontal_crs:
            raise ValueError("spatial component CRS differs from twin")
        for feature in collection["features"]:
            validate_geometry(feature["geometry"], geographic=False)
            if role is R.WARD:
                ward_id = feature["properties"].get("WARD")
                if not isinstance(ward_id, str) or ward_id in wards:
                    raise ValueError("ward component requires unique named wards")
                wards[ward_id] = shape(feature["geometry"])
        if role is R.CATCHMENT:
            catchments = import_module("shapely.ops").unary_union(
                [shape(f["geometry"]) for f in collection["features"]]
            )
            if not catchments.covers(pilot):
                blockers.append("Selected catchment geometry does not cover the pilot.")
    if any(w not in wards for w in snapshot.pilot_area.ward_ids):
        raise ValueError("pilot references an absent ward")
    selected_wards = import_module("shapely.ops").unary_union(
        [wards[w] for w in snapshot.pilot_area.ward_ids]
    )
    if not selected_wards.covers(pilot):
        blockers.append("Pilot geometry extends beyond its selected wards.")

    model = None
    if R.DRAIN_GRAPH in data:
        model = DrainModelInput.model_validate(
            object_data(snapshot.evidence["drain-input"])["model"]
        )
        parameters = object_data(snapshot.evidence["drain-parameters"])
        expected_parameters = {
            "nodes": [
                {
                    "drain_node_id": n.drain_node_id,
                    "invert_elevation": n.invert_elevation.model_dump(mode="json"),
                    "storage_volume": n.storage_volume.model_dump(mode="json"),
                }
                for n in model.graph.nodes
            ],
            "edges": [
                {
                    "drain_edge_id": e.drain_edge_id,
                    "parameters": e.parameters.model_dump(mode="json"),
                }
                for e in model.graph.edges
            ],
            "definitions": model.definitions.model_dump(mode="json"),
        }
        if parameters != expected_parameters:
            raise ValueError("drain parameter artifact differs from graph and static definitions")
        if model.graph.model_dump(mode="json") != data[R.DRAIN_GRAPH]:
            raise ValueError("drain graph differs from its frozen source input")
        if (
            model.graph.city_id != snapshot.city_id
            or model.graph.pilot_area_id != snapshot.pilot_area.pilot_area_id
            or model.graph.working_crs != snapshot.horizontal_crs
            or model.graph.evidence_scope is not snapshot.evidence_scope
        ):
            raise ValueError("drain graph city/pilot/CRS/scope differs from twin")
        if model.wards.source.sha256 != snapshot.sources[R.WARD].source_sha256:
            raise ValueError("twin ward version differs from the drain graph's exact ward source")
        if data.get(R.EXCHANGE, {}).get("exchanges") != [
            e.model_dump(mode="json") for e in model.graph.exchanges
        ]:
            raise ValueError("physical exchanges differ from the selected drain graph")
        expected_pumps = [p.model_dump(mode="json") for p in model.definitions.pumps]
        if data.get(R.PUMP, {}).get("pumps") != expected_pumps:
            raise ValueError("pump assets differ from selected static definitions")
        result = assess(model)
        blockers.extend(result.scenario_blockers)
        if not result.geometric_cross_ward_path:
            blockers.append("Selected graph has no cross-ward path to a defined receiver.")
        if any(n.ward_id not in snapshot.pilot_area.ward_ids for n in model.graph.nodes):
            raise ValueError("drain graph extends into a ward absent from the pilot declaration")
        if any(not pilot.covers(shape(e.geometry)) for e in model.graph.edges):
            blockers.append("Pilot does not contain the selected drain model.")
        if snapshot.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL:
            from floodguard.drainage.model_contracts import DrainImportDraft

            draft = DrainImportDraft.model_validate_json(snapshot.evidence["drain-draft"])
            imported, bound_wards = import_sources(
                draft.source_info,
                snapshot.evidence["drain-source-reconstruction"],
                snapshot.evidence["drain-source-wards"],
                max_bytes=128 * 1024 * 1024,
            )
            plan = ImportBindingPlan.model_validate(
                object_data(snapshot.evidence["drain-input"])["binding_plan"]
            )
            if bind_graph(imported, bound_wards, plan) != model:
                raise ValueError("real drain model cannot be recreated from its source bindings")
            real_cross = result.real_cross_ward_path_available and not result.geometry_errors
        if terrain is not None:
            frame = model.graph.vertical_reference
            compatible = (
                frame.datum_transform_status.value in {"COMPATIBLE", "TRANSFORMED"}
                and terrain.get("datum_transform_status") in {"COMPATIBLE", "TRANSFORMED"}
                and frame.vertical_datum == terrain.get("vertical_datum")
                and frame.vertical_unit == terrain.get("vertical_unit") == "m"
            )

    roofs: set[str] = set()
    for role in (R.VISUAL_CITY, R.HYDRAULIC_SURFACE):
        if role not in data:
            continue
        if data[role].get("floodguard_crs") != snapshot.horizontal_crs:
            raise ValueError("urban GIS component CRS differs from twin")
        for feature in data[role]["features"]:
            props = feature["properties"]
            cls = VisualFeature if role is R.VISUAL_CITY else HydraulicFeature
            values = {key: value for key, value in props.items() if key in cls.model_fields}
            typed = cls.model_validate({**values, "geometry": feature["geometry"]})
            validate_geometry(typed.geometry, geographic=False)
            if not pilot.covers(shape(typed.geometry)):
                blockers.append("Pilot does not contain all selected urban GIS geometry.")
            if props.get("surface_class") == "ROOF":
                roofs.add(typed.feature_id)
    if R.ROOF_RUNOFF in data:
        rules = [RoofRunoffRule.model_validate(r) for r in data[R.ROOF_RUNOFF]["rules"]]
        if (
            len({r.roof_feature_id for r in rules}) != len(rules)
            or {r.roof_feature_id for r in rules} != roofs
        ):
            raise ValueError("roof policies must match the selected hydraulic roof features")
        node_ids = {n.drain_node_id for n in model.graph.nodes} if model else set()
        for rule in rules:
            if (
                rule.explicit_drain_target is not None
                and rule.explicit_drain_target not in node_ids
            ):
                raise ValueError("roof target is absent from the selected drain graph")
            if rule.receiving_geometry and not pilot.covers(
                shape(rule.receiving_geometry.geometry)
            ):
                blockers.append("Roof receiving geometry lies outside the pilot area.")
    if R.PARAMETERS in data:
        expected = Snapshot(
            snapshot.city_id,
            snapshot.pilot_area,
            snapshot.horizontal_crs,
            snapshot.evidence_scope,
            dict(snapshot.components),
            dict(snapshot.sources),
            {},
            dict(snapshot.evidence),
        )
        assemble_parameters(expected)
        if expected.components.get(R.PARAMETERS) != snapshot.components[R.PARAMETERS]:
            raise ValueError("parameter set differs from the selected drain and surface versions")
    if not compatible:
        blockers.append(
            "Terrain, drain and static boundary elevations lack one compatible metric datum."
        )
    return sorted(set(blockers)), compatible, real_cross
