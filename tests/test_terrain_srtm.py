import hashlib

import numpy as np
import pytest
from pyproj import Transformer

from floodguard.terrain.service import _readiness_status
from floodguard.terrain.srtm import (
    MAX_PILOT_CELLS,
    SRTM_BYTES,
    SRTM_SIDE,
    SrtmTarget,
    convert_srtm,
    decode_hgt,
    sample_hgt_grid,
)


@pytest.fixture(scope="module")
def hgt_bytes() -> bytes:
    # An analytical north/south ramp with an explicit void and negative elevation.
    values = np.broadcast_to(
        np.arange(SRTM_SIDE, dtype=">i2")[:, None], (SRTM_SIDE, SRTM_SIDE)
    ).copy()
    values[1800, 1800] = -20
    values[1800, 1801] = -32768
    return values.tobytes()


def test_hgt_byte_order_post_layout_and_negative_heights(hgt_bytes: bytes) -> None:
    tile = decode_hgt(hgt_bytes, "N22E088.hgt")
    assert tile.west == 88 and tile.south == 22
    assert tile.elevations[0, 0] == 0
    assert tile.elevations[3600, 3600] == 3600
    assert tile.elevations[1800, 1800] == -20
    assert tile.elevations[1800, 1801] == -32768
    assert not tile.elevations.flags.writeable


def test_nearest_post_benchmark_preserves_void_and_south_to_north_orientation(
    hgt_bytes: bytes,
) -> None:
    tile = decode_hgt(hgt_bytes, "N22E088.hgt")
    forward = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    for row, column, expected in [(1800, 1800, -20), (1800, 1801, None), (1799, 1800, 1799)]:
        x, y = forward.transform(88 + column / 3600, 23 - row / 3600)
        if expected is None:
            # A larger grid keeps the adjacent valid post while retaining the nodata cell.
            grid = sample_hgt_grid(
                tile,
                width=2,
                height=1,
                origin_x_m=x - 15,
                origin_y_m=y - 15,
                cell_size_m=30,
                crs="EPSG:32645",
            )
            assert grid.elevations_m[0][0] is None
        else:
            grid = sample_hgt_grid(
                tile,
                width=1,
                height=1,
                origin_x_m=x - 5,
                origin_y_m=y - 5,
                cell_size_m=10,
                crs="EPSG:32645",
            )
            assert grid.elevations_m == [[expected]]
    grid = sample_hgt_grid(
        tile,
        width=1,
        height=5,
        origin_x_m=x - 15,
        origin_y_m=y - 75,
        cell_size_m=30,
        crs="EPSG:32645",
    )
    assert grid.elevations_m[0][0] > grid.elevations_m[-1][0]


def test_conversion_preserves_source_hash_and_never_grants_readiness(hgt_bytes: bytes) -> None:
    forward = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    x, y = forward.transform(88.37, 22.60)
    target = SrtmTarget(
        working_crs="EPSG:32645", bounds_working=[x, y, x + 100, y + 90], cell_size_m=10
    )
    package = convert_srtm(
        hgt_bytes,
        filename="N22E088.hgt",
        target=target,
        pilot_area_id="test-pilot",
        boundary_reference="test://extent",
    )
    assert package.derivation.source_sha256 == hashlib.sha256(hgt_bytes).hexdigest()
    assert package.grid.width * package.grid.height <= MAX_PILOT_CELLS
    assert package.native_horizontal_resolution_m >= 30
    assert package.effective_information_resolution_m > package.computational_resolution_m
    assert package.vertical_datum == "EGM96"
    assert package.datum_transform_status.value == "UNRESOLVED"
    assert (
        package.depression_assessment.value
        == package.multi_level_assessment.value
        == "NOT_ASSESSED"
    )
    assert package.interventions == package.multi_level_structures == []
    assert _readiness_status(package).value == "VISUAL_READY"
    assert package == convert_srtm(
        hgt_bytes,
        filename="N22E088.hgt",
        target=target,
        pilot_area_id="test-pilot",
        boundary_reference="test://extent",
    )


@pytest.mark.parametrize(
    "name", ["dem.hgt", "N90E088.hgt", "N22E180.hgt", "../N22E088.hgt", "N22E088.tif"]
)
def test_bad_hgt_names_fail(hgt_bytes: bytes, name: str) -> None:
    with pytest.raises(ValueError):
        decode_hgt(hgt_bytes, name)


@pytest.mark.parametrize(
    "payload", [b"", b"PK\x03\x04", bytes(1201 * 1201 * 2), b"x" * (SRTM_BYTES + 1)]
)
def test_wrong_hgt_size_fails(payload: bytes) -> None:
    with pytest.raises(ValueError, match="exactly"):
        decode_hgt(payload, "N22E088.hgt")


def test_sampling_rejects_outside_tile_and_excessive_grid(hgt_bytes: bytes) -> None:
    tile = decode_hgt(hgt_bytes, "N22E088.hgt")
    with pytest.raises(ValueError, match="outside this HGT tile"):
        sample_hgt_grid(
            tile, width=1, height=1, origin_x_m=0, origin_y_m=0, cell_size_m=30, crs="EPSG:32645"
        )
    with pytest.raises(ValueError, match="1 to"):
        sample_hgt_grid(
            tile,
            width=MAX_PILOT_CELLS + 1,
            height=1,
            origin_x_m=0,
            origin_y_m=0,
            cell_size_m=30,
            crs="EPSG:32645",
        )
