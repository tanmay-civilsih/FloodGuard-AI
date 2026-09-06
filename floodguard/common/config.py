"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOODGUARD_", env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    operators_json: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite:///./floodguard.db"

    object_store_endpoint: str = "localhost:9000"
    object_store_access_key: str = "floodguard"
    object_store_secret_key: str = "floodguard_dev_only"
    object_store_secure: bool = False
    raw_bucket: str = "floodguard-raw"
    spatial_bucket: str = "floodguard-spatial"

    harvest_max_object_bytes: int = Field(default=128 * 1024 * 1024, ge=1)
    harvest_max_total_bytes: int = Field(default=768 * 1024 * 1024, ge=1)
    harvest_max_resources_per_source: int = Field(default=250, ge=1, le=5000)
    harvest_timeout_seconds: float = Field(default=60.0, gt=0, le=600)

    working_crs: str = "EPSG:32645"
    spatial_alignment_tolerance_m: float = Field(default=0.05, ge=0, le=10)
    rainfall_conservation_tolerance: float = Field(default=1e-9, ge=0, le=1e-2)
    spatial_max_object_bytes: int = Field(default=128 * 1024 * 1024, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
