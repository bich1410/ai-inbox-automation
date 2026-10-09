"""Rút chữ từ file PDF."""

import io

import pdfplumber

MIN_TEXT_CHARS = 30  # ít chữ hơn mức này thì coi như PDF không có lớp chữ (bản scan)


class PdfReadError(Exception):
    """File không đọc được."""


class NoTextLayerError(PdfReadError):
    """PDF mở được nhưng không có lớp chữ, thường là ảnh scan hoặc ảnh chụp."""


def extract_text(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as error:
        raise PdfReadError("Cannot open the file as a PDF") from error

    text = "\n\n".join(pages).strip()
    if len(text) < MIN_TEXT_CHARS:
        raise NoTextLayerError("No text found in the PDF. It looks like a scan or photo")
    return text