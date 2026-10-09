import io
from types import SimpleNamespace

import pytest
from PIL import Image

from app.extractor import _token_usage
from app.pdf_reader import NoTextLayerError, PdfReadError, extract_text


def test_image_only_pdf_has_no_text_layer():
    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), "white").save(buffer, "PDF")  # PDF chỉ có ảnh, không có chữ
    with pytest.raises(NoTextLayerError):
        extract_text(buffer.getvalue())


def test_no_text_layer_is_a_kind_of_pdf_read_error():
    assert issubclass(NoTextLayerError, PdfReadError)


def test_token_usage_is_total_minus_prompt():
    usage = SimpleNamespace(
        prompt_token_count=1000, candidates_token_count=100, thoughts_token_count=50, total_token_count=1160
    )
    assert _token_usage(SimpleNamespace(usage_metadata=usage)) == (1000, 160)


def test_token_usage_falls_back_to_candidates_plus_thoughts():
    usage = SimpleNamespace(
        prompt_token_count=200, candidates_token_count=80, thoughts_token_count=None, total_token_count=None
    )
    assert _token_usage(SimpleNamespace(usage_metadata=usage)) == (200, 80)