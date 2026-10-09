"""Thử trích xuất một PDF: python -m scripts.try_extract <đường dẫn PDF> [auto|pdf]"""

import json
import sys
from pathlib import Path

from app.extractor import extract_from_pdf_bytes

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"
KEY_FIELDS = ["invoice_number", "vendor_name", "customer_name", "invoice_date", "due_date", "currency", "subtotal", "tax_amount", "total"]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Cách dùng: python -m scripts.try_extract <đường dẫn PDF> [auto|pdf]")
    path = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "auto"

    outcome = extract_from_pdf_bytes(path.read_bytes(), mode=mode)
    print(
        f"Đường đọc: {outcome.path} | model: {outcome.model} | "
        f"token vào/ra: {outcome.input_tokens}/{outcome.output_tokens}"
    )

    predicted = outcome.invoice.model_dump(mode="json")
    truth = {record["file"]: record for record in json.loads(TRUTH_PATH.read_text(encoding="utf-8"))}.get(path.name)

    print(f"\n{'Trường':<16} {'Đáp án':<28} Model trả")
    for field in KEY_FIELDS:
        expected = truth[field] if truth else "-"
        mark = "" if not truth or str(expected) == str(predicted[field]) else "   <-- KHÁC"
        print(f"{field:<16} {str(expected):<28} {predicted[field]}{mark}")

    print("\nSố dòng hàng:", len(predicted["line_items"]), "| đáp án:", len(truth["line_items"]) if truth else "-")
    print("Cảnh báo số liệu:", outcome.invoice.totals_issues() or "không")


if __name__ == "__main__":
    main()