"""Explicit current-pipeline product selection and complete source-artifact verification."""

from __future__ import annotations

from typing import Any

from floodguard.common.integrity import verified_payload
from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.model_contracts import DRAIN_MODEL_PIPELINE_VERSION, DrainModelInput
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.drainage.service import DrainService
from floodguard.spatial.service import SPATIAL_PIPELINE_VERSION, SpatialService
from floodguard.terrain.contracts import TerrainProductKind
from floodguard.terrain.service import TERRAIN_PIPELINE_VERSION, TerrainService
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.contracts import SourceVersion, TwinBuildRequest
from floodguard.twin.snapshot import Snapshot, assemble_parameters, object_data
from floodguard.urban_gis.contracts import URBAN_GIS_PIPELINE_VERSION
from floodguard.urban_gis.service import UrbanGisService


class TwinSourceLoader:
    def __init__(
        self,
        terrain: TerrainService,
        urban: UrbanGisService,
        drains: DrainService,
        spatial: SpatialService,
        *,
        max_bytes: int,
    ) -> None:
        self.terrain = terrain
        self.urban = urban
        self.drains = drains
        self.spatial = spatial
        self.max_bytes = max_bytes

    def load(self, request: TwinBuildRequest) -> Snapshot:
        request = TwinBuildRequest.model_validate(request.model_dump(mode="json"))
        snapshot = Snapshot(
            request.city_id,
            request.pilot_area,
            request.horizontal_crs,
            DrainEvidenceScope.REAL_PILOT_PROVISIONAL,
        )
        snapshot.evidence["selection"] = canonical_bytes(request.model_dump(mode="json"))

        def check(record: Any, pipeline: str | None = None) -> None:
            if record.city_id != request.city_id or record.working_crs != request.horizontal_crs:
                raise ValueError("selected component city/CRS differs from twin request")
            if pipeline and record.pipeline_version != pipeline:
                raise ValueError("new twin builds require current component pipelines")
            if (
                hasattr(record, "pilot_area_id")
                and record.pilot_area_id != request.pilot_area.pilot_area_id
            ):
                raise ValueError("selected component belongs to another pilot")
            if (
                hasattr(record, "evidence_scope")
                and record.evidence_scope.value == "REFERENCE_FIXTURE"
            ):
                raise ValueError("reference components cannot be substituted into a real twin")

        def source(domain: Any, product_id: Any, pipeline: str, payload: bytes) -> SourceVersion:
            return SourceVersion(
                domain=domain,
                product_id=str(product_id),
                pipeline_version=pipeline,
                evidence_scope=snapshot.evidence_scope,
                source_sha256=sha256(payload),
            )

        for role, identity, category in (
            (R.WARD, request.ward_id, "WARD_BOUNDARY"),
            (R.CATCHMENT, request.catchment_id, "CATCHMENT"),
            (R.WATERBODY, request.waterbody_id, "WATER_BODY"),
        ):
            layer = self.spatial.get_layer(identity)
            check(layer)
            if layer.source_category != category:
                raise ValueError("selected spatial category does not match twin component")
            snapshot.evidence[f"{role.name.lower()}-qa"] = self.spatial.qa_geojson(identity)
            payload = self.spatial.object_store.read_spatial(layer.normalized_object_key)
            verified_payload(
                payload, expected_sha256=layer.normalized_sha256, max_bytes=self.max_bytes
            )
            snapshot.add(
                role, payload, source("SPATIAL", identity, SPATIAL_PIPELINE_VERSION, payload)
            )
            snapshot.evidence[f"{role.name.lower()}-metadata"] = canonical_bytes(
                layer.model_dump(mode="json")
            )

        if request.terrain_id is None:
            for role in (R.VISUAL_TERRAIN, R.HYDRAULIC_TERRAIN):
                snapshot.missing[role] = request.missing_reasons["terrain"]
        else:
            terrain = self.terrain.get(request.terrain_id)
            check(terrain, TERRAIN_PIPELINE_VERSION)
            for kind in TerrainProductKind:
                payload = self.terrain.read_artifact(terrain.terrain_id, kind)
                if len(payload) > self.max_bytes:
                    raise ValueError("terrain artifact exceeds twin snapshot size limit")
                if kind in {
                    TerrainProductKind.VISUAL_TERRAIN,
                    TerrainProductKind.HYDRAULIC_TERRAIN,
                }:
                    role = (
                        R.VISUAL_TERRAIN
                        if kind is TerrainProductKind.VISUAL_TERRAIN
                        else R.HYDRAULIC_TERRAIN
                    )
                    snapshot.add(
                        role,
                        payload,
                        source("TERRAIN", terrain.terrain_id, terrain.pipeline_version, payload),
                    )
                else:
                    snapshot.evidence[f"terrain-{kind.value.lower()}"] = payload
            snapshot.evidence["terrain-metadata"] = canonical_bytes(terrain.model_dump(mode="json"))

        if request.urban_gis_id is None:
            for role in (R.VISUAL_CITY, R.HYDRAULIC_SURFACE, R.ROOF_RUNOFF):
                snapshot.missing[role] = request.missing_reasons["urban_gis"]
        else:
            urban = self.urban.get(request.urban_gis_id)
            check(urban, URBAN_GIS_PIPELINE_VERSION)
            for name, urban_role in (
                ("visual", R.VISUAL_CITY),
                ("hydraulic", R.HYDRAULIC_SURFACE),
                ("roof-runoff", R.ROOF_RUNOFF),
                ("qa", None),
                ("audit", None),
            ):
                payload = self.urban.read_artifact(urban.urban_gis_id, name)
                if len(payload) > self.max_bytes:
                    raise ValueError("urban artifact exceeds twin snapshot size limit")
                if urban_role is None:
                    snapshot.evidence[f"urban-{name}"] = payload
                else:
                    snapshot.add(
                        urban_role,
                        payload,
                        source("URBAN_GIS", urban.urban_gis_id, urban.pipeline_version, payload),
                    )
            snapshot.evidence["urban-metadata"] = canonical_bytes(urban.model_dump(mode="json"))

        if request.drain_product_id is None:
            for role in (R.DRAIN_GRAPH, R.EXCHANGE, R.PUMP):
                snapshot.missing[role] = request.missing_reasons["drainage"]
        else:
            drain = self.drains.get(request.drain_product_id)
            check(drain, DRAIN_MODEL_PIPELINE_VERSION)
            self.drains.verify(drain)
            for name in drain.artifacts:
                snapshot.evidence[f"drain-{name}"] = self.drains.read_artifact(
                    drain.product_id, name
                )
            snapshot.evidence["drain-metadata"] = canonical_bytes(drain.model_dump(mode="json"))
            if drain.product_kind == "IMPORT_DRAFT":
                for role in (R.DRAIN_GRAPH, R.EXCHANGE, R.PUMP):
                    snapshot.missing[role] = (
                        "Selected source is an unbound VISUAL_ONLY drain import draft."
                    )
            else:
                for name, role in (("graph", R.DRAIN_GRAPH), ("exchanges", R.EXCHANGE)):
                    value = snapshot.evidence[f"drain-{name}"]
                    snapshot.add(
                        role,
                        value,
                        source("DRAINAGE", drain.product_id, drain.pipeline_version, value),
                    )
                model = DrainModelInput.model_validate(
                    object_data(snapshot.evidence["drain-input"])["model"]
                )
                pumps = canonical_bytes(
                    {"pumps": [p.model_dump(mode="json") for p in model.definitions.pumps]}
                )
                snapshot.add(
                    R.PUMP,
                    pumps,
                    source("DRAINAGE", drain.product_id, drain.pipeline_version, pumps),
                )
                plan = object_data(snapshot.evidence["drain-input"])["binding_plan"]
                from uuid import UUID

                draft = self.drains.get(UUID(plan["draft_id"]))
                if draft.fingerprint != plan["draft_fingerprint"]:
                    raise ValueError("directed graph binding no longer identifies the exact draft")
                self.drains.verify(draft)
                snapshot.evidence["drain-draft"] = self.drains.read_artifact(
                    draft.product_id, "draft"
                )
        assemble_parameters(snapshot)
        return snapshot
