"""Sequence 5 reconstruction orchestration, lineage, confidence, and review gate."""

from __future__ import annotations

import hashlib
import json
from math import hypot
from typing import Any
from uuid import UUID, uuid4, uuid5

from pyproj import Transformer

from floodguard.contracts.time import utc_now
from floodguard.harvester.contracts import DatasetVersionRead, DatasetVersionStatus, RawObjectRead
from floodguard.reconstruction.contracts import (
    ConfidenceBand,
    DrainageReconstructionRead,
    ExtractionMode,
    ReconstructionCalibration,
    ReconstructionReadiness,
    ReconstructionResult,
    ReconstructionReviewCreate,
    ReconstructionReviewRead,
    ReconstructionStatus,
    ReviewDecision,
    ReviewerType,
)
from floodguard.reconstruction.georeference import AffineFit, fit_affine
from floodguard.reconstruction.models import (
    DrainageReconstructionRecord,
    ReconstructionReviewRecord,
)
from floodguard.reconstruction.pdf_native import (
    CleanedDrain,
    NativeStructure,
    NativeTextSpan,
    clean_native_drain_paths,
    drainage_labels,
    extract_native_structures,
    inspect_native_pdf,
    is_manhole_label,
)
from floodguard.reconstruction.repository import ReconstructionRepository
from floodguard.registry.contracts import SourceCategory, SourceRead
from floodguard.spatial.object_store import SpatialObjectExistsError, SpatialObjectStore

RECONSTRUCTION_NAMESPACE = UUID("49d6e434-362b-4b7f-bbe8-24f8d55ce912")
RECONSTRUCTION_PIPELINE_VERSION = "sequence-5-v1"


class ReconstructionError(RuntimeError):
    pass


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _put_idempotent(
    object_store: SpatialObjectStore,
    object_key: str,
    payload: bytes,
    *,
    content_type: str,
) -> None:
    try:
        object_store.put_spatial_once(object_key, payload, content_type=content_type)
    except SpatialObjectExistsError as exc:
        if object_store.read_spatial(object_key) != payload:
            raise ReconstructionError(
                f"immutable reconstruction key exists with different bytes: {object_key}"
            ) from exc


def _confidence_band(score: float) -> ConfidenceBand:
    if score >= 0.85:
        return ConfidenceBand.HIGH
    if score >= 0.60:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _distance_to_segment(point: tuple[float, float], drain: CleanedDrain) -> float:
    px, py = point
    ax, ay = drain.start
    bx, by = drain.end
    vx, vy = bx - ax, by - ay
    denominator = vx * vx + vy * vy
    if denominator == 0:
        return hypot(px - ax, py - ay)
    position = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / denominator))
    closest = (ax + position * vx, ay + position * vy)
    return hypot(px - closest[0], py - closest[1])


def _nearest_drain_index(
    point: tuple[float, float],
    drains: tuple[CleanedDrain, ...],
    *,
    maximum_distance_points: float = 40.0,
) -> int | None:
    if not drains:
        return None
    distances = [_distance_to_segment(point, drain) for drain in drains]
    index = min(range(len(distances)), key=distances.__getitem__)
    return index if distances[index] <= maximum_distance_points else None


def _nearest_manhole_label(
    structure: NativeStructure,
    labels: tuple[NativeTextSpan, ...],
) -> str | None:
    candidates = [label for label in labels if is_manhole_label(label.text)]
    if not candidates:
        return None
    label = min(
        candidates,
        key=lambda item: hypot(
            structure.point[0] - item.point[0],
            structure.point[1] - item.point[1],
        ),
    )
    distance = hypot(
        structure.point[0] - label.point[0],
        structure.point[1] - label.point[1],
    )
    return label.text if distance <= 30.0 else None


