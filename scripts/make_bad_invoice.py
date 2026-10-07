"""Tạo một hóa đơn cố tình sai tổng tiền để thử luồng duyệt tay."""

from scripts.generate_invoices import OUTPUT_DIR, make_invoice_data, render_pdf


def main() -> None:
    data = make_invoice_data(9001)
    data["total"] = round(data["total"] + 50, 2)  # tổng tiền in trên PDF bị lệch 50
    path = OUTPUT_DIR / "needs_review_invoice.pdf"
    render_pdf(data, path)
    print(f"Đã tạo {path} (số hóa đơn {data['invoice_number']}, tổng in trên PDF: {data['total']})")


if __name__ == "__main__":
    main()