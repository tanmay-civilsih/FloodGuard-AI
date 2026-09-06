"""Immutable drain products with artifact verification and conservative readiness."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid5

from floodguard.common.integrity import verified_payload
from floodguard.drainage.assessment import assess
from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.importer import bind_graph, import_sources
from floodguard.drainage.model_contracts import (
    DRAIN_MODEL_PIPELINE_VERSION,
    ArtifactReference,
    DrainBuildResult,
    DrainImportDraft,
    DrainModelInput,
    DrainProductRead,
    DrainReadiness,
    HydraulicReadiness,
    ImportBindingPlan,
    ImportSourceInfo,
    WardBoundarySet,
)
from floodguard.drainage.models import DrainProductRecord
from floodguard.drainage.repository import DrainRepository
from floodguard.drainage.serialization import canonical_bytes, decode_object, sha256
from floodguard.spatial.object_store import SpatialObjectExistsError, SpatialObjectStore

NAMESPACE = UUID("e49dcad9-45b2-4610-b0dc-75ae9c2195af")
ProductKind = Literal["IMPORT_DRAFT", "DIRECTED_GRAPH"]


class DrainIntegrityError(ValueError):
    """The immutable product cannot be trusted or reused."""


def fingerprint(kind: str, input_bytes: bytes) -> str:
    return sha256(
        canonical_bytes(
            {
                "pipeline": DRAIN_MODEL_PIPELINE_VERSION,
                "kind": kind,
                "input_sha256": sha256(input_bytes),
            }
        )
    )


def feature_collection(features: list[dict[str, Any]], crs: str) -> dict[str, Any]:
    return {"type": "FeatureCollection", "floodguard_crs": crs, "features": features}


class DrainService:
    def __init__(
        self,
        repository: DrainRepository,
        store: SpatialObjectStore,
        *,
        working_crs: str,
        max_bytes: int = 128 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.store = store
        self.working_crs = working_crs
        self.max_bytes = max_bytes

    def import_draft(
        self,
        info: ImportSourceInfo,
        reconstruction_bytes: bytes,
        ward_bytes: bytes,
    ) -> DrainBuildResult:
        draft, wards = import_sources(
            info, reconstruction_bytes, ward_bytes, max_bytes=self.max_bytes
        )
        content = {
            "source_info": info.model_dump(mode="json"),
            "reconstruction": decode_object(reconstruction_bytes, self.max_bytes),
            "ward_document": decode_object(ward_bytes, self.max_bytes),
        }
        artifacts = {
            "draft": canonical_bytes(draft.model_dump(mode="json")),
            "wards": canonical_bytes(wards.model_dump(mode="json")),
            "source-reconstruction": reconstruction_bytes,
            "source-wards": ward_bytes,
            "qa": canonical_bytes(
                feature_collection(
                    [
                        {
                            "type": "Feature",
                            "id": item.source_feature_id,
                            "geometry": item.geometry,
                            "properties": {
                                "kind": item.feature_kind,
                                "ward_ids": item.intersecting_ward_ids,
                                "status": "UNASSIGNED",
                            },
                        }
                        for item in draft.features
                    ],
                    info.working_crs,
                )
            ),
        }
        return self._persist(
            "IMPORT_DRAFT",
            content,
            artifacts,
            city_id=info.city_id,
            pilot_area_id=info.pilot_area_id,
            crs=info.working_crs,
            scope=info.evidence_scope,
        )

    def build_reference(self, model: DrainModelInput) -> DrainBuildResult:
        if model.graph.evidence_scope is not DrainEvidenceScope.REFERENCE_FIXTURE:
            raise ValueError("real-pilot graphs require a verified import binding plan")
        return self._build_model(model, {"model": model.model_dump(mode="json")})

    def build_bound(self, plan: ImportBindingPlan) -> DrainBuildResult:
        record = self.get(plan.draft_id)
        if record.product_kind != "IMPORT_DRAFT" or record.fingerprint != plan.draft_fingerprint:
            raise ValueError("binding plan does not identify the exact import draft")
        self.verify(record)
        draft = DrainImportDraft.model_validate_json(self.read_artifact(record.product_id, "draft"))
        wards = WardBoundarySet.model_validate_json(self.read_artifact(record.product_id, "wards"))
        model = bind_graph(draft, wards, plan)
        sources = {
            name: self.read_artifact(record.product_id, name)
            for name in ("source-reconstruction", "source-wards")
        }
        bound_ids = {
            feature for binding in plan.edge_bindings for feature in binding.source_feature_ids
        }
        sources["binding-coverage"] = canonical_bytes(
            {
                "draft_id": str(record.product_id),
                "source_drain_count": sum(f.feature_kind == "DRAIN" for f in draft.features),
                "unbound_drain_ids": sorted(
                    f.source_feature_id
                    for f in draft.features
                    if f.feature_kind == "DRAIN" and f.source_feature_id not in bound_ids
                ),
                "coverage_meaning": "Feature references only; partial line geometry is permitted.",
            }
        )
        return self._build_model(
            model,
            {
                "model": model.model_dump(mode="json"),
                "binding_plan": plan.model_dump(mode="json"),
                "draft_fingerprint": record.fingerprint,
            },
            sources=sources,
        )

    def _build_model(
        self,
        model: DrainModelInput,
        content: dict[str, Any],
        *,
        sources: dict[str, bytes] | None = None,
    ) -> DrainBuildResult:
        model = DrainModelInput.model_validate(model.model_dump(mode="json"))
        assessment = assess(model)
        if assessment.geometry_errors:
            raise ValueError("; ".join(assessment.geometry_errors))
        graph = model.graph
        qa_features = [
            {
                "type": "Feature",
                "id": item.drain_node_id,
                "geometry": item.geometry,
                "properties": {"kind": item.node_type.value, "ward_id": item.ward_id},
            }
            for item in graph.nodes
        ]
        qa_features.extend(
            [
                {
                    "type": "Feature",
                    "id": item.drain_edge_id,
                    "geometry": item.geometry,
                    "properties": {
                        "kind": item.edge_type.value,
                        "from": item.from_node_id,
                        "to": item.to_node_id,
                    },
                }
                for item in graph.edges
            ]
        )
        qa_features.extend(
            [
                {
                    "type": "Feature",
                    "id": item.exchange_id,
                    "geometry": item.geometry,
                    "properties": {"kind": item.exchange_type.value, "node_id": item.drain_node_id},
                }
                for item in graph.exchanges
            ]
        )
        artifacts = {
            "graph": canonical_bytes(graph.model_dump(mode="json")),
            "parameters": canonical_bytes(
                {
                    "nodes": [
                        {
                            "drain_node_id": node.drain_node_id,
                            "invert_elevation": node.invert_elevation.model_dump(mode="json"),
                            "storage_volume": node.storage_volume.model_dump(mode="json"),
                        }
                        for node in graph.nodes
                    ],
                    "edges": [
                        {
                            "drain_edge_id": edge.drain_edge_id,
                            "parameters": edge.parameters.model_dump(mode="json"),
                        }
                        for edge in graph.edges
                    ],
                    "definitions": model.definitions.model_dump(mode="json"),
                }
            ),
            "exchanges": canonical_bytes(
                {
                    "surface_cell_binding": "DEFERRED_TO_SEQUENCE_11",
                    "exchanges": [item.model_dump(mode="json") for item in graph.exchanges],
                }
            ),
            "assessment": canonical_bytes(assessment.model_dump(mode="json")),
            "wards": canonical_bytes(model.wards.model_dump(mode="json")),
            "qa": canonical_bytes(feature_collection(qa_features, graph.working_crs)),
            **(sources or {}),
        }
        return self._persist(
            "DIRECTED_GRAPH",
            content,
            artifacts,
            city_id=graph.city_id,
            pilot_area_id=graph.pilot_area_id,
            crs=graph.working_crs,
            scope=graph.evidence_scope,
        )

    def _persist(
        self,
        kind: ProductKind,
        content: dict[str, Any],
        payloads: dict[str, bytes],
        *,
        city_id: str,
        pilot_area_id: str,
        crs: str,
        scope: DrainEvidenceScope,
    ) -> DrainBuildResult:
        if crs != self.working_crs:
            raise ValueError("drain product must use the configured working CRS")
        payloads = {**payloads, "input": canonical_bytes(content)}
        product_fingerprint = fingerprint(kind, payloads["input"])
        existing = self.repository.find(product_fingerprint)
        if existing is not None:
            self.verify(self.repository.read(existing))
            return DrainBuildResult(
                product_id=existing.product_id, created=False, product_kind=kind
            )
        product_id = uuid5(NAMESPACE, product_fingerprint)
        prefix = f"drainage/{product_id}"
        payloads["audit"] = canonical_bytes(
            {
                "pipeline_version": DRAIN_MODEL_PIPELINE_VERSION,
                "fingerprint": product_fingerprint,
                "product_id": str(product_id),
                "product_kind": kind,
                "evidence_scope": scope.value,
                "city_id": city_id,
                "pilot_area_id": pilot_area_id,
                "working_crs": crs,
                "artifacts": {name: sha256(value) for name, value in payloads.items()},
                "surface_cell_ids_assigned": False,
                "final_human_acceptance": "PENDING_SEQUENCE_20",
            }
        )
        if any(len(payload) > self.max_bytes for payload in payloads.values()):
            raise ValueError("drain artifact exceeds configured size limit")
        self.store.ensure_ready()
        references = {}
        for name, payload in payloads.items():
            key = f"{prefix}/{name}.json"
            try:
                self.store.put_spatial_once(key, payload, content_type="application/json")
            except SpatialObjectExistsError as exc:
                if self.store.read_spatial(key) != payload:
                    raise DrainIntegrityError(
                        "immutable drain artifact already has different bytes"
                    ) from exc
            verified_payload(
                self.store.read_spatial(key),
                expected_sha256=sha256(payload),
                expected_size=len(payload),
                max_bytes=self.max_bytes,
            )
            references[name] = ArtifactReference(
                object_key=key,
                sha256=sha256(payload),
                byte_size=len(payload),
                media_type="application/json",
            ).model_dump(mode="json")
        record, created = self.repository.add(
            DrainProductRecord(
                product_id=product_id,
                city_id=city_id,
                pilot_area_id=pilot_area_id,
                fingerprint=product_fingerprint,
                pipeline_version=DRAIN_MODEL_PIPELINE_VERSION,
                product_kind=kind,
                evidence_scope=scope.value,
                working_crs=crs,
                artifacts=references,
            )
        )
        self.verify(self.repository.read(record))
        return DrainBuildResult(product_id=record.product_id, created=created, product_kind=kind)

    def get(self, product_id: UUID) -> DrainProductRead:
        record = self.repository.get(product_id)
        if record is None:
            raise LookupError(str(product_id))
        return self.repository.read(record)

    def list_products(self, city_id: str) -> list[DrainProductRead]:
        return [self.repository.read(item) for item in self.repository.list_products(city_id)]

    def read_artifact(self, product_id: UUID, name: str) -> bytes:
        record = self.get(product_id)
        if name not in record.artifacts:
            raise LookupError("unsupported drain artifact")
        reference = record.artifacts[name]
        try:
            return verified_payload(
                self.store.read_spatial(reference.object_key),
                expected_sha256=reference.sha256,
                expected_size=reference.byte_size,
                max_bytes=self.max_bytes,
            )
        except ValueError as exc:
            raise DrainIntegrityError(str(exc)) from exc

    def verify(self, record: DrainProductRead) -> None:
        required = {"input", "audit", "wards", "qa"}
        if record.product_kind == "IMPORT_DRAFT":
            required |= {"draft", "source-reconstruction", "source-wards"}
        else:
            required |= {"graph", "parameters", "exchanges", "assessment"}
            if record.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL:
                required |= {"source-reconstruction", "source-wards", "binding-coverage"}
        if not required.issubset(record.artifacts):
            raise DrainIntegrityError("drain product lacks required artifacts")
        payloads = {name: self.read_artifact(record.product_id, name) for name in record.artifacts}
        audit = decode_object(payloads["audit"], self.max_bytes)
        if (
            fingerprint(record.product_kind, payloads["input"]) != record.fingerprint
            or uuid5(NAMESPACE, record.fingerprint) != record.product_id
            or audit.get("product_id") != str(record.product_id)
            or audit.get("artifacts")
            != {name: sha256(value) for name, value in payloads.items() if name != "audit"}
            or any(
                audit.get(name) != getattr(record, name)
                for name in (
                    "city_id",
                    "pilot_area_id",
                    "working_crs",
                    "fingerprint",
                    "product_kind",
                    "evidence_scope",
                    "pipeline_version",
                )
            )
        ):
            raise DrainIntegrityError("drain artifact manifest/identity mismatch")

    def readiness(self, city_id: str) -> DrainReadiness:
        records = self.list_products(city_id)
        eligible = real_imports = reference_ready = real_graphs = 0
        real_cross = False
        for record in records:
            if (
                record.pipeline_version != DRAIN_MODEL_PIPELINE_VERSION
                or record.working_crs != self.working_crs
            ):
                continue
            try:
                self.verify(record)
                real = record.evidence_scope is DrainEvidenceScope.REAL_PILOT_PROVISIONAL
                if record.product_kind == "IMPORT_DRAFT":
                    eligible += 1
                    real_imports += int(real)
                    continue
                content = decode_object(
                    self.read_artifact(record.product_id, "input"), self.max_bytes
                )
                result = assess(DrainModelInput.model_validate(content["model"]))
                if result.geometry_errors:
                    continue
                eligible += 1
                real_graphs += int(real)
                real_cross |= result.real_cross_ward_path_available
                reference_ready += int(
                    not real
                    and result.readiness_status is HydraulicReadiness.HYDRAULIC_SCENARIO_READY
                    and result.geometric_cross_ward_path
                )
            except (ValueError, FileNotFoundError, KeyError):
                continue
        technical = reference_ready > 0 and real_imports > 0
        return DrainReadiness(
            city_id=city_id,
            total_products=len(records),
            eligible_products=eligible,
            real_pilot_imports=real_imports,
            reference_ready=reference_ready,
            provisional_real_graphs=real_graphs,
            real_cross_ward_path_available=real_cross,
            technical_development_gate_passed=technical,
            sequence9_real_cross_ward_gate_passed=False,
            completion_reason=(
                "Reference and real-source import verified; final acceptance remains pending."
                if technical
                else "A ready cross-ward reference and verified real-source import are required."
            ),
        )