def _bounds(features: list[dict[str, Any]]) -> list[float]:
    coordinates: list[tuple[float, float]] = []
    for feature in features:
        geometry = feature["geometry"]
        raw_coordinates = geometry["coordinates"]
        if geometry["type"] == "Point":
            coordinates.append((float(raw_coordinates[0]), float(raw_coordinates[1])))
        else:
            coordinates.extend((float(item[0]), float(item[1])) for item in raw_coordinates)
    if not coordinates:
        raise ReconstructionError("reconstruction produced no feature coordinates")
    xs = [item[0] for item in coordinates]
    ys = [item[1] for item in coordinates]
    return [min(xs), min(ys), max(xs), max(ys)]


def _qa_features(
    features: list[dict[str, Any]],
    *,
    working_crs: str,
) -> list[dict[str, Any]]:
    transformer = Transformer.from_crs(working_crs, "EPSG:4326", always_xy=True)
    qa: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature["geometry"]
        raw_coordinates = geometry["coordinates"]
        if geometry["type"] == "Point":
            coordinates: object = list(
                transformer.transform(float(raw_coordinates[0]), float(raw_coordinates[1]))
            )
        else:
            coordinates = [
                list(transformer.transform(float(item[0]), float(item[1])))
                for item in raw_coordinates
            ]
        qa.append(
            {
                "type": "Feature",
                "id": feature["id"],
                "geometry": {"type": geometry["type"], "coordinates": coordinates},
                "properties": feature["properties"],
            }
        )
    return qa


def _fingerprint(
    source: SourceRead,
    version: DatasetVersionRead,
    raw_object: RawObjectRead,
    calibration: ReconstructionCalibration,
    *,
    working_crs: str,
) -> str:
    payload = {
        "pipeline_version": RECONSTRUCTION_PIPELINE_VERSION,
        "source_id": str(source.source_id),
        "source_dataset_version_id": str(version.dataset_version_id),
        "source_object_id": str(raw_object.object_id),
        "source_object_key": raw_object.object_key,
        "source_sha256": raw_object.sha256,
        "working_crs": working_crs,
        "calibration": calibration.model_dump(mode="json"),
    }
    return _sha256(_json_bytes(payload))


