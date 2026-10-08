"""Các công cụ truy vấn hóa đơn mà agent được phép gọi. Mọi câu SQL đều do ta viết sẵn."""

import logging
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import InvoiceRecord
from app.embeddings import EmbeddingError, embed_query

logger = logging.getLogger(__name__)

MAX_ROWS = 20


class InvoiceFilters(BaseModel):
    """Các bộ lọc dùng chung. Trường nào để trống thì không lọc theo trường đó."""

    vendor_name: str | None = Field(default=None, max_length=100)
    customer_name: str | None = Field(default=None, max_length=100)
    date_from: date | None = None
    date_to: date | None = None
    status: Literal["auto_approved", "approved", "rejected"] | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    min_total: float | None = Field(default=None, ge=0)
    max_total: float | None = Field(default=None, ge=0)


class SearchInvoicesArgs(InvoiceFilters):
    limit: int = Field(default=10, ge=1, le=MAX_ROWS)


class InvoiceStatsArgs(InvoiceFilters):
    group_by: Literal["none", "vendor", "customer", "month", "status"] = "none"


class SemanticSearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=5, ge=1, le=10)


def _apply_filters(statement, filters: InvoiceFilters):
    """Thêm các điều kiện WHERE tương ứng với những bộ lọc có giá trị."""
    if filters.vendor_name:
        statement = statement.where(InvoiceRecord.vendor_name.icontains(filters.vendor_name, autoescape=True))
    if filters.customer_name:
        statement = statement.where(InvoiceRecord.customer_name.icontains(filters.customer_name, autoescape=True))
    if filters.date_from:
        statement = statement.where(InvoiceRecord.invoice_date >= filters.date_from)
    if filters.date_to:
        statement = statement.where(InvoiceRecord.invoice_date <= filters.date_to)
    if filters.status:
        statement = statement.where(InvoiceRecord.status == filters.status)
    if filters.currency:
        statement = statement.where(InvoiceRecord.currency == filters.currency.upper())
    if filters.min_total is not None:
        statement = statement.where(InvoiceRecord.total >= filters.min_total)
    if filters.max_total is not None:
        statement = statement.where(InvoiceRecord.total <= filters.max_total)
    return statement


def _invoice_to_dict(record: InvoiceRecord, distance: float | None = None) -> dict:
    data = {
        "invoice_number": record.invoice_number,
        "vendor_name": record.vendor_name,
        "customer_name": record.customer_name,
        "invoice_date": record.invoice_date.isoformat(),
        "currency": record.currency,
        "total": float(record.total),
        "status": record.status,
        "has_issues": bool(record.issues),
        "items": [item.description for item in record.line_items],
    }
    if distance is not None:
        data["distance"] = round(distance, 3)
    return data


def search_invoices(session: Session, args: SearchInvoicesArgs) -> dict:
    statement = (
        _apply_filters(select(InvoiceRecord), args)
        .order_by(InvoiceRecord.invoice_date.desc(), InvoiceRecord.id.desc())
        .limit(args.limit + 1)  # lấy thừa 1 dòng để biết còn kết quả bị cắt không
    )
    records = session.scalars(statement).all()
    return {
        "invoices": [_invoice_to_dict(record) for record in records[: args.limit]],
        "truncated": len(records) > args.limit,
    }


def invoice_stats(session: Session, args: InvoiceStatsArgs) -> dict:
    group_columns = {
        "none": None,
        "vendor": InvoiceRecord.vendor_name,
        "customer": InvoiceRecord.customer_name,
        "month": func.to_char(InvoiceRecord.invoice_date, "YYYY-MM"),
        "status": InvoiceRecord.status,
    }
    group_column = group_columns[args.group_by]

    columns = [
        InvoiceRecord.currency,
        func.count().label("invoice_count"),
        func.sum(InvoiceRecord.total).label("total_sum"),
    ]
    group_by = [InvoiceRecord.currency]  # luôn tách theo loại tiền tệ
    if group_column is not None:
        columns.insert(0, group_column.label("group_value"))
        group_by.insert(0, group_column)

    statement = _apply_filters(select(*columns), args).group_by(*group_by).order_by(*group_by).limit(50)

    results = []
    for row in session.execute(statement).all():
        item = {
            "currency": row.currency,
            "invoice_count": row.invoice_count,
            "total_sum": float(row.total_sum),
        }
        if group_column is not None:
            item = {"group": row.group_value, **item}
        results.append(item)

    return {"note": "Totals are per currency and must never be added across currencies.", "rows": results}


def semantic_search_invoices(session: Session, args: SemanticSearchArgs) -> dict:
    query_vector = embed_query(args.query)
    distance = InvoiceRecord.embedding.cosine_distance(query_vector)
    rows = session.execute(
        select(InvoiceRecord, distance.label("distance"))
        .where(InvoiceRecord.embedding.is_not(None))
        .order_by(distance)
        .limit(args.limit)
    ).all()
    return {
        "note": "Closest matches first. A lower distance means a closer match in meaning.",
        "invoices": [_invoice_to_dict(record, dist) for record, dist in rows],
    }


# Tên công cụ -> (khuôn tham số, hàm chạy)
TOOLS = {
    "search_invoices": (SearchInvoicesArgs, search_invoices),
    "invoice_stats": (InvoiceStatsArgs, invoice_stats),
    "semantic_search_invoices": (SemanticSearchArgs, semantic_search_invoices),
}


def run_tool(session: Session, name: str, raw_args: dict) -> dict:
    """Chạy một công cụ do LLM yêu cầu. Lỗi luôn được trả về dạng dict để LLM đọc được, không làm sập server."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}

    args_model, function = TOOLS[name]
    try:
        args = args_model.model_validate(raw_args)
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        return {"error": f"Invalid arguments: {problems}"}

    try:
        return function(session, args)
    except EmbeddingError:
        logger.exception("Embedding failed in tool %s", name)
        return {"error": "Semantic search is unavailable right now."}
    except SQLAlchemyError:
        logger.exception("Database error in tool %s", name)
        session.rollback()
        return {"error": "Database error. Please try again later."}