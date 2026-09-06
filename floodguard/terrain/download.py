"""Bounded public SRTM downloads and in-memory archive validation."""

from __future__ import annotations

import io
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from email.message import Message
from typing import IO
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from floodguard.contracts.time import utc_now
from floodguard.registry.seed import ESA_SRTM_BASE_URL
from floodguard.terrain.grid import sha256
from floodguard.terrain.srtm import SRTM_BYTES, decode_hgt

MAX_SRTM_ZIP_BYTES = 32 * 1024 * 1024
SRTM_DOWNLOAD_DEADLINE_SECONDS = 120.0


@dataclass(frozen=True, slots=True)
class SrtmArchive:
    source_url: str
    filename: str
    payload: bytes
    downloaded_at: datetime
    etag: str | None = None
    last_modified: str | None = None

    def provenance(self) -> dict[str, object]:
        return {
            "adapter": "esa-step-srtmgl1-download-v1",
            "source_url": self.source_url,
            "filename": self.filename,
            "sha256": sha256(self.payload),
            "byte_size": len(self.payload),
            "downloaded_at": self.downloaded_at.isoformat(),
            "etag": self.etag,
            "last_modified": self.last_modified,
        }


def archive_url(tile: str) -> str:
    if not re.fullmatch(r"[NS]\d{2}[EW]\d{3}", tile):
        raise ValueError("expected one SRTM tile name")
    return f"{ESA_SRTM_BASE_URL}{tile}.SRTMGL1.hgt.zip"


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: Message, newurl: str
    ) -> Request | None:
        raise ValueError("SRTM mirror redirected the download; source review is required")


def download_srtm(
    tile: str, *, max_bytes: int, timeout_seconds: float
) -> SrtmArchive:
    url = archive_url(tile)
    limit = min(max_bytes, MAX_SRTM_ZIP_BYTES)
    deadline = time.monotonic() + SRTM_DOWNLOAD_DEADLINE_SECONDS
    request = Request(url, headers={"User-Agent": "FloodGuard-AI/0.6 SRTM pilot acquisition"})
    try:
        with build_opener(NoRedirects()).open(
            request, timeout=min(timeout_seconds, 30.0)
        ) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("SRTM mirror did not return the requested tile")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > limit:
                raise ValueError("SRTM archive exceeds the configured byte limit")
            payload = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise ValueError("SRTM download exceeded the total time limit")
                chunk = response.read(min(64 * 1024, limit + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > limit:
                    raise ValueError("SRTM archive exceeds the configured byte limit")
            return SrtmArchive(
                source_url=url,
                filename=f"{tile}.SRTMGL1.hgt.zip",
                payload=bytes(payload),
                downloaded_at=utc_now(),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(
            "The ESA SRTM mirror could not be reached; retry acquisition later"
        ) from exc


def unpack_srtm(archive: SrtmArchive, tile: str) -> tuple[str, bytes]:
    if archive.source_url != archive_url(tile) or archive.filename != f"{tile}.SRTMGL1.hgt.zip":
        raise ValueError("SRTM archive does not match the requested public tile")
    if len(archive.payload) > MAX_SRTM_ZIP_BYTES:
        raise ValueError("SRTM archive exceeds the byte limit")
    try:
        with zipfile.ZipFile(io.BytesIO(archive.payload)) as zipped:
            files = zipped.infolist()
            if len(files) != 1:
                raise ValueError("SRTM archive must contain one original HGT file")
            entry = files[0]
            accepted = {f"{tile}.hgt".lower(), f"{tile}.SRTMGL1.hgt".lower()}
            if entry.filename.lower() not in accepted or entry.file_size != SRTM_BYTES:
                raise ValueError("SRTM archive has an unexpected tile name or HGT size")
            if entry.flag_bits & 1:
                raise ValueError("Encrypted SRTM archives are unsupported")
            payload = zipped.read(entry)  # Checks the ZIP CRC; no paths are extracted to disk.
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("SRTM response is not a valid original HGT archive") from exc
    decode_hgt(payload, entry.filename)
    return entry.filename, payload
