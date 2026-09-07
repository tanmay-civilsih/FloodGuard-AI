"""Verified historical evidence, immutable replay packaging and independent recreation."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid5

from pyproj import Transformer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from floodguard.common.integrity import verified_payload
from floodguard.drainage.serialization import canonical_bytes, sha256
from floodguard.forcing.contracts import BuildRequest, Source
from floodguard.forcing.service import MAX_BYTES, ForcingService
from floodguard.harvester.contracts import DatasetVersionStatus
from floodguard.harvester.service import HarvesterService
from floodguard.history.contracts import (
    EventRequest,
    HistoricalEventManifest,
    ObservationRecord,
    SourceAvailabilityRecord,
    WindowReference,
)
from floodguard.history.models import HistoricalEventRecord
from floodguard.history.power import NAMESPACE, decode_power, selection_url
from floodguard.history.replay import validate_application, window_request
from floodguard.twin.contracts import BlobReference, ComponentRole


def identity(manifest: HistoricalEventManifest) -> UUID:
    data = manifest.model_dump(mode="json", exclude={"historical_event_id"})
    return uuid5(NAMESPACE, sha256(canonical_bytes(data)))


class HistoryService:
    def __init__(
        self,
        session: Session,
        forcing: ForcingService,
        harvester: HarvesterService,
    ) -> None:
        self.session, self.forcing, self.harvester = session, forcing, harvester

    def raw_inputs(
        self,
        request: EventRequest,
    ) -> tuple[BlobReference, SourceAvailabilityRecord, list[ObservationRecord], dict[str, Any]]:
        version = self.harvester.get_version(request.dataset_version_id)
        if (
            version.status is not DatasetVersionStatus.COMPLETE
            or version.city_id != request.city_id
        ):
            raise ValueError("event requires a complete dataset version in the same city")
        objects = [o for o in version.objects if o.object_id == request.raw_object_id]
        if len(objects) != 1:
            raise ValueError("raw object must belong to the declared dataset version")
        obj = objects[0]
        if obj.source_url != selection_url(request.selection):
            raise ValueError("raw object acquisition URL differs from the declared POWER selection")
        raw_ref = BlobReference(
            object_key=obj.object_key,
            sha256=obj.sha256,
            byte_size=obj.byte_size,
        )
        payload = verified_payload(
            self.forcing.store.read_raw(obj.object_key),
            expected_sha256=obj.sha256,
            expected_size=obj.byte_size,
            max_bytes=2_000_000,
        )
        availability = SourceAvailabilityRecord(
            source_id=version.source_id,
            dataset_version_id=version.dataset_version_id,
            source_revision=obj.sha256,
            acquired_at=version.acquired_at,
            valid_from=request.selection.start,
            valid_to=request.selection.end,
            availability_status="UNKNOWN",
            availability_evidence="Download does not evidence historical provider availability.",
        )
        records, metadata = decode_power(payload, request.selection, availability)
        return raw_ref, availability, records, metadata

    def prepare(
        self,
        request: EventRequest,
    ) -> tuple[
        BlobReference,
        SourceAvailabilityRecord,
        list[ObservationRecord],
        dict[str, Any],
        list[tuple[WindowReference, BuildRequest | None]],
    ]:
        request = EventRequest.model_validate_json(request.model_dump_json())
        validate_application(request)
        twin = self.forcing.twins.verify(self.forcing.twins.get(request.twin_id))
        if twin.city_id != request.city_id:
            raise ValueError("event and twin city differ")
        catchment = twin.component(ComponentRole.CATCHMENT)
        expected_area_id = (
            twin.pilot_area.pilot_area_id
            if request.catchment_status == "STUDY_AREA"
            else catchment.source.product_id
            if catchment.source is not None
            else None
        )
        if request.catchment_id != expected_area_id:
            raise ValueError(
                "event catchment/study area must identify the exact retained twin area"
            )
        raw_ref, availability, records, metadata = self.raw_inputs(request)
        source = Source(
            source=selection_url(request.selection),
            version=str(request.dataset_version_id),
            sha256=raw_ref.sha256,
            quality="PROVISIONAL",
            method="POWER header rate conversion; hourly UTC; explicit uniform regional estimate.",
        )
        windows = []
        cursor = request.event_start
        while cursor < request.event_end:
            end = min(cursor + timedelta(hours=3), request.event_end)
            selected = [r for r in records if cursor <= r.interval_start < end]
            missing = sum(r.qc != "VALID" for r in selected)
            prepared = None
            blockers = []
            if not missing:
                prepared = window_request(request, records, source, cursor, end)
                blockers = self.forcing.preview(prepared).blockers
            else:
                blockers = ["Missing/rejected rainfall; no zero filling or silent fallback."]
            # PREPARED requires an ID only after build; use a temporary deterministic sentinel.
            windows.append(
                (
                    WindowReference(
                        start=cursor,
                        end=end,
                        missing_intervals=missing,
                        status="MISSING_RAIN" if missing else "PREPARED",
                        forcing_package_id=None if missing else UUID(int=0),
                        blockers=blockers,
                    ),
                    prepared,
                )
            )
            cursor = end
        return raw_ref, availability, records, metadata, windows

    def preview(self, request: EventRequest) -> dict[str, Any]:
        _, _, records, metadata, windows = self.prepare(request)
        return {
            "event_key": request.event_key,
            "record_count": len(records),
            "rainfall_only": True,
            "strict_backtest_eligible": False,
            "metadata": metadata,
            "windows": [
                {**w.model_dump(mode="json"), "forcing_package_id": None} for w, _ in windows
            ],
        }

    def build(self, request: EventRequest) -> HistoricalEventManifest:
        request = EventRequest.model_validate_json(request.model_dump_json())
        raw_ref, availability, records, metadata, candidates = self.prepare(request)
        windows = []
        for window, prepared in candidates:
            if prepared is not None:
                window.forcing_package_id = self.forcing.build(prepared).forcing_package_id
            windows.append(window)
        artifacts = {
            "request.json": canonical_bytes(request.model_dump(mode="json")),
            "observations.json": canonical_bytes([r.model_dump(mode="json") for r in records]),
            "adapter.json": canonical_bytes(metadata),
        }
        manifest = HistoricalEventManifest(
            historical_event_id=UUID(int=0),
            event_key=request.event_key,
            title=request.title,
            city_id=request.city_id,
            catchment_id=request.catchment_id,
            event_start=request.event_start,
            event_end=request.event_end,
            twin_id=request.twin_id,
            dataset_version_id=request.dataset_version_id,
            raw_object=raw_ref,
            availability=availability,
            windows=windows,
            artifacts={name: self.forcing.write_blob(data) for name, data in artifacts.items()},
            software_version=self.forcing.twins.software_version,
            software_source_sha256=self.forcing.twins.software_source_sha256,
            evidence_gaps=request.evidence_gaps,
        )
        manifest.historical_event_id = identity(manifest)
        return self.recreate(canonical_bytes(manifest.model_dump(mode="json")))

    def validate(self, payload: bytes) -> HistoricalEventManifest:
        if len(payload) > MAX_BYTES:
            raise ValueError("event manifest exceeds size bound")
        manifest = HistoricalEventManifest.model_validate_json(payload)
        if identity(manifest) != manifest.historical_event_id:
            raise ValueError("event identity mismatch")
        if set(manifest.artifacts) != {"request.json", "observations.json", "adapter.json"}:
            raise ValueError("event artifact inventory mismatch")
        artifacts = {k: self.forcing.read_blob(v) for k, v in manifest.artifacts.items()}
        request = EventRequest.model_validate_json(artifacts["request.json"])
        raw_ref, availability, records, metadata, candidates = self.prepare(request)
        if (
            manifest.raw_object != raw_ref
            or manifest.availability != availability
            or manifest.event_key != request.event_key
            or manifest.title != request.title
            or manifest.city_id != request.city_id
            or manifest.catchment_id != request.catchment_id
            or manifest.twin_id != request.twin_id
            or manifest.dataset_version_id != request.dataset_version_id
            or manifest.event_start != request.event_start
            or manifest.event_end != request.event_end
            or manifest.evidence_gaps != request.evidence_gaps
        ):
            raise ValueError("event metadata differs from immutable source/request")
        expected = canonical_bytes([r.model_dump(mode="json") for r in records])
        if artifacts["observations.json"] != expected or artifacts[
            "adapter.json"
        ] != canonical_bytes(metadata):
            raise ValueError("normalized observations differ from raw-source computation")
        if len(candidates) != len(manifest.windows):
            raise ValueError("event window count differs from request")
        for (expected_window, prepared), actual in zip(candidates, manifest.windows, strict=True):
            if prepared is not None:
                if actual.forcing_package_id is None:
                    raise ValueError("prepared event window is missing forcing identity")
                content = self.forcing.read_artifact(actual.forcing_package_id, "request.json")
                if BuildRequest.model_validate_json(content) != prepared:
                    raise ValueError("event forcing differs from normalized historical window")
                expected_window.forcing_package_id = actual.forcing_package_id
            if actual != expected_window:
                raise ValueError("event window metadata differs from verified inputs")
        return manifest

    def recreate(self, payload: bytes) -> HistoricalEventManifest:
        manifest = self.validate(payload)
        ref = self.forcing.write_blob(payload)
        existing = self.session.get(HistoricalEventRecord, manifest.historical_event_id)
        if existing is None:
            self.session.add(
                HistoricalEventRecord(
                    historical_event_id=manifest.historical_event_id,
                    city_id=manifest.city_id,
                    event_key=manifest.event_key,
                    manifest=ref.model_dump(mode="json"),
                )
            )
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                if self.session.get(HistoricalEventRecord, manifest.historical_event_id) is None:
                    raise
        return self.get(manifest.historical_event_id)

    def get(self, event_id: UUID) -> HistoricalEventManifest:
        record = self.session.get(HistoricalEventRecord, event_id)
        if record is None:
            raise LookupError(str(event_id))
        ref = BlobReference.model_validate(record.manifest)
        manifest = self.validate(self.forcing.read_blob(ref))
        if (
            manifest.historical_event_id != event_id
            or manifest.city_id != record.city_id
            or manifest.event_key != record.event_key
        ):
            raise ValueError("event catalogue differs from retained manifest")
        return manifest

    def list_events(self, city_id: str) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(HistoricalEventRecord)
            .where(HistoricalEventRecord.city_id == city_id)
            .order_by(HistoricalEventRecord.created_at.desc())
        )
        return [
            {"historical_event_id": str(r.historical_event_id), "event_key": r.event_key}
            for r in rows
        ]

    def observations(self, event_id: UUID) -> list[dict[str, Any]]:
        manifest = self.get(event_id)
        data: list[dict[str, Any]] = json.loads(
            self.forcing.read_blob(manifest.artifacts["observations.json"])
        )
        return data

    def view(self, event_id: UUID) -> dict[str, Any]:
        manifest = self.get(event_id)
        request = EventRequest.model_validate_json(
            self.forcing.read_blob(manifest.artifacts["request.json"])
        )
        records = [
            ObservationRecord.model_validate(r)
            for r in json.loads(self.forcing.read_blob(manifest.artifacts["observations.json"]))
        ]
        records = [
            r for r in records if request.event_start <= r.interval_start < request.event_end
        ]
        twin = self.forcing.twins.verify(self.forcing.twins.get(request.twin_id))
        point = Transformer.from_crs("EPSG:4326", twin.horizontal_crs, always_xy=True).transform(
            request.selection.longitude,
            request.selection.latitude,
        )
        accumulated = 0.0
        complete = True
        intervals = []
        for record in records:
            if record.value is None:
                complete = False
            else:
                accumulated += (
                    record.value
                    * (record.interval_end - record.interval_start).total_seconds()
                    / 3600
                )
            intervals.append(
                {
                    "start": record.interval_start.isoformat(),
                    "end": record.interval_end.isoformat(),
                    "rate_mm_h": record.value,
                    "qc": record.qc,
                    "accumulation_mm": accumulated if complete else None,
                    "known_accumulation_mm": accumulated,
                }
            )
        return {
            "manifest": manifest.model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "intervals": intervals,
            "coverage": {"valid": sum(r.qc == "VALID" for r in records), "total": len(records)},
            "map": {
                "geometry": twin.pilot_area.geometry,
                "horizontal_crs": twin.horizontal_crs,
                "extraction_point": list(point),
                "label": "Retained twin study area",
            },
            "twin_readiness": twin.hydraulic_readiness.value,
            "source_resolution": "MERRA-2: 0.5 degrees latitude x 0.625 degrees longitude",
        }
