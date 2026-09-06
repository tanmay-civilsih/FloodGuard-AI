"""Aligned, explicitly synthetic components for deterministic twin recreation tests."""

from typing import Any

from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.reference import reference_model
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.terrain.contracts import TerrainGrid
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.contracts import PilotArea, SourceVersion
from floodguard.twin.snapshot import Snapshot, assemble_parameters
from floodguard.urban_gis.reference import _polygon, reference_package
from floodguard.urban_gis.service import _feature_geojson


def reference_snapshot() -> Snapshot:
    pilot_id = "kolkata-sequence9-reference"
    scope = DrainEvidenceScope.REFERENCE_FIXTURE
    pilot = PilotArea(
        pilot_area_id=pilot_id,
        geometry=_polygon(299990, 2499990, 300110, 2500070),
        ward_ids=["reference-A", "reference-B"],
    )
    snapshot = Snapshot("kolkata", pilot, "EPSG:32645", scope)
    model = reference_model()
    model.graph.pilot_area_id = pilot_id
    model.wards.boundaries[0].geometry = _polygon(299990, 2499990, 300025, 2500070)
    model.wards.boundaries[1].geometry = _polygon(300025, 2499990, 300110, 2500070)

    def add(role: R, content: dict[str, Any], group: str) -> None:
        payload = canonical_bytes(content)
        snapshot.add(
            role,
            payload,
            SourceVersion(
                domain="REFERENCE",
                product_id=group,
                pipeline_version="sequence-9-reference-v1",
                evidence_scope=scope,
                source_sha256=sha256(payload),
            ),
        )

    wards = {
        "type": "FeatureCollection",
        "floodguard_crs": snapshot.horizontal_crs,
        "features": [
            {"type": "Feature", "geometry": w.geometry, "properties": {"WARD": w.ward_id}}
            for w in model.wards.boundaries
        ],
    }
    old = model.wards.source
    new = old.model_copy(
        update={"sha256": sha256(canonical_bytes(wards)), "version": "twin-reference-v1"}
    )
    model.wards.source = new
    model.graph.source_references = [new if s == old else s for s in model.graph.source_references]
    add(R.WARD, wards, "reference-wards-v1")
    add(
        R.CATCHMENT,
        {
            "type": "FeatureCollection",
            "floodguard_crs": snapshot.horizontal_crs,
            "features": [
                {"type": "Feature", "id": "catchment", "properties": {}, "geometry": pilot.geometry}
            ],
        },
        "reference-catchment-v1",
    )
    add(
        R.WATERBODY,
        {
            "type": "FeatureCollection",
            "floodguard_crs": snapshot.horizontal_crs,
            "features": [
                {
                    "type": "Feature",
                    "id": "receiver",
                    "properties": {},
                    "geometry": model.definitions.outfalls[0].receiving_geometry,
                }
            ],
        },
        "reference-water-v1",
    )
    grid = TerrainGrid(
        width=12,
        height=8,
        origin_x_m=299990,
        origin_y_m=2499990,
        cell_size_m=10,
        crs=snapshot.horizontal_crs,
        elevations_m=[[6.0] * 12 for _ in range(8)],
    )
    for role in (R.VISUAL_TERRAIN, R.HYDRAULIC_TERRAIN):
        add(
            role,
            {
                "product": "VISUAL_TERRAIN" if role is R.VISUAL_TERRAIN else "HYDRAULIC_TERRAIN",
                "grid": grid.model_dump(mode="json"),
                "vertical_datum": "SYNTHETIC_REFERENCE_DATUM",
                "vertical_unit": "m",
                "datum_transform_status": "COMPATIBLE",
                "native_horizontal_resolution_m": 10,
                "computational_resolution_m": 10,
                "effective_information_resolution_m": 10,
                "source_surface_type": "DTM",
                "limitations": ["Controlled synthetic surface; no real terrain assessment."],
            },
            "reference-terrain-v1",
        )
    snapshot.evidence["terrain-metadata"] = canonical_bytes(
        {
            "readiness_status": "HYDRAULIC_SCENARIO_READY",
            "evidence_scope": scope.value,
            "limitations": ["Synthetic benchmark surface only."],
        }
    )
    urban = reference_package(pilot_area_id=pilot_id)
    add(
        R.VISUAL_CITY,
        {
            "type": "FeatureCollection",
            "floodguard_crs": snapshot.horizontal_crs,
            "features": [_feature_geojson(f, "VISUAL") for f in urban.visual_features],
        },
        "reference-urban-v1",
    )
    add(
        R.HYDRAULIC_SURFACE,
        {
            "type": "FeatureCollection",
            "floodguard_crs": snapshot.horizontal_crs,
            "features": [_feature_geojson(f, "HYDRAULIC") for f in urban.hydraulic_features],
        },
        "reference-urban-v1",
    )
    add(
        R.ROOF_RUNOFF,
        {
            "rules": [r.model_dump(mode="json") for r in urban.roof_runoff_rules],
            "surface_cell_binding": "DEFERRED_TO_SEQUENCE_11",
        },
        "reference-urban-v1",
    )
    add(R.DRAIN_GRAPH, model.graph.model_dump(mode="json"), "reference-drain-v1")
    add(
        R.EXCHANGE,
        {
            "exchanges": [e.model_dump(mode="json") for e in model.graph.exchanges],
            "surface_cell_binding": "DEFERRED_TO_SEQUENCE_11",
        },
        "reference-drain-v1",
    )
    add(
        R.PUMP,
        {"pumps": [p.model_dump(mode="json") for p in model.definitions.pumps]},
        "reference-drain-v1",
    )
    snapshot.evidence["drain-input"] = canonical_bytes({"model": model.model_dump(mode="json")})
    snapshot.evidence["drain-parameters"] = canonical_bytes(
        {
            "definitions": model.definitions.model_dump(mode="json"),
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
        }
    )
    snapshot.evidence["reference-description"] = canonical_bytes(
        {
            "scope": scope.value,
            "fixture_version": "sequence-9-reference-v1",
            "human_review_claimed": False,
        }
    )
    assemble_parameters(snapshot)
    return snapshot
