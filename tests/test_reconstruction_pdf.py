from floodguard.reconstruction.contracts import ExtractionMode
from floodguard.reconstruction.pdf_native import (
    clean_native_drain_paths,
    drainage_labels,
    extract_native_structures,
    inspect_native_pdf,
)
from tests.reconstruction_fixtures import synthetic_pdf


def test_native_pdf_inspection_precedes_ocr_and_extracts_symbols() -> None:
    extraction = inspect_native_pdf(synthetic_pdf())
    assert extraction.inspection.extraction_mode is ExtractionMode.NATIVE_VECTOR_TEXT
    assert extraction.inspection.ocr_used is False
    assert extraction.inspection.native_vector_path_count == 4
    assert extraction.inspection.native_text_span_count == 2

    drains = clean_native_drain_paths(extraction.paths)
    structures = extract_native_structures(extraction.paths)
    labels = drainage_labels(
        extraction.text_spans,
        page_width=extraction.inspection.page_width_points,
        page_height=extraction.inspection.page_height_points,
    )
    assert len(drains) == 1
    assert drains[0].source_fragment_count == 3
    assert len(structures) == 1
    assert len(labels) == 2

