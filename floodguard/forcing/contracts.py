"""Strict forcing inputs: explicit support, provenance, units and interpolation."""

from __future__ import annotations

import itertools
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from floodguard.contracts.time import UtcDateTime
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.twin.contracts import BlobReference

POLICY: Literal["sequence-10-forcing-v1"] = "sequence-10-forcing-v1"
VOLUME_TOLERANCE = 1e-10
MAX_VALUES = 2_000_000
Text = Annotated[str, Field(min_length=1, max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Mode(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    REPLAY = "REPLAY"
    EXTERNAL_FORECAST = "EXTERNAL_FORECAST"
    RADAR_NOWCAST = "RADAR_NOWCAST"
    RADAR_NWP_BLEND = "RADAR_NWP_BLEND"


class Coverage(StrEnum):
    FULL = "FULL_COVERAGE"
    PARTIAL = "PARTIAL_COVERAGE"
    BLENDED = "BLENDED_EXTENSION"
    INSUFFICIENT = "INSUFFICIENT"


class Source(Input):
    source: Text
    version: Text
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality: Literal["SOURCE_DECLARED", "PROVISIONAL", "SYNTHETIC"]
    method: Text


class Grid(Input):
    horizontal_crs: Text
    x_edges_m: list[float] = Field(min_length=2, max_length=2049)
    y_edges_m: list[float] = Field(min_length=2, max_length=2049)

    @model_validator(mode="after")
    def regular_metric(self) -> Grid:
        validate_metric_working_crs(self.horizontal_crs)
        for edges in (self.x_edges_m, self.y_edges_m):
            delta = np.diff(edges)
            if not np.all(np.isfinite(delta)) or np.any(delta <= 0):
                raise ValueError("grid edges must be finite and strictly increasing")
            if not np.allclose(delta, delta[0], rtol=1e-12, atol=0):
                raise ValueError("RainCube requires a regular rectilinear grid")
        if (len(self.x_edges_m) - 1) * (len(self.y_edges_m) - 1) > MAX_VALUES:
            raise ValueError("rainfall grid exceeds prototype size bound")
        return self


class RainMember(Input):
    member_id: Text
    rain_rate_mm_h: list[list[list[float]]]


def increasing(times: list[datetime]) -> None:
    if any(b <= a for a, b in itertools.pairwise(times)):
        raise ValueError(
            "series times must strictly increase; duplicates/gaps need an explicit adapter"
        )


class RainInput(Input):
    mode: Mode
    issue_time: UtcDateTime
    time_edges: list[UtcDateTime] = Field(min_length=2, max_length=1001)
    grid: Grid
    native_spatial_resolution_m: float = Field(gt=0)
    effective_spatial_resolution_m: float = Field(gt=0)
    source: Source
    processing_lineage: list[Source] = Field(default_factory=list, max_length=20)
    ensemble_definition: Text
    members: list[RainMember] = Field(min_length=1, max_length=20)
    units: Literal["mm/h"] = "mm/h"
    temporal_interpretation: Literal["INTERVAL_MEAN"] = "INTERVAL_MEAN"

    @model_validator(mode="after")
    def valid_rain(self) -> RainInput:
        increasing(self.time_edges)
        if self.effective_spatial_resolution_m < self.native_spatial_resolution_m:
            raise ValueError("effective resolution cannot be finer than native information")
        if len({m.member_id for m in self.members}) != len(self.members):
            raise ValueError("ensemble members must be unique")
        shape = (
            len(self.time_edges) - 1,
            len(self.grid.y_edges_m) - 1,
            len(self.grid.x_edges_m) - 1,
        )
        if int(np.prod(shape)) * len(self.members) > MAX_VALUES:
            raise ValueError("rainfall cube exceeds prototype size bound")
        for member in self.members:
            rates = np.asarray(member.rain_rate_mm_h, dtype=np.float64)
            if rates.shape != shape or not np.all(np.isfinite(rates)) or np.any(rates < 0):
                raise ValueError("rainfall must be finite, nonnegative and match time/y/x shape")
        if self.mode is Mode.SYNTHETIC and self.source.quality != "SYNTHETIC":
            raise ValueError("synthetic rain must declare synthetic quality")
        if self.mode is not Mode.SYNTHETIC and self.source.quality == "SYNTHETIC":
            raise ValueError("synthetic rain cannot be labelled operational or replay data")
        if self.mode in {Mode.RADAR_NOWCAST, Mode.RADAR_NWP_BLEND}:
            minimum = 2 if self.mode is Mode.RADAR_NWP_BLEND else 1
            if len(self.processing_lineage) < minimum:
                raise ValueError("processed radar/blend requires explicit upstream source lineage")
            identities = {(s.source, s.version, s.sha256) for s in self.processing_lineage}
            if len(identities) != len(self.processing_lineage) or any(
                s.quality == "SYNTHETIC" for s in self.processing_lineage
            ):
                raise ValueError("operational radar lineage must be distinct and nonsynthetic")
        if self.mode is not Mode.REPLAY and self.time_edges[0] < self.issue_time:
            raise ValueError("forecast/synthetic rainfall cannot precede its issue time")
        return self


class BoundarySeries(Input):
    boundary_id: Text
    kind: Literal["RIVER_STAGE", "CANAL_STAGE", "TIDE_LEVEL", "OUTFALL_STAGE"]
    time: list[UtcDateTime] = Field(min_length=2, max_length=10001)
    stage_m: list[float] = Field(min_length=2, max_length=10001)
    vertical_datum: Text
    vertical_unit: Literal["m"] = "m"
    vertical_transform_status: Literal["COMPATIBLE", "TRANSFORMED", "UNRESOLVED"]
    target_vertical_datum: Text | None = None
    vertical_offset_m: float | None = None
    transform_method: Text | None = None
    interpolation_method: Literal["LINEAR", "STEP_HOLD"]
    source: Source

    @model_validator(mode="after")
    def coherent(self) -> BoundarySeries:
        increasing(self.time)
        if len(self.time) != len(self.stage_m):
            raise ValueError("stage values must match times")
        if self.vertical_transform_status == "TRANSFORMED":
            if (
                self.target_vertical_datum is None
                or self.vertical_offset_m is None
                or self.transform_method is None
            ):
                raise ValueError("transformed stage needs target, offset and evidenced method")
        elif any(
            v is not None
            for v in (self.target_vertical_datum, self.vertical_offset_m, self.transform_method)
        ):
            raise ValueError("untransformed stage cannot carry an implicit transform")
        return self


class ControlSeries(Input):
    asset_id: Text
    asset_kind: Literal["PUMP", "GATE", "SLUICE"]
    control_kind: Literal["DISCRETE_STATE", "CONTINUOUS_FRACTION"]
    time: list[UtcDateTime] = Field(min_length=2, max_length=10001)
    operating_state: list[Literal["ON", "OFF", "AVAILABLE", "UNAVAILABLE", "OPEN", "CLOSED"]]
    control_value: list[Annotated[float, Field(ge=0, le=1)]]
    interpolation_method: Literal["LINEAR", "STEP_HOLD"]
    source: Source

    @model_validator(mode="after")
    def coherent(self) -> ControlSeries:
        increasing(self.time)
        if len(self.time) != len(self.operating_state) or len(self.time) != len(self.control_value):
            raise ValueError("control values/states must match times")
        if self.control_kind == "DISCRETE_STATE":
            if self.interpolation_method != "STEP_HOLD":
                raise ValueError("discrete controls require STEP_HOLD")
            for state, value in zip(self.operating_state, self.control_value, strict=True):
                if value != (1 if state in {"ON", "AVAILABLE", "OPEN"} else 0):
                    raise ValueError("discrete control state and value disagree")
        elif any(
            s in {"OFF", "UNAVAILABLE", "CLOSED"} and v != 0
            for s, v in zip(self.operating_state, self.control_value, strict=True)
        ):
            raise ValueError("disabled controls cannot have nonzero control fraction")
        return self


class ForcingWindow(Input):
    rain: RainInput
    boundaries: list[BoundarySeries] = Field(default_factory=list, max_length=1000)
    controls: list[ControlSeries] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique_series(self) -> ForcingWindow:
        if len({b.boundary_id for b in self.boundaries}) != len(self.boundaries):
            raise ValueError("duplicate hydraulic boundary")
        if len({c.asset_id for c in self.controls}) != len(self.controls):
            raise ValueError("duplicate operational control")
        return self


class BuildRequest(Input):
    twin_id: UUID
    issue_time: UtcDateTime
    valid_from: UtcDateTime
    valid_to: UtcDateTime
    target_grid: Grid
    forecast: ForcingWindow
    antecedent: ForcingWindow | None = None
    antecedent_missing_reason: Text | None = None

    @model_validator(mode="after")
    def explicit_window(self) -> BuildRequest:
        duration = (self.valid_to - self.valid_from).total_seconds()
        if not 0 < duration <= 10800 or self.valid_from < self.issue_time:
            raise ValueError("forecast must start at/after issue and last >0 to 3 hours")
        if self.forecast.rain.issue_time > self.issue_time:
            raise ValueError("package cannot consume rainfall issued in its future")
        if self.antecedent is None:
            if self.antecedent_missing_reason is None:
                raise ValueError("absent antecedent forcing needs an explicit reason")
        else:
            if self.antecedent_missing_reason is not None:
                raise ValueError("antecedent cannot be both present and missing")
            if (
                self.antecedent.rain.mode not in {Mode.REPLAY, Mode.SYNTHETIC}
                or self.antecedent.rain.time_edges[-1] != self.valid_from
                or self.antecedent.rain.issue_time > self.issue_time
            ):
                raise ValueError(
                    "antecedent must be historical/synthetic and end at forecast start"
                )
        return self


class Assessment(Input):
    coverage: Coverage
    common_valid_from: UtcDateTime | None
    common_valid_to: UtcDateTime | None
    hydraulic_use_eligible: bool
    blockers: list[str]
    antecedent_status: Literal["MISSING", "COMPLETE", "INCOMPLETE"]
    rainfall_volume_m3_by_member: dict[str, float]
    maximum_remap_relative_error: float
    final_human_acceptance_pending: Literal[True] = True
    operational_validation_claimed: Literal[False] = False


class Manifest(Input):
    policy: Literal["sequence-10-forcing-v1"] = POLICY
    forcing_package_id: UUID
    twin_id: UUID
    city_id: Text
    issue_time: UtcDateTime
    valid_from: UtcDateTime
    valid_to: UtcDateTime
    software_version: Text
    software_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifacts: dict[str, BlobReference]
    quality_summary: Assessment


class Product(Input):
    forcing_package_id: UUID
    twin_id: UUID
    city_id: str
    fingerprint: str
    manifest: BlobReference
    created_at: UtcDateTime


class BuildResult(Input):
    forcing_package_id: UUID
    created: bool
    quality_summary: Assessment
