"""Thêm một hóa đơn thử qua POST /invoices rồi kiểm tra vector đã được tạo tự động chưa."""

import time
from datetime import date

import httpx
from sqlalchemy import select

from app.db import InvoiceRecord, SessionLocal


def main() -> None:
    number = f"DEMO-{int(time.time())}"
    invoice = {
        "invoice_number": number,
        "vendor_name": "Nimbus Cloud Services",
        "customer_name": "Baldwin Ltd",
        "invoice_date": date.today().isoformat(),
        "currency": "USD",
        "line_items": [
            {"description": "Cloud GPU server rental", "quantity": 10, "unit_price": 12.5, "line_total": 125.0}
        ],
        "subtotal": 125.0,
        "tax_rate": 10,
        "tax_amount": 12.5,
        "total": 137.5,
    }
    payload = {"invoice": invoice, "status": "auto_approved", "source": "demo"}

    response = httpx.post("http://127.0.0.1:8000/invoices", json=payload, timeout=60)
    print("Mã trạng thái:", response.status_code)

    with SessionLocal() as session:
        record = session.scalar(select(InvoiceRecord).where(InvoiceRecord.invoice_number == number))
        print("Đã lưu:", record is not None)
        print("Có vector:", record is not None and record.embedding is not None)


if __name__ == "__main__":
    main()