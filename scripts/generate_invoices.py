"""Sinh hóa đơn PDF giả + file đáp án chuẩn (ground truth) để test và đánh giá."""

import json
import random
from datetime import timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from faker import Faker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ---- Cấu hình ----
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
NUM_INVOICES = 10
SEED = 42  # cố định seed để mỗi lần chạy ra cùng một bộ dữ liệu
CURRENCIES = ["USD", "EUR", "GBP"]
TAX_RATES = [0, 5, 8, 10]

ITEM_CATALOG = [
    "Web design services",
    "Monthly hosting",
    "Software license",
    "Consulting (per hour)",
    "Office supplies",
    "Marketing campaign",
    "Data entry services",
    "Equipment rental",
]

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)


def make_invoice_data(index: int) -> dict:
    """Tạo dữ liệu cho một hóa đơn. Đây cũng chính là đáp án chuẩn."""
    invoice_date = fake.date_between(start_date="-90d", end_date="today")
    due_date = invoice_date + timedelta(days=random.choice([14, 30, 45]))

    line_items = []
    for description in random.sample(ITEM_CATALOG, k=random.randint(1, 5)):
        quantity = random.randint(1, 10)
        unit_price = round(random.uniform(20, 500), 2)
        line_items.append(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": round(quantity * unit_price, 2),
            }
        )

    subtotal = round(sum(item["line_total"] for item in line_items), 2)
    tax_rate = random.choice(TAX_RATES)
    tax_amount = round(subtotal * tax_rate / 100, 2)

    return {
        "invoice_number": f"INV-2026-{index:04d}",
        "vendor_name": fake.company(),
        "vendor_address": fake.address().replace("\n", ", "),
        "customer_name": fake.company(),
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "currency": random.choice(CURRENCIES),
        "line_items": line_items,
        "subtotal": subtotal,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total": round(subtotal + tax_amount, 2),
    }


def render_pdf(data: dict, path: Path) -> None:
    """Vẽ dữ liệu hóa đơn thành file PDF."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    story = []  # danh sách các thành phần, ReportLab sẽ vẽ lần lượt từ trên xuống
    story.append(Paragraph(escape(data["vendor_name"]), styles["Title"]))
    story.append(Paragraph(escape(data["vendor_address"]), styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(f"INVOICE {data['invoice_number']}", styles["Heading2"]))
    story.append(
        Paragraph(
            f"Invoice date: {data['invoice_date']}<br/>Due date: {data['due_date']}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"<b>Bill to:</b> {escape(data['customer_name'])}", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    # Bảng các dòng hàng
    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for item in data["line_items"]:
        rows.append(
            [
                item["description"],
                str(item["quantity"]),
                f"{item['unit_price']:.2f}",
                f"{item['line_total']:.2f}",
            ]
        )
    items_table = Table(rows, colWidths=[85 * mm, 20 * mm, 32 * mm, 33 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    # Bảng tổng tiền, căn phải
    totals = [
        ["Subtotal", f"{data['subtotal']:.2f}"],
        [f"Tax ({data['tax_rate']}%)", f"{data['tax_amount']:.2f}"],
        [f"TOTAL ({data['currency']})", f"{data['total']:.2f}"],
    ]
    totals_table = Table(totals, colWidths=[40 * mm, 32 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
            ]
        )
    )
    story.append(totals_table)

    doc.build(story)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    for i in range(1, NUM_INVOICES + 1):
        data = make_invoice_data(i)
        filename = f"invoice_{i:03d}.pdf"
        render_pdf(data, OUTPUT_DIR / filename)
        records.append({"file": filename, **data})

    truth_path = OUTPUT_DIR / "ground_truth.json"
    truth_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Đã tạo {NUM_INVOICES} hóa đơn và {truth_path.name} trong {OUTPUT_DIR}")


if __name__ == "__main__":
    main()