from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.embeddings import build_embedding_text


def test_embedding_text_mentions_vendor_and_items():
    record = SimpleNamespace(
        invoice_number="INV-1",
        vendor_name="Acme Ltd",
        customer_name=None,
        invoice_date=date(2026, 8, 1),
        total=Decimal("120.50"),
        currency="USD",
        line_items=[
            SimpleNamespace(description="Monthly hosting", quantity=Decimal("2.000"), unit_price=Decimal("60.25"))
        ],
    )
    text = build_embedding_text(record)
    assert "Acme Ltd" in text
    assert "Monthly hosting" in text
    assert "unknown customer" in text