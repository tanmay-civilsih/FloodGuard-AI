"""Conservative interval/member remapping and deterministic Xarray/Zarr storage."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import numpy as np
import xarray as xr
from numpy.typing import NDArray

from floodguard.forcing.contracts import MAX_VALUES, POLICY, VOLUME_TOLERANCE, Grid, RainInput
from floodguard.spatial.resampling import conservative_remap_rainfall


@dataclass
class RemappedRain:
    rates: NDArray[np.float64]  # time, y, x, member
    accumulation: NDArray[np.float64]
    volumes: dict[str, float]
    maximum_relative_error: float


def remap(rain: RainInput, target: Grid) -> RemappedRain:
    if rain.grid.horizontal_crs != target.horizontal_crs:
        raise ValueError("rainfall CRS must match target; use an explicit upstream adapter")
    shape = (
        len(rain.time_edges) - 1,
        len(target.y_edges_m) - 1,
        len(target.x_edges_m) - 1,
        len(rain.members),
    )
    if int(np.prod(shape)) > MAX_VALUES:
        raise ValueError("remapped rain exceeds prototype size bound")
    output = np.empty(shape, dtype=np.float64)
    seconds = np.array(
        [
            (b - a).total_seconds()
            for a, b in zip(rain.time_edges, rain.time_edges[1:], strict=False)
        ]
    )
    volumes: dict[str, float] = {}
    error = 0.0
    for member_index, member in enumerate(rain.members):
        volume = 0.0
        for i, (rates, dt) in enumerate(zip(member.rain_rate_mm_h, seconds, strict=True)):
            result = conservative_remap_rainfall(
                rates,
                rain.grid.x_edges_m,
                rain.grid.y_edges_m,
                target.x_edges_m,
                target.y_edges_m,
                timestep_seconds=float(dt),
                tolerance=VOLUME_TOLERANCE,
            )
            if not result.conservation.passed:
                raise ValueError("rainfall volume conservation failed")
            output[i, :, :, member_index] = result.rain_rate_mm_h
            volume += result.conservation.volume_after_m3
            error = max(error, result.conservation.relative_error)
        volumes[member.member_id] = volume
    accumulation = np.cumsum(output * seconds[:, None, None, None] / 3600, axis=0)
    if not np.all(np.isfinite(accumulation)) or not all(np.isfinite(list(volumes.values()))):
        raise ValueError("rainfall accumulation/volume exceeds finite numerical range")
    return RemappedRain(output, accumulation, volumes, error)


def zarr_bytes(rain: RainInput, target: Grid, result: RemappedRain) -> bytes:
    """No archive extraction. Fixed ZIP metadata and uncompressed arrays ensure stable bytes."""
    times = np.array([t.timestamp() for t in rain.time_edges], dtype=np.float64)
    dims = ["time", "y", "x"]
    rates, accumulation = result.rates, result.accumulation
    coords: dict[str, Any] = {
        "time": ("time", times[:-1]),
        "y": ("y", (np.array(target.y_edges_m[:-1]) + target.y_edges_m[1:]) / 2),
        "x": ("x", (np.array(target.x_edges_m[:-1]) + target.x_edges_m[1:]) / 2),
    }
    if len(rain.members) > 1:
        dims.append("ensemble_member")
        coords["ensemble_member"] = ("ensemble_member", np.arange(len(rain.members)))
    else:
        rates, accumulation = rates[..., 0], accumulation[..., 0]
    quality = 0 if rain.source.quality == "SOURCE_DECLARED" else 1
    dataset = xr.Dataset(
        {
            "rain_rate": (dims, rates, {"units": "mm/h", "cell_methods": "time: mean"}),
            "accumulation": (
                dims,
                accumulation,
                {
                    "units": "mm",
                    "interpretation": "cumulative depth at interval end, since first time edge",
                },
            ),
            "quality_flag": (
                dims,
                np.full(rates.shape, quality, dtype=np.uint8),
                {
                    "flag_values": [0, 1],
                    "flag_meanings": "source_declared provisional_or_synthetic",
                },
            ),
            "time_bounds": (["time", "bounds"], np.stack((times[:-1], times[1:]), axis=1)),
            "valid_time": ("time", times[:-1]),
            "lead_time": ("time", times[:-1] - rain.issue_time.timestamp(), {"units": "s"}),
        },
        coords=coords,
        attrs={
            "policy": POLICY,
            "issue_time": rain.issue_time.isoformat(),
            "mode": rain.mode.value,
            "source": rain.source.model_dump(mode="json"),
            "processing_lineage": [s.model_dump(mode="json") for s in rain.processing_lineage],
            "horizontal_crs": target.horizontal_crs,
            "native_spatial_resolution_m": rain.native_spatial_resolution_m,
            "effective_spatial_resolution_m": max(
                rain.effective_spatial_resolution_m,
                target.x_edges_m[1] - target.x_edges_m[0],
                target.y_edges_m[1] - target.y_edges_m[0],
            ),
            "grid_transform": [
                target.x_edges_m[0],
                target.x_edges_m[1] - target.x_edges_m[0],
                0,
                target.y_edges_m[0],
                0,
                target.y_edges_m[1] - target.y_edges_m[0],
            ],
            "ensemble_definition": rain.ensemble_definition,
            "member_ids": [m.member_id for m in rain.members],
            "temporal_interpretation": "INTERVAL_MEAN; no extrapolation",
            "maximum_remap_relative_error": result.maximum_relative_error,
            "volume_tolerance": VOLUME_TOLERANCE,
        },
    )
    for name in ("time", "valid_time", "time_bounds"):
        dataset[name].attrs.update(
            units="seconds since 1970-01-01 00:00:00", calendar="proleptic_gregorian"
        )
    dataset["time"].attrs["bounds"] = "time_bounds"
    dataset["x"].attrs["units"] = dataset["y"].attrs["units"] = "m"
    encoding = {str(name): {"compressor": None, "_FillValue": None} for name in dataset.variables}
    with TemporaryDirectory(prefix="floodguard-rain-") as temporary:
        directory = Path(temporary) / "rain.zarr"
        dataset.to_zarr(directory, mode="w", zarr_format=2, consolidated=True, encoding=encoding)
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_STORED) as archive:
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    info = ZipInfo(path.relative_to(directory).as_posix(), (1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
    return output.getvalue()
