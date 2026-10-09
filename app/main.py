from decimal import Decimal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import InvoiceRecord, LineItemRecord, get_session
from app.embeddings import attach_embedding
from app.extractor import ExtractionError, extract_invoice
from app.pdf_reader import PdfReadError, extract_text
from app.routes_ask import router as ask_router
from app.schemas import ExtractResponse, InvoiceSummary, SaveInvoiceRequest

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Mọi endpoint (trừ /health) đều yêu cầu khóa API
protected = [Depends(require_api_key)]

app = FastAPI(title="AI Inbox Automation")
app.include_router(ask_router, dependencies=protected)


def to_decimal(value: float | None) -> Decimal | None:
    """float -> Decimal qua chuỗi, để lưu vào cột NUMERIC không bị sai số dấu phẩy động."""
    return None if value is None else Decimal(str(value))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse, dependencies=protected)
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


@app.post("/invoices", response_model=InvoiceSummary, status_code=201, dependencies=protected)
def save_invoice(
    payload: SaveInvoiceRequest,
    response: Response,
    session: Session = Depends(get_session),
):
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
        # Hóa đơn này (cùng nhà cung cấp và số hóa đơn) đã được lưu: trả lại bản cũ, không báo lỗi
        existing = session.scalar(
            select(InvoiceRecord).where(
                InvoiceRecord.vendor_name == invoice.vendor_name,
                InvoiceRecord.invoice_number == invoice.invoice_number,
            )
        )
        if existing is None:
            raise HTTPException(
                status_code=409, detail="Could not save the invoice because of a database constraint"
            ) from error
        response.status_code = 200
        return existing

    session.refresh(record)  # nạp lại các giá trị do database tự sinh (id, created_at)
    attach_embedding(session, record)  # cố gắng tạo vector; lỗi cũng không làm hỏng việc lưu
    return record


@app.get("/invoices", response_model=list[InvoiceSummary], dependencies=protected)
def list_invoices(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(InvoiceRecord).order_by(InvoiceRecord.created_at.desc()).limit(limit)
    if status:
        query = query.where(InvoiceRecord.status == status)
    return session.scalars(query).all()