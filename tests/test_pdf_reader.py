import json
from pathlib import Path

import pytest

from app.pdf_reader import PdfReadError, extract_text

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def test_extract_text_contains_known_fields():
    truth = json.loads((SAMPLES / "ground_truth.json").read_text(encoding="utf-8"))[0]
    text = extract_text((SAMPLES / truth["file"]).read_bytes())
    assert truth["invoice_number"] in text
    assert f"{truth['total']:.2f}" in text


def test_non_pdf_bytes_are_rejected():
    with pytest.raises(PdfReadError):
        extract_text(b"this is not a pdf")