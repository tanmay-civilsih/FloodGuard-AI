"""Typed contracts for the Sequence-2 data source registry."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from floodguard.contracts.time import UtcDateTime

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AccessClass(StrEnum):
    OPEN_AUTOMATED = "OPEN_AUTOMATED"
    OPEN_MANUAL = "OPEN_MANUAL"
    PUBLIC_VIEW_ONLY = "PUBLIC_VIEW_ONLY"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    COMMERCIAL_OPTIONAL = "COMMERCIAL_OPTIONAL"
    UNKNOWN = "UNKNOWN"


class SourceCategory(StrEnum):
    DRAINAGE_MAP = "DRAINAGE_MAP"
    WARD_BOUNDARY = "WARD_BOUNDARY"
    CATCHMENT = "CATCHMENT"
    WATER_BODY = "WATER_BODY"
    OPENSTREETMAP = "OPENSTREETMAP"
    ELEVATION = "ELEVATION"
    SATELLITE_IMAGERY = "SATELLITE_IMAGERY"
    RAINFALL_OBSERVATION = "RAINFALL_OBSERVATION"
    HISTORICAL_RAINFALL = "HISTORICAL_RAINFALL"
    ATMOSPHERIC_STATE = "ATMOSPHERIC_STATE"
    FLOOD_OBSERVATION = "FLOOD_OBSERVATION"
    RAINFALL_NOWCAST = "RAINFALL_NOWCAST"
    RADAR = "RADAR"
    HYDRAULIC_BOUNDARY = "HYDRAULIC_BOUNDARY"
    LIDAR = "LIDAR"
    PUMP_SCADA = "PUMP_SCADA"
    DRAIN_SENSOR = "DRAIN_SENSOR"
    CCTV = "CCTV"
    TRAFFIC = "TRAFFIC"


class AccessMethod(StrEnum):
    HTTP = "HTTP"
    CKAN = "CKAN"
    REST = "REST"
    STAC = "STAC"
    WMS = "WMS"
    WFS = "WFS"
    WMTS = "WMTS"
    OVERPASS = "OVERPASS"
    PBF_EXTRACT = "PBF_EXTRACT"
    PORTAL = "PORTAL"
    AUTHORIZED_FEED = "AUTHORIZED_FEED"
    MANUAL_TRANSFER = "MANUAL_TRANSFER"


class AuthenticationType(StrEnum):
    NONE = "NONE"
    BEARER_TOKEN = "BEARER_TOKEN"
    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    USER_ACCOUNT = "USER_ACCOUNT"
    EARTHDATA_LOGIN = "EARTHDATA_LOGIN"
    UNKNOWN = "UNKNOWN"


class AuthorityLevel(StrEnum):
    MUNICIPAL_PRIMARY = "MUNICIPAL_PRIMARY"
    STATE_GOVERNMENT = "STATE_GOVERNMENT"
    NATIONAL_GOVERNMENT = "NATIONAL_GOVERNMENT"
    INTERNATIONAL_AGENCY = "INTERNATIONAL_AGENCY"
    COMMUNITY = "COMMUNITY"
    COMMERCIAL = "COMMERCIAL"
    UNKNOWN = "UNKNOWN"


class SourceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    PLANNED = "PLANNED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class SourceBase(BaseModel):
    provider: NonEmpty
    dataset_name: NonEmpty
    city_id: NonEmpty
    category: SourceCategory
    endpoint: NonEmpty
    access_method: AccessMethod
    format: NonEmpty
    licence: NonEmpty
    redistribution_policy: NonEmpty
    automation_allowed: bool
    access_class: AccessClass
    authentication_type: AuthenticationType = AuthenticationType.NONE
    credential_ref: str | None = None
    authority_level: AuthorityLevel
    horizontal_crs: str | None = None
    vertical_datum: str | None = None
    spatial_resolution: str | None = None
    temporal_resolution: str | None = None
    refresh_policy: NonEmpty
    fallback_source_id: UUID | None = None
    fallback_strategy: NonEmpty
    status: SourceStatus
    terms_url: str | None = None
    last_verified_at: UtcDateTime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_access_governance(self) -> "SourceBase":
        if self.access_class is AccessClass.OPEN_AUTOMATED and not self.automation_allowed:
            raise ValueError("OPEN_AUTOMATED sources must allow automation")
        if self.access_class in {
            AccessClass.OPEN_MANUAL,
            AccessClass.PUBLIC_VIEW_ONLY,
            AccessClass.UNKNOWN,
        } and self.automation_allowed:
            raise ValueError(f"{self.access_class} sources cannot be marked automation_allowed")
        if self.authentication_type is AuthenticationType.NONE and self.credential_ref is not None:
            raise ValueError("credential_ref requires a non-NONE authentication_type")
        if (
            self.access_class is AccessClass.AUTHORIZATION_REQUIRED
            and self.authentication_type is not AuthenticationType.NONE
            and self.credential_ref is None
        ):
            raise ValueError("authorization-required sources must declare a credential_ref")
        if self.credential_ref is not None:
            allowed_prefixes = ("env://", "docker-secret://", "secret://")
            if not self.credential_ref.startswith(allowed_prefixes):
                raise ValueError("credential_ref must be a reference, never a raw credential")
            if any(token in self.credential_ref for token in ("=", " ", "\n", "\t")):
                raise ValueError("credential_ref appears to contain credential material")
        return self


class SourceCreate(SourceBase):
    source_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def validate_fallback(self) -> "SourceCreate":
        if self.fallback_source_id == self.source_id:
            raise ValueError("source cannot reference itself as fallback")
        return self


class SourceReplace(SourceBase):
    pass


class SourceRead(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    source_id: UUID
    created_at: UtcDateTime
    updated_at: UtcDateTime


class RegistryReadiness(BaseModel):
    catalogue_complete: bool
    required_categories: list[SourceCategory]
    documented_categories: list[SourceCategory]
    missing_categories: list[SourceCategory]
    available_categories: list[SourceCategory]
    blocked_or_planned_categories: list[SourceCategory]
    total_sources: int
