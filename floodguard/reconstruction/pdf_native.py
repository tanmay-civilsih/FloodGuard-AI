"""Native PDF vector/text inspection and deterministic drainage symbol extraction."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from math import atan2, cos, hypot, pi, sin
from typing import Any

from pypdf import PdfReader

from floodguard.reconstruction.contracts import ExtractionMode, NativePdfInspection

Point = tuple[float, float]
Rgb = tuple[float, float, float]
_PAINT_OPERATORS = {"S", "s", "B", "B*", "b", "b*", "f", "f*"}
_DRAIN_LABEL = re.compile(
    r"(?i)(\bMH\s*\d+\b|\bIVL\s*=|SEWER|\blength\b|"
    r"\d+(?:\.\d+)?\s*m?m\s*[ØO0]|\d+\s*[\"']\s*[ØO0])"
)
_MANHOLE_LABEL = re.compile(r"(?i)\bMH\s*\d+\b")


class PdfNativeExtractionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NativePath:
    points: tuple[Point, ...]
    stroke_rgb: Rgb
    line_width_points: float
    closed: bool


@dataclass(frozen=True, slots=True)
class NativeTextSpan:
    text: str
    point: Point
    font_size: float


@dataclass(frozen=True, slots=True)
class NativePdfExtraction:
    inspection: NativePdfInspection
    paths: tuple[NativePath, ...]
    text_spans: tuple[NativeTextSpan, ...]


@dataclass(frozen=True, slots=True)
class CleanedDrain:
    start: Point
    end: Point
    source_fragment_count: int
    source_length_points: float


@dataclass(frozen=True, slots=True)
class NativeStructure:
    point: Point
    symbol_width_points: float
    symbol_height_points: float


@dataclass(slots=True)
class _GraphicsState:
    stroke_rgb: Rgb = (0.0, 0.0, 0.0)
    line_width: float = 1.0

    def copy(self) -> _GraphicsState:
        return _GraphicsState(self.stroke_rgb, self.line_width)


def _number(value: Any) -> float:
    return float(value)


def _transform(x: float, y: float, matrix: Any) -> Point:
    return (
        _number(matrix[0]) * x + _number(matrix[2]) * y + _number(matrix[4]),
        _number(matrix[1]) * x + _number(matrix[3]) * y + _number(matrix[5]),
    )


def _rgb_from_cmyk(arguments: Any) -> Rgb:
    cyan, magenta, yellow, black = (_number(value) for value in arguments[:4])
    return (
        round((1.0 - cyan) * (1.0 - black), 6),
        round((1.0 - magenta) * (1.0 - black), 6),
        round((1.0 - yellow) * (1.0 - black), 6),
    )


def _metadata(reader: PdfReader) -> dict[str, str]:
    document = reader.metadata
    if document is None:
        return {}
    result: dict[str, str] = {}
    for key, output_key in (
        ("/Title", "title"),
        ("/Creator", "creator"),
        ("/Producer", "producer"),
        ("/CreationDate", "creation_date"),
        ("/ModDate", "modified_date"),
    ):
        value = document.get(key)
        if value is not None:
            result[output_key] = str(value)[:500]
    return result


def _embedded_image_count(page: Any) -> int:
    resources = page.get("/Resources")
    if resources is None:
        return 0
    resources = resources.get_object()
    xobjects = resources.get("/XObject")
    if xobjects is None:
        return 0
    count = 0
    for value in xobjects.get_object().values():
        item = value.get_object()
        if item.get("/Subtype") == "/Image":
            count += 1
    return count


def inspect_native_pdf(payload: bytes, *, selected_page: int = 1) -> NativePdfExtraction:
    if not payload.startswith(b"%PDF-"):
        raise PdfNativeExtractionError("source object is not a PDF")
    try:
        reader = PdfReader(BytesIO(payload), strict=False)
    except Exception as exc:
        raise PdfNativeExtractionError(f"PDF could not be opened: {exc}") from exc
    if not reader.pages:
        raise PdfNativeExtractionError("PDF contains no pages")
    if selected_page > len(reader.pages):
        raise PdfNativeExtractionError("selected PDF page does not exist")
    page = reader.pages[selected_page - 1]
    paths: list[NativePath] = []
    text_spans: list[NativeTextSpan] = []
    state = _GraphicsState()
    state_stack: list[_GraphicsState] = []
    current_path: list[Point] = []
    path_start: Point | None = None
    path_closed = False

    def reset_path() -> None:
        nonlocal current_path, path_start, path_closed
        current_path = []
        path_start = None
        path_closed = False

    def operand_before(operator: bytes, arguments: Any, cm: Any, tm: Any) -> None:
        del tm
        nonlocal state, path_start, path_closed
        name = operator.decode("ascii", errors="ignore")
        if name == "q":
            state_stack.append(state.copy())
        elif name == "Q":
            if state_stack:
                state = state_stack.pop()
        elif name == "RG":
            state.stroke_rgb = tuple(
                round(_number(value), 6) for value in arguments[:3]
            )  # type: ignore[assignment]
        elif name == "G":
            grey = round(_number(arguments[0]), 6)
            state.stroke_rgb = (grey, grey, grey)
        elif name == "K":
            state.stroke_rgb = _rgb_from_cmyk(arguments)
        elif name == "w":
            state.line_width = _number(arguments[0])
        elif name == "m":
            point = _transform(_number(arguments[0]), _number(arguments[1]), cm)
            current_path.clear()
            current_path.append(point)
            path_start = point
            path_closed = False
        elif name == "l":
            current_path.append(
                _transform(_number(arguments[0]), _number(arguments[1]), cm)
            )
        elif name == "c":
            for index in (0, 2, 4):
                current_path.append(
                    _transform(
                        _number(arguments[index]),
                        _number(arguments[index + 1]),
                        cm,
                    )
                )
        elif name in {"v", "y"}:
            for index in range(0, len(arguments), 2):
                current_path.append(
                    _transform(
                        _number(arguments[index]),
                        _number(arguments[index + 1]),
                        cm,
                    )
                )
        elif name == "re":
            x = _number(arguments[0])
            y = _number(arguments[1])
            width = _number(arguments[2])
            height = _number(arguments[3])
            current_path.clear()
            current_path.extend(
                _transform(px, py, cm)
                for px, py in (
                    (x, y),
                    (x + width, y),
                    (x + width, y + height),
                    (x, y + height),
                    (x, y),
                )
            )
            path_start = current_path[0]
            path_closed = True
        elif name == "h":
            if path_start is not None and current_path[-1:] != [path_start]:
                current_path.append(path_start)
            path_closed = True
        elif name in _PAINT_OPERATORS:
            if len(current_path) >= 2:
                closed = path_closed or name in {"s", "b", "b*"}
                if closed and path_start is not None and current_path[-1] != path_start:
                    current_path.append(path_start)
                paths.append(
                    NativePath(
                        points=tuple(current_path),
                        stroke_rgb=state.stroke_rgb,
                        line_width_points=state.line_width,
                        closed=closed,
                    )
                )
            reset_path()
        elif name == "n":
            reset_path()

    def visit_text(
        text: str,
        cm: Any,
        tm: Any,
        font_dictionary: Any,
        font_size: float,
    ) -> None:
        del font_dictionary
        normalized = " ".join(text.split())
        if not normalized:
            return
        text_spans.append(
            NativeTextSpan(
                text=normalized,
                point=_transform(_number(tm[4]), _number(tm[5]), cm),
                font_size=float(font_size),
            )
        )

    try:
        page.extract_text(
            visitor_operand_before=operand_before,
            visitor_text=visit_text,
        )
    except Exception as exc:
        raise PdfNativeExtractionError(f"native PDF content extraction failed: {exc}") from exc
    vector_count = len(paths)
    text_count = len(text_spans)
    native_sufficient = vector_count > 0 and text_count > 0
    inspection = NativePdfInspection(
        page_count=len(reader.pages),
        selected_page=selected_page,
        page_width_points=float(page.mediabox.width),
        page_height_points=float(page.mediabox.height),
        page_rotation_degrees=int(page.rotation),
        native_vector_path_count=vector_count,
        native_text_span_count=text_count,
        embedded_image_count=_embedded_image_count(page),
        extraction_mode=(
            ExtractionMode.NATIVE_VECTOR_TEXT
            if native_sufficient
            else ExtractionMode.OCR_FALLBACK
        ),
        ocr_used=False,
        metadata=_metadata(reader),
    )
    return NativePdfExtraction(
        inspection=inspection,
        paths=tuple(paths),
        text_spans=tuple(text_spans),
    )


def _is_red(rgb: Rgb) -> bool:
    return rgb[0] >= 0.9 and rgb[1] <= 0.15 and rgb[2] <= 0.15


def clean_native_drain_paths(
    paths: tuple[NativePath, ...],
    *,
    angle_bin_degrees: float = 5.0,
    offset_bin_points: float = 4.0,
    maximum_gap_points: float = 12.0,
    minimum_length_points: float = 12.0,
) -> tuple[CleanedDrain, ...]:
    """Merge native red CAD dash fragments into traceable straight drain reaches."""

    groups: dict[tuple[int, int], list[tuple[float, float, float]]] = defaultdict(list)
    angle_step = angle_bin_degrees * pi / 180.0
    for path in paths:
        if not _is_red(path.stroke_rgb):
            continue
        for start, end in zip(path.points, path.points[1:], strict=False):
            length = hypot(end[0] - start[0], end[1] - start[1])
            if length < 1.0:
                continue
            theta = atan2(end[1] - start[1], end[0] - start[0]) % pi
            angle_bin = round(theta / angle_step)
            representative_theta = angle_bin * angle_step
            ux, uy = cos(representative_theta), sin(representative_theta)
            nx, ny = -uy, ux
            midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            rho = midpoint[0] * nx + midpoint[1] * ny
            offset_bin = round(rho / offset_bin_points)
            start_t = start[0] * ux + start[1] * uy
            end_t = end[0] * ux + end[1] * uy
            groups[(angle_bin, offset_bin)].append(
                (min(start_t, end_t), max(start_t, end_t), length)
            )

    cleaned: list[CleanedDrain] = []
    for (angle_bin, offset_bin), intervals in sorted(groups.items()):
        theta = angle_bin * angle_step
        ux, uy = cos(theta), sin(theta)
        nx, ny = -uy, ux
        rho = offset_bin * offset_bin_points
        intervals.sort()
        low, high, source_length = intervals[0]
        fragments = 1
        for next_low, next_high, next_length in intervals[1:]:
            if next_low - high <= maximum_gap_points:
                high = max(high, next_high)
                source_length += next_length
                fragments += 1
                continue
            if high - low >= minimum_length_points:
                cleaned.append(
                    CleanedDrain(
                        start=(ux * low + nx * rho, uy * low + ny * rho),
                        end=(ux * high + nx * rho, uy * high + ny * rho),
                        source_fragment_count=fragments,
                        source_length_points=source_length,
                    )
                )
            low, high, source_length, fragments = next_low, next_high, next_length, 1
        if high - low >= minimum_length_points:
            cleaned.append(
                CleanedDrain(
                    start=(ux * low + nx * rho, uy * low + ny * rho),
                    end=(ux * high + nx * rho, uy * high + ny * rho),
                    source_fragment_count=fragments,
                    source_length_points=source_length,
                )
            )
    return tuple(
        sorted(
            cleaned,
            key=lambda item: (
                round(item.start[0], 6),
                round(item.start[1], 6),
                round(item.end[0], 6),
                round(item.end[1], 6),
            ),
        )
    )


def extract_native_structures(paths: tuple[NativePath, ...]) -> tuple[NativeStructure, ...]:
    """Detect the repeated cyan circular manhole symbol used by the selected KMC CAD map."""

    structures: list[NativeStructure] = []
    for path in paths:
        endpoints_close = hypot(
            path.points[0][0] - path.points[-1][0],
            path.points[0][1] - path.points[-1][1],
        ) < 0.5
        if (
            path.stroke_rgb != (0.0, 1.0, 1.0)
            or (not path.closed and not endpoints_close)
            or len(path.points) < 9
        ):
            continue
        xs = [point[0] for point in path.points]
        ys = [point[1] for point in path.points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        if not (12.0 <= width <= 16.0 and 12.0 <= height <= 16.0):
            continue
        if min(width, height) / max(width, height) < 0.9:
            continue
        structures.append(
            NativeStructure(
                point=((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0),
                symbol_width_points=width,
                symbol_height_points=height,
            )
        )
    return tuple(sorted(structures, key=lambda item: item.point))


def drainage_labels(
    spans: tuple[NativeTextSpan, ...],
    *,
    page_width: float,
    page_height: float,
) -> tuple[NativeTextSpan, ...]:
    labels = [
        span
        for span in spans
        if _DRAIN_LABEL.search(span.text)
        and 5.0 < span.point[0] < page_width - 5.0
        and 5.0 < span.point[1] < page_height - 5.0
    ]
    return tuple(sorted(labels, key=lambda item: (item.point, item.text)))


def is_manhole_label(text: str) -> bool:
    return _MANHOLE_LABEL.search(text) is not None