class ReconstructionService:
    def __init__(
        self,
        repository: ReconstructionRepository,
        object_store: SpatialObjectStore,
        *,
        working_crs: str,
        max_object_bytes: int,
    ) -> None:
        if max_object_bytes < 1:
            raise ValueError("max_object_bytes must be positive")
        Transformer.from_crs(working_crs, "EPSG:4326", always_xy=True)
        self.repository = repository
        self.object_store = object_store
        self.working_crs = working_crs
        self.max_object_bytes = max_object_bytes

    def reconstruct(
        self,
        source: SourceRead,
        version: DatasetVersionRead,
        raw_object: RawObjectRead,
        calibration: ReconstructionCalibration,
    ) -> ReconstructionResult:
        self._validate_inputs(source, version, raw_object, calibration)
        existing_fingerprint = _fingerprint(
            source,
            version,
            raw_object,
            calibration,
            working_crs=self.working_crs,
        )
        existing = self.repository.find_by_fingerprint(existing_fingerprint)
        if existing is not None:
            return ReconstructionResult(
                reconstruction_id=existing.reconstruction_id,
                created=False,
                status=ReconstructionStatus(existing.status),
                drain_count=existing.drain_count,
                structure_count=existing.structure_count,
                label_count=existing.label_count,
                georeference_rmse_m=existing.georeference_rmse_m,
            )

        self.object_store.ensure_ready()
        raw_payload = self.object_store.read_raw(raw_object.object_key)
        if len(raw_payload) > self.max_object_bytes:
            raise ReconstructionError("raw drainage map exceeds configured object-size limit")
        if _sha256(raw_payload) != raw_object.sha256:
            raise ReconstructionError("raw drainage map bytes do not match immutable SHA-256")
        extraction = inspect_native_pdf(raw_payload, selected_page=calibration.source_page)
        if extraction.inspection.extraction_mode is not ExtractionMode.NATIVE_VECTOR_TEXT:
            raise ReconstructionError(
                "native vector/text content is insufficient; an explicit OCR fallback review "
                "is required before reconstruction"
            )
        affine = fit_affine(calibration, working_crs=self.working_crs)
        if affine.rmse_m > calibration.max_georeference_rmse_m:
            raise ReconstructionError(
                f"georeference RMSE {affine.rmse_m:.3f} m exceeds the calibrated "
                f"{calibration.max_georeference_rmse_m:.3f} m tolerance"
            )
        drains = clean_native_drain_paths(extraction.paths)
        structures = extract_native_structures(extraction.paths)
        labels = drainage_labels(
            extraction.text_spans,
            page_width=extraction.inspection.page_width_points,
            page_height=extraction.inspection.page_height_points,
        )
        if not drains or not structures or not labels:
            raise ReconstructionError(
                "native reconstruction did not produce drains, structures, and labels"
            )
        reconstruction_id = uuid5(
            RECONSTRUCTION_NAMESPACE,
            existing_fingerprint,
        )
        working_features, confidence_summary = self._build_features(
            reconstruction_id,
            version,
            raw_object,
            affine,
            drains,
            structures,
            labels,
            source_page=calibration.source_page,
        )
        qa_features = _qa_features(working_features, working_crs=self.working_crs)
        working_collection = {
            "type": "FeatureCollection",
            "name": f"KMC Ward {calibration.ward_id} reconstructed drainage",
            "crs": {"type": "name", "properties": {"name": self.working_crs}},
            "features": working_features,
        }
        qa_collection = {
            "type": "FeatureCollection",
            "name": f"KMC Ward {calibration.ward_id} reconstructed drainage QA",
            "features": qa_features,
        }
        audit = {
            "reconstruction_id": str(reconstruction_id),
            "pipeline_version": RECONSTRUCTION_PIPELINE_VERSION,
            "source": {
                "source_id": str(source.source_id),
                "dataset_version_id": str(version.dataset_version_id),
                "object_id": str(raw_object.object_id),
                "object_key": raw_object.object_key,
                "filename": raw_object.filename,
                "url": raw_object.source_url,
                "sha256": raw_object.sha256,
                "authority": source.authority_level.value,
            },
            "calibration": calibration.model_dump(mode="json"),
            "native_inspection": extraction.inspection.model_dump(mode="json"),
            "affine_coefficients": list(affine.coefficients),
            "control_results": [item.model_dump(mode="json") for item in affine.control_results],
            "georeference_rmse_m": affine.rmse_m,
            "georeference_max_error_m": affine.max_error_m,
            "feature_counts": {
                "drains": len(drains),
                "structures": len(structures),
                "labels": len(labels),
            },
            "missing_attribute_policy": {
                "dimension_m": None,
                "invert_elevation_m": None,
                "flow_direction": None,
                "material": None,
                "reason": "Labels are preserved as annotations; engineering values remain NULL "
                "until human interpretation and validation.",
            },
            "initial_review_status": ReconstructionStatus.PENDING_REVIEW.value,
        }
        working_bytes = _json_bytes(working_collection)
        qa_bytes = _json_bytes(qa_collection)
        audit_bytes = _json_bytes(audit)
        prefix = (
            f"reconstruction/{source.city_id}/{source.source_id}/"
            f"{version.dataset_version_id}/{reconstruction_id}"
        )
        working_key = f"{prefix}/working.geojson"
        qa_key = f"{prefix}/qa.geojson"
        audit_key = f"{prefix}/audit.json"
        _put_idempotent(
            self.object_store,
            working_key,
            working_bytes,
            content_type="application/geo+json",
        )
        _put_idempotent(
            self.object_store,
            qa_key,
            qa_bytes,
            content_type="application/geo+json",
        )
        _put_idempotent(
            self.object_store,
            audit_key,
            audit_bytes,
            content_type="application/json",
        )
        bounds_working = _bounds(working_features)
        bounds_wgs84 = _bounds(qa_features)
        now = utc_now()
        record = DrainageReconstructionRecord(
            reconstruction_id=reconstruction_id,
            source_dataset_version_id=version.dataset_version_id,
            source_id=source.source_id,
            source_object_id=raw_object.object_id,
            city_id=source.city_id,
            ward_id=calibration.ward_id,
            source_authority=source.authority_level.value,
            source_object_key=raw_object.object_key,
            source_filename=raw_object.filename,
            source_url=raw_object.source_url,
            source_sha256=raw_object.sha256,
            reconstruction_fingerprint=existing_fingerprint,
            pipeline_version=RECONSTRUCTION_PIPELINE_VERSION,
            calibration_id=calibration.calibration_id,
            working_crs=self.working_crs,
            georeference_method=calibration.georeference_method,
            affine_coefficients=list(affine.coefficients),
            control_points=[item.model_dump(mode="json") for item in affine.control_results],
            georeference_rmse_m=affine.rmse_m,
            georeference_max_error_m=affine.max_error_m,
            georeference_tolerance_m=calibration.max_georeference_rmse_m,
            native_inspection=extraction.inspection.model_dump(mode="json"),
            working_object_key=working_key,
            qa_object_key=qa_key,
            audit_object_key=audit_key,
            working_sha256=_sha256(working_bytes),
            qa_sha256=_sha256(qa_bytes),
            audit_sha256=_sha256(audit_bytes),
            feature_count=len(working_features),
            drain_count=len(drains),
            structure_count=len(structures),
            label_count=len(labels),
            bounds_working=bounds_working,
            bounds_wgs84=bounds_wgs84,
            confidence_summary=confidence_summary,
            status=ReconstructionStatus.PENDING_REVIEW.value,
            reviewed_by=None,
            reviewed_at=None,
            created_at=now,
        )
        persisted, created = self.repository.add(record)
        return ReconstructionResult(
            reconstruction_id=persisted.reconstruction_id,
            created=created,
            status=ReconstructionStatus(persisted.status),
            drain_count=persisted.drain_count,
            structure_count=persisted.structure_count,
            label_count=persisted.label_count,
            georeference_rmse_m=persisted.georeference_rmse_m,
        )

    def _validate_inputs(
        self,
        source: SourceRead,
        version: DatasetVersionRead,
        raw_object: RawObjectRead,
        calibration: ReconstructionCalibration,
    ) -> None:
        if source.category is not SourceCategory.DRAINAGE_MAP:
            raise ReconstructionError("only governed DRAINAGE_MAP sources can be reconstructed")
        if version.status is not DatasetVersionStatus.COMPLETE:
            raise ReconstructionError("only COMPLETE immutable raw versions can be reconstructed")
        if version.source_id != source.source_id or version.city_id != source.city_id:
            raise ReconstructionError("raw dataset version does not belong to the source")
        if raw_object.dataset_version_id != version.dataset_version_id:
            raise ReconstructionError("raw object does not belong to the dataset version")
        if not any(item.object_id == raw_object.object_id for item in version.objects):
            raise ReconstructionError("raw object is not present in the immutable version contract")
        if raw_object.filename != calibration.source_filename:
            raise ReconstructionError("calibration filename does not match raw object")
        if raw_object.sha256 != calibration.source_sha256:
            raise ReconstructionError("calibration SHA-256 does not match raw object")

    def _build_features(
        self,
        reconstruction_id: UUID,
        version: DatasetVersionRead,
        raw_object: RawObjectRead,
        affine: AffineFit,
        drains: tuple[CleanedDrain, ...],
        structures: tuple[NativeStructure, ...],
        labels: tuple[NativeTextSpan, ...],
        *,
        source_page: int,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        features: list[dict[str, Any]] = []
        confidence_counts = {band.value: 0 for band in ConfidenceBand}
        drain_ids: list[UUID] = []
        lineage = {
            "reconstruction_id": str(reconstruction_id),
            "source_dataset_version_id": str(version.dataset_version_id),
            "source_object_id": str(raw_object.object_id),
            "source_object_key": raw_object.object_key,
            "source_page": source_page,
        }
        for index, drain in enumerate(drains):
            feature_id = uuid5(reconstruction_id, f"drain:{index}")
            drain_ids.append(feature_id)
            score = 0.90 if drain.source_fragment_count >= 3 else 0.78
            band = _confidence_band(score)
            confidence_counts[band.value] += 1
            features.append(
                {
                    "type": "Feature",
                    "id": str(feature_id),
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            list(affine.transform(*drain.start)),
                            list(affine.transform(*drain.end)),
                        ],
                    },
                    "properties": {
                        **lineage,
                        "feature_id": str(feature_id),
                        "feature_kind": "DRAIN",
                        "extraction_method": "NATIVE_RED_CAD_STROKE_MERGE",
                        "confidence_score": score,
                        "confidence_band": band.value,
                        "source_fragment_count": drain.source_fragment_count,
                        "source_length_points": drain.source_length_points,
                        "dimension_m": None,
                        "invert_elevation_m": None,
                        "flow_direction": None,
                        "material": None,
                    },
                }
            )
        for index, structure in enumerate(structures):
            feature_id = uuid5(reconstruction_id, f"structure:{index}")
            drain_index = _nearest_drain_index(structure.point, drains)
            score = 0.86
            band = _confidence_band(score)
            confidence_counts[band.value] += 1
            features.append(
                {
                    "type": "Feature",
                    "id": str(feature_id),
                    "geometry": {
                        "type": "Point",
                        "coordinates": list(affine.transform(*structure.point)),
                    },
                    "properties": {
                        **lineage,
                        "feature_id": str(feature_id),
                        "feature_kind": "STRUCTURE",
                        "structure_type": "MANHOLE_CANDIDATE",
                        "structure_label": _nearest_manhole_label(structure, labels),
                        "associated_drain_id": (
                            str(drain_ids[drain_index]) if drain_index is not None else None
                        ),
                        "extraction_method": "NATIVE_CYAN_CAD_CIRCLE",
                        "confidence_score": score,
                        "confidence_band": band.value,
                        "invert_elevation_m": None,
                        "material": None,
                    },
                }
            )
        for index, label in enumerate(labels):
            feature_id = uuid5(reconstruction_id, f"label:{index}:{label.text}")
            drain_index = _nearest_drain_index(label.point, drains)
            score = 0.90
            band = _confidence_band(score)
            confidence_counts[band.value] += 1
            features.append(
                {
                    "type": "Feature",
                    "id": str(feature_id),
                    "geometry": {
                        "type": "Point",
                        "coordinates": list(affine.transform(*label.point)),
                    },
                    "properties": {
                        **lineage,
                        "feature_id": str(feature_id),
                        "feature_kind": "LABEL",
                        "raw_text": label.text,
                        "associated_drain_id": (
                            str(drain_ids[drain_index]) if drain_index is not None else None
                        ),
                        "extraction_method": "NATIVE_PDF_TEXT",
                        "confidence_score": score,
                        "confidence_band": band.value,
                        "interpreted_engineering_value": None,
                    },
                }
            )
        return features, confidence_counts

    def get(self, reconstruction_id: UUID) -> DrainageReconstructionRead:
        record = self.repository.get(reconstruction_id)
        if record is None:
            raise LookupError(str(reconstruction_id))
        return self.repository.read(record)

    def list_reconstructions(
        self,
        *,
        city_id: str | None = None,
    ) -> list[DrainageReconstructionRead]:
        return self.repository.reads(
            self.repository.list_reconstructions(city_id=city_id)
        )

    def qa_geojson(self, reconstruction_id: UUID) -> bytes:
        reconstruction = self.get(reconstruction_id)
        return self.object_store.read_spatial(reconstruction.qa_object_key)

    def review(
        self,
        reconstruction_id: UUID,
        request: ReconstructionReviewCreate,
    ) -> ReconstructionReviewRead:
        reconstruction = self.repository.get(reconstruction_id)
        if reconstruction is None:
            raise LookupError(str(reconstruction_id))
        if request.decision is ReviewDecision.APPROVE:
            if request.reviewer_type is not ReviewerType.HUMAN:
                raise ReconstructionError(
                    "automated review cannot satisfy the human approval completion gate"
                )
            if not request.all_checks_passed:
                raise ReconstructionError("approval requires every engineering QA check")
            status = ReconstructionStatus.APPROVED
        else:
            status = ReconstructionStatus.REJECTED
        checklist = {
            "source_alignment_checked": request.source_alignment_checked,
            "drain_symbology_checked": request.drain_symbology_checked,
            "feature_placement_checked": request.feature_placement_checked,
            "missing_attributes_not_invented": request.missing_attributes_not_invented,
        }
        record = ReconstructionReviewRecord(
            review_id=uuid4(),
            reconstruction_id=reconstruction_id,
            decision=request.decision.value,
            reviewer=request.reviewer,
            reviewer_type=request.reviewer_type.value,
            notes=request.notes,
            checklist=checklist,
            created_at=utc_now(),
        )
        persisted = self.repository.add_review(
            reconstruction,
            record,
            resulting_status=status.value,
        )
        return ReconstructionReviewRead.model_validate(persisted)

    def list_reviews(self, reconstruction_id: UUID) -> list[ReconstructionReviewRead]:
        if self.repository.get(reconstruction_id) is None:
            raise LookupError(str(reconstruction_id))
        return self.repository.review_reads(self.repository.list_reviews(reconstruction_id))

    def readiness(self, *, city_id: str) -> ReconstructionReadiness:
        records = self.repository.list_reconstructions(city_id=city_id)
        pending = sum(
            item.status == ReconstructionStatus.PENDING_REVIEW.value for item in records
        )
        approved = sum(item.status == ReconstructionStatus.APPROVED.value for item in records)
        rejected = sum(item.status == ReconstructionStatus.REJECTED.value for item in records)
        geographic = sum(
            item.georeference_rmse_m <= item.georeference_tolerance_m
            and item.georeference_max_error_m <= item.georeference_tolerance_m
            for item in records
        )
        native = sum(
            item.native_inspection.get("extraction_mode")
            == ExtractionMode.NATIVE_VECTOR_TEXT.value
            and item.native_inspection.get("ocr_used") is False
            for item in records
        )
        qualifying = [
            item
            for item in records
            if item.status == ReconstructionStatus.APPROVED.value
            and item.georeference_rmse_m <= item.georeference_tolerance_m
            and item.georeference_max_error_m <= item.georeference_tolerance_m
            and item.source_authority == "MUNICIPAL_PRIMARY"
            and item.drain_count > 0
            and item.structure_count > 0
            and item.label_count > 0
            and item.native_inspection.get("extraction_mode")
            == ExtractionMode.NATIVE_VECTOR_TEXT.value
        ]
        gate = bool(qualifying)
        if gate:
            reason = "At least one real, valid, native-content reconstruction has human approval."
        elif not records:
            reason = "No real municipal drainage map has been reconstructed."
        elif not approved:
            reason = (
                "A geographically valid reconstruction exists but still needs human QA approval."
            )
        else:
            reason = "No approved reconstruction satisfies all geometry and provenance checks."
        return ReconstructionReadiness(
            city_id=city_id,
            total_reconstructions=len(records),
            pending_review=pending,
            approved_reconstructions=approved,
            rejected_reconstructions=rejected,
            geographically_valid=geographic,
            native_vector_text_reconstructions=native,
            total_drains=sum(item.drain_count for item in records),
            total_structures=sum(item.structure_count for item in records),
            total_labels=sum(item.label_count for item in records),
            completion_gate_passed=gate,
            completion_gate_reason=reason,
        )
