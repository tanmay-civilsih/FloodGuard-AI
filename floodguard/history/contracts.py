"""Additive v1 historical contracts; existing forcing serialization stays unchanged."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from floodguard.contracts.time import UtcDateTime
from floodguard.forcing.contracts import Grid, Input, Text
from floodguard.twin.contracts import BlobReference

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SourceAvailabilityRecord(Input):
    schema_version: Literal["source-availability-v1"] = "source-availability-v1"
    source_id: UUID
    dataset_version_id: UUID
    source_revision: Text
    acquired_at: UtcDateTime
    valid_from: UtcDateTime
    valid_to: UtcDateTime
    source_issue_time: UtcDateTime | None = None
    provider_available_at: UtcDateTime | None = None
    availability_status: Literal["VERIFIED", "ESTIMATED", "UNKNOWN"]
    availability_evidence: Text
    estimated_latency_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def coherent(self) -> SourceAvailabilityRecord:
        if self.valid_to <= self.valid_from:
            raise ValueError("source valid interval must have positive duration")
        if self.source_issue_time is not None and self.source_issue_time > self.acquired_at:
            raise ValueError("source issue cannot follow acquisition")
        if self.availability_status == "VERIFIED":
            if self.provider_available_at is None or self.estimated_latency_seconds is not None:
                raise ValueError("verified availability requires a time and no estimated latency")
        elif self.availability_status == "UNKNOWN":
            if self.provider_available_at is not None or self.estimated_latency_seconds is not None:
                raise ValueError("unknown availability cannot assert a time or latency")
        elif self.estimated_latency_seconds is None:
            raise ValueError("estimated availability requires a declared latency")
        if self.provider_available_at is not None:
            if self.provider_available_at > self.acquired_at:
                raise ValueError("availability cannot follow acquisition")
            if self.source_issue_time and self.source_issue_time > self.provider_available_at:
                raise ValueError("availability cannot precede source issue")
        return self

    def eligible_at(self, issue: datetime) -> bool:
        return (
            self.availability_status == "VERIFIED"
            and self.provider_available_at is not None
            and self.provider_available_at <= issue
            and (self.source_issue_time is None or self.source_issue_time <= issue)
        )


class ObservationRecord(Input):
    schema_version: Literal["observation-v1"] = "observation-v1"
    observation_id: Text
    station_or_geometry_id: Text
    quantity: Literal["RAINFALL_RATE", "RAINFALL_ACCUMULATION", "FLOOD_DEPTH", "WATER_LEVEL"]
    value: float | None
    units: Literal["mm/h", "mm", "m"]
    interval_start: UtcDateTime
    interval_end: UtcDateTime
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    evidence_kind: Literal["MEASURED", "REANALYSIS", "SATELLITE_ESTIMATE", "FORECAST", "SYNTHETIC"]
    support: Literal["POINT", "GRID_CELL_ESTIMATE"]
    native_resolution_m: float = Field(gt=0)
    qc: Literal["VALID", "MISSING", "REJECTED"]
    uncertainty: float | None = Field(default=None, ge=0)
    vertical_reference: Text | None = None
    source: SourceAvailabilityRecord

    @model_validator(mode="after")
    def coherent(self) -> ObservationRecord:
        if self.interval_end <= self.interval_start:
            raise ValueError("observation interval must have positive duration")
        if not (
            self.source.valid_from
            <= self.interval_start
            < self.interval_end
            <= self.source.valid_to
        ):
            raise ValueError("observation lies outside declared source valid interval")
        expected = {
            "RAINFALL_RATE": "mm/h",
            "RAINFALL_ACCUMULATION": "mm",
            "FLOOD_DEPTH": "m",
            "WATER_LEVEL": "m",
        }[self.quantity]
        if self.units != expected:
            raise ValueError("quantity and units disagree")
        if (self.qc == "VALID") != (self.value is not None):
            raise ValueError("missing/rejected observations must have null values")
        if self.value is not None and self.quantity != "WATER_LEVEL" and self.value < 0:
            raise ValueError("rainfall and flood depth must be nonnegative")
        if self.quantity in {"WATER_LEVEL", "FLOOD_DEPTH"} and self.vertical_reference is None:
            raise ValueError("water level/depth needs a vertical or local depth reference")
        return self

    def eligible_predictor(self, issue: datetime) -> bool:
        return (
            self.qc == "VALID"
            and self.source.eligible_at(issue)
            and self.evidence_kind != "SYNTHETIC"
            and (self.evidence_kind == "FORECAST" or self.interval_end <= issue)
        )


class PowerSelection(Input):
    latitude: float = Field(ge=-89, le=89)
    longitude: float = Field(ge=-179, le=179)
    start: UtcDateTime
    end: UtcDateTime

    @model_validator(mode="after")
    def bounded_days(self) -> PowerSelection:
        if not timedelta(days=1) <= self.end - self.start <= timedelta(days=31):
            raise ValueError("POWER selection must span 1 to 31 complete UTC days")
        if any(t.hour or t.minute or t.second or t.microsecond for t in (self.start, self.end)):
            raise ValueError("POWER selection must use midnight UTC day boundaries")
        if self.start.year < 2001:
            raise ValueError("hourly POWER archive starts in 2001")
        return self


class EventRequest(Input):
    schema_version: Literal["history-request-v1"] = "history-request-v1"
    event_key: Text
    title: Text
    city_id: Text = "kolkata"
    catchment_id: Text
    catchment_status: Literal["VERIFIED", "STUDY_AREA"]
    catchment_evidence: Text
    selection: PowerSelection
    dataset_version_id: UUID
    raw_object_id: UUID
    twin_id: UUID
    replay_grid: Grid
    event_start: UtcDateTime
    event_end: UtcDateTime
    antecedent_hours: int = Field(ge=0, le=24, default=3)
    spatial_application: Literal["UNIFORM_REGIONAL_ESTIMATE"] = "UNIFORM_REGIONAL_ESTIMATE"
    spatial_application_reason: Text
    evidence_gaps: list[Text] = Field(min_length=1, max_length=50)
    infrastructure_assumptions: list[Text] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def event_window(self) -> EventRequest:
        start, end = self.event_start, self.event_end
        if not self.selection.start <= start < end <= self.selection.end:
            raise ValueError("event must lie inside acquired selection")
        if any(t.minute or t.second or t.microsecond for t in (start, end)):
            raise ValueError("event uses complete hourly intervals")
        if start - timedelta(hours=self.antecedent_hours) < self.selection.start:
            raise ValueError("selection does not cover declared antecedent window")
        return self


class WindowReference(Input):
    start: UtcDateTime
    end: UtcDateTime
    forcing_package_id: UUID | None = None
    missing_intervals: int = Field(ge=0)
    status: Literal["PREPARED", "MISSING_RAIN"]
    blockers: list[Text]

    @model_validator(mode="after")
    def coherent(self) -> WindowReference:
        if not timedelta(0) < self.end - self.start <= timedelta(hours=3):
            raise ValueError("replay windows must be positive and at most three hours")
        if self.status == "PREPARED":
            if self.forcing_package_id is None or self.missing_intervals:
                raise ValueError("prepared window needs a package and complete rainfall")
        elif self.forcing_package_id is not None or not self.missing_intervals:
            raise ValueError("missing rainfall window must not publish a forcing package")
        return self


class HistoricalEventManifest(Input):
    schema_version: Literal["historical-event-v1"] = "historical-event-v1"
    historical_event_id: UUID
    event_key: Text
    title: Text
    city_id: Text
    catchment_id: Text
    event_start: UtcDateTime
    event_end: UtcDateTime
    timezone: Literal["UTC"] = "UTC"
    twin_id: UUID
    dataset_version_id: UUID
    raw_object: BlobReference
    availability: SourceAvailabilityRecord
    windows: list[WindowReference]
    state_continuity: Literal["NOT_INITIALIZED_RAINFALL_ONLY"] = "NOT_INITIALIZED_RAINFALL_ONLY"
    artifacts: dict[str, BlobReference]
    software_version: Text
    software_source_sha256: Digest
    scientific_label: Literal["COARSE_REANALYSIS_RAINFALL_REPLAY"] = (
        "COARSE_REANALYSIS_RAINFALL_REPLAY"
    )
    measured_flood_validation: Literal[False] = False
    strict_backtest_eligible: Literal[False] = False
    evidence_gaps: list[Text]

    @model_validator(mode="after")
    def contiguous(self) -> HistoricalEventManifest:
        cursor = self.event_start
        ids = []
        for window in self.windows:
            if window.start != cursor:
                raise ValueError("event windows must be ordered and contiguous")
            cursor = window.end
            if window.forcing_package_id is not None:
                ids.append(window.forcing_package_id)
        if not self.windows or cursor != self.event_end or len(ids) != len(set(ids)):
            raise ValueError("event windows must cover event with distinct package identities")
        return self


class EventSplit(Input):
    historical_event_id: UUID
    storm_group: Text
    role: Literal["TRAIN", "TUNE", "TEST"]
    start: UtcDateTime
    end: UtcDateTime
    geography: Text

    @model_validator(mode="after")
    def positive(self) -> EventSplit:
        if self.end <= self.start:
            raise ValueError("split event must have a positive duration")
        return self


class EvaluationDatasetDefinition(Input):
    schema_version: Literal["evaluation-dataset-v1"] = "evaluation-dataset-v1"
    target_definition: Text
    feature_definition: Text
    label_quality: Text
    events: list[EventSplit] = Field(min_length=3)
    base_model_training_cutoff: UtcDateTime | None = None

    @model_validator(mode="after")
    def separated(self) -> EvaluationDatasetDefinition:
        if {e.role for e in self.events} != {"TRAIN", "TUNE", "TEST"}:
            raise ValueError("all three event split roles are required")
        if len({e.historical_event_id for e in self.events}) != len(self.events):
            raise ValueError("an event cannot appear in multiple splits")
        groups: dict[str, str] = {}
        for e in self.events:
            if e.storm_group in groups and groups[e.storm_group] != e.role:
                raise ValueError("a whole storm group cannot cross splits")
            groups[e.storm_group] = e.role
            if (
                e.role != "TRAIN"
                and self.base_model_training_cutoff
                and e.start <= self.base_model_training_cutoff
            ):
                raise ValueError("evaluation overlaps base-model training history")
        for earlier, later in (("TRAIN", "TUNE"), ("TUNE", "TEST")):
            if max(e.end for e in self.events if e.role == earlier) > min(
                e.start for e in self.events if e.role == later
            ):
                raise ValueError("whole-event splits must be chronological and nonoverlapping")
        return self

    def split_hash(self) -> str:
        from floodguard.drainage.serialization import canonical_bytes, sha256

        return sha256(canonical_bytes(self.model_dump(mode="json")))
