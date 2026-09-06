from types import SimpleNamespace
from uuid import uuid4

import pytest

from floodguard.drainage.serialization import sha256
from floodguard.drainage.source_loader import load_pilot_sources
from floodguard.reconstruction.contracts import ReconstructionStatus
from floodguard.spatial.object_store import MemorySpatialObjectStore
from tests.drain_model_fixtures import sources


def loader_fixture():
    info, raw, wards, _ = sources()
    store = MemorySpatialObjectStore()
    store.raw_objects["pdf"] = b"PDF source test"
    store.spatial_objects.update({"working": raw, "qa": b"{}", "audit": b"{}", "wards": wards})
    record = SimpleNamespace(
        ward_id="7",
        status=ReconstructionStatus.APPROVED,
        reconstruction_id=info.reconstruction_id,
        working_crs=info.working_crs,
        source_object_key="pdf",
        source_sha256=sha256(store.raw_objects["pdf"]),
        working_object_key="working",
        working_sha256=sha256(raw),
        qa_object_key="qa",
        qa_sha256=sha256(b"{}"),
        audit_object_key="audit",
        audit_sha256=sha256(b"{}"),
    )
    layer = SimpleNamespace(
        source_category="WARD_BOUNDARY",
        working_crs=info.working_crs,
        normalization_id=info.normalization_id,
        normalized_object_key="wards",
        normalized_sha256=sha256(wards),
    )
    recon = SimpleNamespace(object_store=store, list_reconstructions=lambda **kw: [record])
    spatial = SimpleNamespace(
        object_store=store, list_layers=lambda **kw: [layer], qa_geojson=lambda identity: b"{}"
    )
    return recon, spatial, record, layer, store


def test_source_loader_binds_exact_approved_input_versions() -> None:
    recon, spatial, record, layer, _ = loader_fixture()
    info, raw, wards = load_pilot_sources(
        recon,
        spatial,
        city_id="kolkata",
        ward_id="7",
        max_bytes=100000,
        reconstruction_id=record.reconstruction_id,
        normalization_id=layer.normalization_id,
    )
    assert info.evidence_scope.value == "REAL_PILOT_PROVISIONAL"
    assert sha256(raw) == info.reconstruction_source.sha256
    assert sha256(wards) == info.ward_source.sha256


@pytest.mark.parametrize(
    "case",
    [
        "unapproved",
        "wrong_ward",
        "wrong_reconstruction",
        "old_wards",
        "wrong_normalization",
        "pdf",
        "working",
        "qa",
        "audit",
        "wards",
    ],
)
def test_source_loader_rejects_unapproved_stale_or_corrupt_inputs(case) -> None:
    recon, spatial, record, _, store = loader_fixture()
    kwargs = {}
    if case == "unapproved":
        record.status = "UNREVIEWED"
    elif case == "wrong_ward":
        record.ward_id = "8"
    elif case == "wrong_reconstruction":
        kwargs["reconstruction_id"] = uuid4()
    elif case == "wrong_normalization":
        kwargs["normalization_id"] = uuid4()
    elif case == "old_wards":

        def reject(identity):
            raise ValueError("Historical pipeline is not current")

        spatial.qa_geojson = reject
    elif case == "pdf":
        store.raw_objects["pdf"] += b"corrupt"
    else:
        store.spatial_objects[case] += b"corrupt"
    with pytest.raises(ValueError):
        load_pilot_sources(
            recon, spatial, city_id="kolkata", ward_id="7", max_bytes=100000, **kwargs
        )
