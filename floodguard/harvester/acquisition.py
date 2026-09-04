"""Network acquisition adapters for Sequence 3.

This module retrieves bytes only. It does not normalize, reproject, resample, or otherwise
alter scientific content; those operations begin in Sequence 4.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, cast
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from floodguard.registry.contracts import AccessMethod, SourceRead


class AcquisitionError(RuntimeError):
    pass


class UnsupportedAcquisitionMethod(AcquisitionError):
    pass


class AcquisitionParametersRequired(AcquisitionError):
    pass


class ObjectTooLargeError(AcquisitionError):
    pass


@dataclass(frozen=True, slots=True)
class RemoteRequest:
    url: str
    filename: str
    method: str = "GET"
    body: bytes | None = None
    headers: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class DownloadedObject:
    source_url: str
    filename: str
    path: Path
    sha256: str
    byte_size: int
    content_type: str | None
    etag: str | None
    last_modified: str | None


class AcquisitionTransport(Protocol):
    def get_json(self, url: str, *, headers: Mapping[str, str]) -> dict[str, object]: ...

    def download(
        self,
        request: RemoteRequest,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> DownloadedObject: ...


class UrlLibTransport:
    def get_json(self, url: str, *, headers: Mapping[str, str]) -> dict[str, object]:
        request = Request(url, headers=dict(headers), method="GET")
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict):
            raise AcquisitionError(f"expected JSON object from {url}")
        return cast(dict[str, object], payload)

    def download(
        self,
        request: RemoteRequest,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> DownloadedObject:
        http_request = Request(
            request.url,
            data=request.body,
            headers=dict(request.headers or {}),
            method=request.method,
        )
        digest = hashlib.sha256()
        size = 0
        with urlopen(http_request, timeout=timeout_seconds) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > max_bytes:
                raise ObjectTooLargeError(
                    f"remote object exceeds {max_bytes} bytes: {request.url}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ObjectTooLargeError(
                            f"download exceeded {max_bytes} bytes: {request.url}"
                        )
                    digest.update(chunk)
                    output.write(chunk)
            return DownloadedObject(
                source_url=request.url,
                filename=request.filename,
                path=destination,
                sha256=digest.hexdigest(),
                byte_size=size,
                content_type=response.headers.get_content_type(),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )


_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(value: str, *, fallback: str = "source.bin") -> str:
    value = value.strip().replace("\\", "/").rsplit("/", 1)[-1]
    value = _FILENAME_RE.sub("_", value).strip("._")
    return value[:240] or fallback


def _url_filename(url: str, fallback: str) -> str:
    path_name = urlparse(url).path.rsplit("/", 1)[-1]
    return safe_filename(path_name, fallback=fallback)


class AcquisitionPlanner:
    def __init__(self, transport: AcquisitionTransport) -> None:
        self.transport = transport

    def plan(
        self,
        source: SourceRead,
        *,
        parameters: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> list[RemoteRequest]:
        params = parameters or {}
        request_headers = dict(headers or {})
        method = source.access_method

        if method is AccessMethod.CKAN:
            return self._plan_ckan(source, request_headers)
        if method in {AccessMethod.HTTP, AccessMethod.REST, AccessMethod.PBF_EXTRACT}:
            return [
                RemoteRequest(
                    url=source.endpoint,
                    filename=_url_filename(source.endpoint, "source-data"),
                    headers=request_headers,
                )
            ]
        if method is AccessMethod.OVERPASS:
            query = params.get("query")
            if not isinstance(query, str) or not query.strip():
                raise AcquisitionParametersRequired(
                    "OVERPASS acquisition requires a bounded query"
                )
            return [
                RemoteRequest(
                    url=source.endpoint,
                    filename="overpass.osm",
                    method="POST",
                    body=urlencode({"data": query}).encode(),
                    headers={
                        **request_headers,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            ]
        if method is AccessMethod.STAC:
            return self._plan_stac(source, params, request_headers)
        if method in {AccessMethod.WMS, AccessMethod.WFS, AccessMethod.WMTS}:
            query = params.get("query")
            if not isinstance(query, dict) or not query:
                raise AcquisitionParametersRequired(
                    f"{method.value} acquisition requires query parameters"
                )
            encoded = urlencode({str(key): str(value) for key, value in query.items()})
            delimiter = "&" if "?" in source.endpoint else "?"
            url = f"{source.endpoint}{delimiter}{encoded}"
            return [
                RemoteRequest(
                    url=url,
                    filename=_url_filename(
                        url,
                        f"{method.value.lower()}-response.bin",
                    ),
                    headers=request_headers,
                )
            ]
        raise UnsupportedAcquisitionMethod(
            f"{source.access_method.value} has no generic automated adapter"
        )

    def _plan_ckan(
        self,
        source: SourceRead,
        headers: Mapping[str, str],
    ) -> list[RemoteRequest]:
        parsed = urlparse(source.endpoint)
        slug = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        if not slug:
            raise AcquisitionError("CKAN dataset endpoint does not contain a package slug")
        query = urlencode({"id": slug})
        api_url = f"{parsed.scheme}://{parsed.netloc}/api/3/action/package_show?{query}"
        payload = self.transport.get_json(api_url, headers=headers)
        if payload.get("success") is not True:
            raise AcquisitionError(f"CKAN package_show failed for {source.endpoint}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise AcquisitionError("CKAN package_show response has no result object")
        resources = result.get("resources")
        if not isinstance(resources, list):
            raise AcquisitionError("CKAN package contains no resource list")

        planned: list[RemoteRequest] = []
        for index, resource_value in enumerate(resources):
            if not isinstance(resource_value, dict):
                continue
            resource = cast(dict[str, object], resource_value)
            url = resource.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            name_value = resource.get("name")
            name = name_value if isinstance(name_value, str) else ""
            format_value = resource.get("format")
            resource_format = format_value if isinstance(format_value, str) else ""
            fallback = _url_filename(url, f"resource-{index:03d}")
            filename = safe_filename(name, fallback=fallback)
            if "." not in filename and resource_format:
                extension = safe_filename(resource_format.lower(), fallback="bin")
                filename = f"{filename}.{extension}"
            planned.append(RemoteRequest(url=url, filename=filename, headers=headers))
        if not planned:
            raise AcquisitionError("CKAN package has no downloadable HTTP resources")
        return planned

    def _plan_stac(
        self,
        source: SourceRead,
        parameters: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> list[RemoteRequest]:
        item_url_value = parameters.get("item_url")
        item_url = item_url_value if isinstance(item_url_value, str) else source.endpoint
        payload = self.transport.get_json(item_url, headers=headers)
        assets = payload.get("assets")
        if not isinstance(assets, dict):
            raise AcquisitionParametersRequired(
                "STAC acquisition requires an Item URL (source endpoint or item_url parameter)"
            )
        requested_keys_value = parameters.get("asset_keys")
        requested_keys = (
            {str(value) for value in requested_keys_value}
            if isinstance(requested_keys_value, list)
            else None
        )
        planned: list[RemoteRequest] = []
        for key, asset_value in sorted(assets.items()):
            if requested_keys is not None and key not in requested_keys:
                continue
            if not isinstance(asset_value, dict):
                continue
            href = asset_value.get("href")
            if not isinstance(href, str) or not href.startswith(("http://", "https://")):
                continue
            planned.append(
                RemoteRequest(
                    url=href,
                    filename=_url_filename(
                        href,
                        safe_filename(str(key), fallback="asset.bin"),
                    ),
                    headers=headers,
                )
            )
        if not planned:
            raise AcquisitionError("STAC item contains no selected HTTP assets")
        return planned
