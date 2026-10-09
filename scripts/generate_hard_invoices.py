"""Tạo bộ hóa đơn khó từ ground_truth.json: bố cục khác, bản scan sạch, bản scan nhiễu.

Mọi bộ đều dùng chung đáp án chuẩn (ground_truth.json), chỉ khác cách hiển thị.
"""

import json
import random
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "data" / "samples"
HARD_DIR = ROOT / "data" / "hard"
SEED = 7  # cố định để mỗi lần chạy ra cùng một bộ dữ liệu


def format_date(value: str | None) -> str:
    return date.fromisoformat(value).strftime("%d %b %Y") if value else "-"


def money(currency: str, amount: float) -> str:
    return f"{currency} {amount:,.2f}"


def render_layout_b(record: dict, path: Path) -> None:
    """Vẽ hóa đơn theo một bố cục khác hẳn bản gốc."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    currency = record["currency"]
    reference = f"PO-{int(record['invoice_number'][-4:]) + 7000}"  # mã gây nhiễu, không phải số hóa đơn

    story = [Paragraph("TAX INVOICE", styles["Heading1"]), Spacer(1, 4 * mm)]

    meta = Table(
        [
            ["Bill No.", record["invoice_number"]],
            ["Issued", format_date(record["invoice_date"])],
            ["Payment due", format_date(record.get("due_date"))],
            ["Customer ref", reference],
        ],
        colWidths=[35 * mm, 60 * mm],
        hAlign="LEFT",
    )
    meta.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [meta, Spacer(1, 8 * mm)]

    parties = Table(
        [
            [
                Paragraph(
                    "<b>FROM</b><br/>" + escape(record["vendor_name"]) + "<br/>" + escape(record.get("vendor_address") or ""),
                    styles["Normal"],
                ),
                Paragraph("<b>BILLED TO</b><br/>" + escape(record.get("customer_name") or ""), styles["Normal"]),
            ]
        ],
        colWidths=[95 * mm, 75 * mm],
    )
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [parties, Spacer(1, 8 * mm)]

    rows = [["Item", "Qty", "Rate", "Line total"]]
    for item in record["line_items"]:
        rows.append(
            [
                item["description"],
                f"{item['quantity']:g}",
                money(currency, item["unit_price"]),
                money(currency, item["line_total"]),
            ]
        )
    items_table = Table(rows, colWidths=[75 * mm, 18 * mm, 38 * mm, 39 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDE6F0")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story += [items_table, Spacer(1, 6 * mm)]

    tax_rate = record.get("tax_rate") or 0
    summary = Table(
        [
            ["Net", money(currency, record["subtotal"])],
            [f"VAT ({tax_rate:g}%)", money(currency, record["tax_amount"])],
            ["Balance due", money(currency, record["total"])],
        ],
        colWidths=[40 * mm, 45 * mm],
        hAlign="RIGHT",
    )
    summary.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
            ]
        )
    )
    story += [summary, Spacer(1, 12 * mm), Paragraph("Payment by bank transfer. Thank you for your business.", styles["Normal"])]

    doc.build(story)


def rasterize(pdf_path: Path, dpi: int) -> Image.Image:
    """Vẽ trang đầu của PDF thành ảnh (PDF chuẩn hiển thị ở 72 dpi)."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return pdf[0].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        pdf.close()


def make_noisy(image: Image.Image, rng: random.Random) -> Image.Image:
    """Làm ảnh giống bản scan kém: nghiêng nhẹ, mờ, nhiễu hạt, tương phản thấp."""
    angle = rng.uniform(-1.5, 1.5)
    image = image.rotate(angle, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    image = image.filter(ImageFilter.GaussianBlur(radius=0.8))
    gray = image.convert("L")
    noise = Image.effect_noise(gray.size, 18)  # ảnh nhiễu có giá trị trung bình 128
    gray = ImageChops.add(gray, noise, scale=1.0, offset=-128)  # cộng nhiễu vào ảnh gốc
    return ImageEnhance.Contrast(gray).enhance(0.85)


def main() -> None:
    records = json.loads((SAMPLES_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)

    folders = {name: HARD_DIR / name for name in ("layout_b", "scan_clean", "scan_noisy")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)

    for record in records:
        name = record["file"]
        source = SAMPLES_DIR / name

        render_layout_b(record, folders["layout_b"] / name)
        rasterize(source, 150).save(folders["scan_clean"] / name, "PDF", resolution=150)
        make_noisy(rasterize(source, 110), rng).save(folders["scan_noisy"] / name, "PDF", resolution=110)
        print(f"[OK] {name}")

    print(f"\nĐã tạo {len(records)} hóa đơn cho mỗi bộ trong {HARD_DIR}")


if __name__ == "__main__":
    main()