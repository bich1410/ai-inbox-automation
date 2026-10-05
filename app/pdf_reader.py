"""Rút chữ từ file PDF."""

import io

import pdfplumber


class PdfReadError(Exception):
    """File không đọc được hoặc không có chữ."""


def extract_text(pdf_bytes: bytes) -> str:
    try:
        # pdfplumber cần một "file-like object", BytesIO biến bytes trong RAM thành dạng đó
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as error:
        raise PdfReadError("Cannot open the file as a PDF") from error

    text = "\n\n".join(pages).strip()
    if not text:
        raise PdfReadError("No text found in the PDF. It may be a scanned image that needs OCR")
    return text