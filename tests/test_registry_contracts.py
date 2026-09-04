import pytest
from pydantic import ValidationError

from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceCreate,
    SourceStatus,
)

BASE = {
    "provider": "provider",
    "dataset_name": "dataset",
    "city_id": "kolkata",
    "category": SourceCategory.DRAINAGE_MAP,
    "endpoint": "https://example.com/data",
    "access_method": AccessMethod.HTTP,
    "format": "PDF",
    "licence": "public",
    "redistribution_policy": "retain provenance",
    "automation_allowed": True,
    "access_class": AccessClass.OPEN_AUTOMATED,
    "authentication_type": AuthenticationType.NONE,
    "authority_level": AuthorityLevel.MUNICIPAL_PRIMARY,
    "refresh_policy": "manual",
    "fallback_strategy": "use cached immutable version",
    "status": SourceStatus.AVAILABLE,
}


def test_open_automated_must_allow_automation() -> None:
    with pytest.raises(ValidationError):
        SourceCreate(**(BASE | {"automation_allowed": False}))


def test_raw_credentials_are_rejected() -> None:
    values = BASE | {
        "access_class": AccessClass.AUTHORIZATION_REQUIRED,
        "authentication_type": AuthenticationType.BEARER_TOKEN,
        "credential_ref": "raw-secret-token",
    }
    with pytest.raises(ValidationError):
        SourceCreate(**values)


def test_credential_reference_is_allowed() -> None:
    values = BASE | {
        "access_class": AccessClass.AUTHORIZATION_REQUIRED,
        "authentication_type": AuthenticationType.BEARER_TOKEN,
        "credential_ref": "env://TOKEN",
    }
    assert SourceCreate(**values).credential_ref == "env://TOKEN"
