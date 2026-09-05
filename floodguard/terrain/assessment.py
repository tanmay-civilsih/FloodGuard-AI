"""Bind an operator's terrain assessment to one exact, unassessed SRTM package."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from floodguard.terrain.contracts import (
    AssessmentStatus,
    EvidenceText,
    MultiLevelStructure,
    TerrainInput,
    TerrainIntervention,
    TerrainPackage,
    VerticalValidation,
)
from floodguard.terrain.grid import package_bytes, sha256

ASSESSMENT_FILENAME = "terrain-assessment.json"
MAX_ASSESSMENT_BYTES = 1_000_000
ReviewEvidence = Annotated[str, Field(min_length=10, max_length=2000)]


class TerrainAssessment(TerrainInput):
    assessment_version: Literal["sequence-6-terrain-assessment-v1"] = (
        "sequence-6-terrain-assessment-v1"
    )
    base_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_by: str = Field(min_length=1, max_length=200)
    reviewed_at: AwareDatetime
    datum_transform_status: Literal["UNRESOLVED", "COMPATIBLE"] = "UNRESOLVED"
    local_vertical_datum: str | None = Field(default=None, min_length=1, max_length=160)
    vertical_reference_evidence: ReviewEvidence
    surface_use_evidence: ReviewEvidence
    depression_assessment: AssessmentStatus = AssessmentStatus.NOT_ASSESSED
    depression_evidence: ReviewEvidence
    multi_level_assessment: AssessmentStatus = AssessmentStatus.NOT_ASSESSED
    multi_level_evidence: ReviewEvidence
    interventions: list[TerrainIntervention] = Field(default_factory=list)
    multi_level_structures: list[MultiLevelStructure] = Field(default_factory=list)
    vertical_validation: VerticalValidation
    limitations: list[EvidenceText] = Field(min_length=1)

    @field_validator("reviewed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence(self) -> TerrainAssessment:
        if self.datum_transform_status == "COMPATIBLE" and self.local_vertical_datum != "EGM96":
            raise ValueError("SRTM compatibility requires a documented local EGM96 reference")
        validation = self.vertical_validation
        if not validation.control_points and (
            validation.control_point_count or validation.rmse_m is not None
        ):
            raise ValueError("assessment control statistics require actual control observations")
        return self


def decode_assessment(payload: bytes) -> TerrainAssessment:
    if len(payload) > MAX_ASSESSMENT_BYTES:
        raise ValueError("terrain assessment exceeds the 1 MB input limit")

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate assessment JSON key: {key}")
            result[key] = value
        return result

    try:
        # PowerShell UTF-8 exports may contain a byte-order mark.
        data: Any = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("terrain assessment must be UTF-8 JSON") from exc
    return TerrainAssessment.model_validate(data)


def assessment_bytes(assessment: TerrainAssessment) -> bytes:
    return json.dumps(
        assessment.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def assessment_template(base_package_sha256: str) -> dict[str, Any]:
    """Export an intentionally incomplete form; blank evidence cannot be imported."""
    return {
        "assessment_version": "sequence-6-terrain-assessment-v1",
        "base_package_sha256": base_package_sha256,
        "reviewed_by": "",
        "reviewed_at": None,
        "datum_transform_status": "UNRESOLVED",
        "local_vertical_datum": None,
        "vertical_reference_evidence": "",
        "surface_use_evidence": "",
        "depression_assessment": "NOT_ASSESSED",
        "depression_evidence": "",
        "multi_level_assessment": "NOT_ASSESSED",
        "multi_level_evidence": "",
        "interventions": [],
        "multi_level_structures": [],
        "vertical_validation": {
            "control_points": [],
            "road_sag_validation": "NOT_ASSESSED",
            "underpass_validation": "NOT_ASSESSED",
            "drain_rim_elevation_consistency": "NOT_ASSESSED",
            "limitations": [],
        },
        "limitations": [],
    }


def apply_assessment(base: TerrainPackage, assessment: TerrainAssessment) -> TerrainPackage:
    if sha256(package_bytes(base)) != assessment.base_package_sha256:
        raise ValueError("assessment does not match this source, pilot extent or grid")
    data = base.model_dump(mode="json")
    reviewed = assessment.model_dump(mode="json")
    for name in (
        "datum_transform_status", "depression_assessment", "multi_level_assessment",
        "interventions", "multi_level_structures", "vertical_validation",
    ):
        data[name] = reviewed[name]
    limitations = list(base.limitations)
    if assessment.datum_transform_status == "COMPATIBLE":
        limitations.remove(
            "EGM96 compatibility with local drain, stage and survey references is unresolved."
        )
    if (
        assessment.depression_assessment is not AssessmentStatus.NOT_ASSESSED
        and assessment.multi_level_assessment is not AssessmentStatus.NOT_ASSESSED
    ):
        limitations.remove("Depression and multi-level structure assessments remain NOT_ASSESSED.")
    data["limitations"] = [
        *limitations,
        *assessment.limitations,
        "Terrain assessment statements are operator-supplied and not independently verified; "
        "they do not grant hydraulic validation or certify street-scale elevations.",
    ]
    return TerrainPackage.model_validate(data)
