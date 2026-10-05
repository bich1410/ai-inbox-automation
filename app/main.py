from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import settings
from app.extractor import ExtractionError, extract_invoice
from app.pdf_reader import PdfReadError, extract_text
from app.schemas import ExtractResponse

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="AI Inbox Automation")


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.llm_provider}


@app.post("/extract", response_model=ExtractResponse)
def extract(file: UploadFile = File(...)):
    pdf_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 10 MB")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        text = extract_text(pdf_bytes)
    except PdfReadError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        invoice = extract_invoice(text)
    except ExtractionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    issues = invoice.totals_issues()
    return ExtractResponse(invoice=invoice, issues=issues, needs_review=bool(issues))