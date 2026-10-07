from decimal import Decimal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import InvoiceRecord, LineItemRecord, get_session
from app.extractor import ExtractionError, extract_invoice
from app.pdf_reader import PdfReadError, extract_text
from app.schemas import ExtractResponse, InvoiceSummary, SaveInvoiceRequest

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="AI Inbox Automation")


def to_decimal(value: float | None) -> Decimal | None:
    """float -> Decimal qua chuỗi, để lưu vào cột NUMERIC không bị sai số dấu phẩy động."""
    return None if value is None else Decimal(str(value))


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


@app.post("/invoices", response_model=InvoiceSummary, status_code=201)
def save_invoice(payload: SaveInvoiceRequest, session: Session = Depends(get_session)):
    invoice = payload.invoice

    # Server tự kiểm tra lại, không tin phía gọi
    issues = invoice.totals_issues()
    if issues and payload.status == "auto_approved":
        raise HTTPException(
            status_code=422,
            detail="This invoice has issues and must be reviewed by a human before it is saved",
        )

    record = InvoiceRecord(
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        vendor_address=invoice.vendor_address,
        customer_name=invoice.customer_name,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        subtotal=to_decimal(invoice.subtotal),
        tax_rate=to_decimal(invoice.tax_rate),
        tax_amount=to_decimal(invoice.tax_amount),
        total=to_decimal(invoice.total),
        status=payload.status,
        issues=issues,
        source=payload.source,
        line_items=[
            LineItemRecord(
                description=item.description,
                quantity=to_decimal(item.quantity),
                unit_price=to_decimal(item.unit_price),
                line_total=to_decimal(item.line_total),
            )
            for item in invoice.line_items
        ],
    )
    session.add(record)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Invoice {invoice.invoice_number} from {invoice.vendor_name} already exists",
        ) from error

    session.refresh(record)  # nạp lại các giá trị do database tự sinh (id, created_at)
    return record


@app.get("/invoices", response_model=list[InvoiceSummary])
def list_invoices(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(InvoiceRecord).order_by(InvoiceRecord.created_at.desc()).limit(limit)
    if status:
        query = query.where(InvoiceRecord.status == status)
    return session.scalars(query).all()