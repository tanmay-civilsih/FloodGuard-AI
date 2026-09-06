"""Source facts may be prefilled; site-specific review must remain human evidence."""

import json

import pytest
from pydantic import ValidationError

from floodguard.terrain.assessment import assessment_template, decode_assessment


def test_template_prefills_source_constraints_but_remains_unimportable() -> None:
    template = assessment_template("a" * 64)
    assert template["datum_transform_status"] == "UNRESOLVED"
    assert template["local_vertical_datum"] is None
    assert "EGM96" in template["vertical_reference_evidence"]
    assert "coarse" in template["surface_use_evidence"].lower()
    assert template["depression_assessment"] == "NOT_ASSESSED"
    assert template["multi_level_assessment"] == "NOT_ASSESSED"
    assert template["vertical_validation"]["limitations"]
    assert template["limitations"]

    with pytest.raises(ValidationError) as failure:
        decode_assessment(json.dumps(template).encode("utf-8"))
    locations = {tuple(error["loc"]) for error in failure.value.errors()}
    assert ("reviewed_by",) in locations
    assert ("reviewed_at",) in locations
    assert ("depression_evidence",) in locations
    assert ("multi_level_evidence",) in locations
    assert ("vertical_reference_evidence",) not in locations
    assert ("surface_use_evidence",) not in locations
    assert ("vertical_validation", "limitations") not in locations
    assert ("limitations",) not in locations
