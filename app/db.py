"""Kết nối PostgreSQL và định nghĩa các bảng."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url
for prefix in ("postgresql://", "postgres://"):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix):]
        break

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # kiểm tra kết nối còn sống trước khi dùng (database Neon có thể đã ngủ)
    connect_args={"connect_timeout": 15},  # đợi tối đa 15 giây khi đánh thức database
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Lớp cha của mọi bảng."""


class InvoiceRecord(Base):
    __tablename__ = "invoices"
    # Cùng nhà cung cấp mà trùng số hóa đơn thì là cùng một hóa đơn
    __table_args__ = (UniqueConstraint("vendor_name", "invoice_number", name="uq_vendor_invoice_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(100))
    vendor_name: Mapped[str] = mapped_column(String(255))
    vendor_address: Mapped[str | None] = mapped_column(Text)
    customer_name: Mapped[str | None] = mapped_column(String(255))
    invoice_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    # auto_approved | approved | rejected
    status: Mapped[str] = mapped_column(String(20))
    issues: Mapped[list] = mapped_column(JSONB, default=list)  # các cảnh báo từ totals_issues()
    source: Mapped[str | None] = mapped_column(String(50))  # ví dụ gmail, webhook
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    line_items: Mapped[list["LineItemRecord"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class LineItemRecord(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    invoice: Mapped["InvoiceRecord"] = relationship(back_populates="line_items")


def get_session():
    """Mỗi request một phiên làm việc, xong thì tự đóng."""
    with SessionLocal() as session:
        yield session