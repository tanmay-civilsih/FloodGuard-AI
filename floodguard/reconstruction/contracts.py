"""Public contracts for Sequence 5 municipal drainage reconstruction."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionMode(StrEnum):
    NATIVE_VECTOR_TEXT = "NATIVE_VECTOR_TEXT"
    OCR_FALLBACK = "OCR_FALLBACK"


class ReconstructionStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ReviewerType(StrEnum):
    HUMAN = "HUMAN"
    AUTOMATED = "AUTOMATED"


class ConfidenceBand(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CalibrationControlPoint(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    page_x: float
    page_y: float
    target_x: float
    target_y: float
    match_description: str = Field(min_length=1)


class ReconstructionCalibration(BaseModel):
    calibration_id: str = Field(min_length=1, max_length=160)
    ward_id: str = Field(min_length=1, max_length=32)
    source_filename: str = Field(min_length=1, max_length=300)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_page: int = Field(default=1, ge=1)
    target_crs: str = Field(min_length=1, max_length=100)
    control_reference: str = Field(min_length=1)
    control_reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    georeference_method: str = Field(min_length=1, max_length=160)
    max_georeference_rmse_m: float = Field(gt=0, le=100)
    control_points: list[CalibrationControlPoint] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_unique_controls(self) -> ReconstructionCalibration:
        page_points = {(item.page_x, item.page_y) for item in self.control_points}
        target_points = {(item.target_x, item.target_y) for item in self.control_points}
        if len(page_points) != len(self.control_points):
            raise ValueError("calibration page control points must be unique")
        if len(target_points) != len(self.control_points):
            raise ValueError("calibration target control points must be unique")
        return self


class NativePdfInspection(BaseModel):
    page_count: int
    selected_page: int
    page_width_points: float
    page_height_points: float
    page_rotation_degrees: int
    native_vector_path_count: int
    native_text_span_count: int
    embedded_image_count: int
    extraction_mode: ExtractionMode
    ocr_used: bool
    metadata: dict[str, str]


class GeoreferenceControlResult(BaseModel):
    name: str
    page_x: float
    page_y: float
    target_easting_m: float
    target_northing_m: float
    residual_m: float
    match_description: str


class DrainageReconstructionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reconstruction_id: UUID
    source_dataset_version_id: UUID
    source_id: UUID
    source_object_id: UUID
    city_id: str
    ward_id: str
    source_authority: str
    source_object_key: str
    source_filename: str
    source_url: str
    source_sha256: str
    reconstruction_fingerprint: str
    pipeline_version: str
    calibration_id: str
    working_crs: str
    georeference_method: str
    affine_coefficients: list[float]
    control_points: list[GeoreferenceControlResult]
    georeference_rmse_m: float
    georeference_max_error_m: float
    georeference_tolerance_m: float
    native_inspection: NativePdfInspection
    working_object_key: str
    qa_object_key: str
    audit_object_key: str
    working_sha256: str
    qa_sha256: str
    audit_sha256: str
    feature_count: int
    drain_count: int
    structure_count: int
    label_count: int
    bounds_working: list[float]
    bounds_wgs84: list[float]
    confidence_summary: dict[str, int]
    status: ReconstructionStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime


class ReconstructionResult(BaseModel):
    reconstruction_id: UUID
    created: bool
    status: ReconstructionStatus
    drain_count: int
    structure_count: int
    label_count: int
    georeference_rmse_m: float


class ReconstructionReviewCreate(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field(min_length=2, max_length=200)
    reviewer_type: ReviewerType
    notes: str = Field(min_length=3, max_length=4000)
    source_alignment_checked: bool
    drain_symbology_checked: bool
    feature_placement_checked: bool
    missing_attributes_not_invented: bool

    @property
    def all_checks_passed(self) -> bool:
        return all(
            (
                self.source_alignment_checked,
                self.drain_symbology_checked,
                self.feature_placement_checked,
                self.missing_attributes_not_invented,
            )
        )


class ReconstructionReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: UUID
    reconstruction_id: UUID
    decision: ReviewDecision
    reviewer: str
    reviewer_type: ReviewerType
    notes: str
    checklist: dict[str, bool]
    created_at: datetime


class ReconstructionReadiness(BaseModel):
    city_id: str
    total_reconstructions: int
    pending_review: int
    approved_reconstructions: int
    rejected_reconstructions: int
    geographically_valid: int
    native_vector_text_reconstructions: int
    total_drains: int
    total_structures: int
    total_labels: int
    completion_gate_passed: bool
    completion_gate_reason: str
    qa_viewer_path: str = "/reconstruction/qa"

