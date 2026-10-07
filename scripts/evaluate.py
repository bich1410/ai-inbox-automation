"""Chạy trích xuất trên toàn bộ hóa đơn mẫu và chấm điểm so với ground_truth.json."""

import json
import time
from collections import defaultdict
from pathlib import Path

from app.config import settings
from app.extractor import ExtractionError, extract_invoice
from app.pdf_reader import PdfReadError, extract_text

ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT / "data" / "samples"
RESULTS_DIR = ROOT / "data" / "eval_results"

TEXT_FIELDS = ["invoice_number", "vendor_name", "vendor_address", "customer_name", "currency"]
DATE_FIELDS = ["invoice_date", "due_date"]
NUMBER_FIELDS = ["subtotal", "tax_rate", "tax_amount", "total"]
ALL_FIELDS = TEXT_FIELDS + DATE_FIELDS + NUMBER_FIELDS + ["line_items"]
ITEM_NUMBER_KEYS = ["quantity", "unit_price", "line_total"]
TOLERANCE = 0.01  # cho phép lệch 1 xu do làm tròn


def normalize(value):
    """Chuẩn hóa để so sánh chuỗi: bỏ khoảng trắng thừa, không phân biệt hoa thường."""
    if value is None:
        return None
    return " ".join(str(value).split()).casefold()


def same_number(expected, predicted) -> bool:
    if expected is None or predicted is None:
        return expected is predicted  # cùng là None thì coi là đúng
    return abs(float(expected) - float(predicted)) <= TOLERANCE


def items_match(expected_items, predicted_items) -> bool:
    """Các dòng hàng đúng khi cùng số dòng và từng dòng khớp mô tả, số lượng, đơn giá, thành tiền."""
    if len(expected_items) != len(predicted_items):
        return False
    for expected, predicted in zip(expected_items, predicted_items):
        if normalize(expected["description"]) != normalize(predicted["description"]):
            return False
        if not all(same_number(expected[key], predicted[key]) for key in ITEM_NUMBER_KEYS):
            return False
    return True


def field_is_correct(field, expected, predicted) -> bool:
    if field == "line_items":
        return items_match(expected[field], predicted[field])
    if field in NUMBER_FIELDS:
        return same_number(expected[field], predicted[field])
    return normalize(expected[field]) == normalize(predicted[field])  # chuỗi và ngày (dạng YYYY-MM-DD)


def main() -> None:
    truth = json.loads((SAMPLES_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    total = len(truth)

    correct = defaultdict(int)  # số hóa đơn đúng cho từng trường
    failures = []
    perfect = 0
    needs_review = 0
    latencies = []

    for record in truth:
        pdf_bytes = (SAMPLES_DIR / record["file"]).read_bytes()
        started = time.perf_counter()
        try:
            invoice = extract_invoice(extract_text(pdf_bytes))
        except (PdfReadError, ExtractionError) as error:
            print(f"[ERROR] {record['file']}: {error}")
            failures.append({"file": record["file"], "error": str(error)})
            continue
        latencies.append(time.perf_counter() - started)

        predicted = invoice.model_dump(mode="json")  # Invoice -> dict thường, ngày thành chuỗi ISO
        if invoice.totals_issues():
            needs_review += 1

        wrong = {}
        for field in ALL_FIELDS:
            if field_is_correct(field, record, predicted):
                correct[field] += 1
            else:
                wrong[field] = {"expected": record[field], "got": predicted[field]}

        if wrong:
            failures.append({"file": record["file"], "wrong_fields": wrong})
            print(f"[DIFF]  {record['file']}: {', '.join(wrong)}")
        else:
            perfect += 1
            print(f"[OK]    {record['file']}")

    average = sum(latencies) / len(latencies) if latencies else None

    print(f"\n=== Kết quả ({settings.llm_model}) ===")
    print(f"Hóa đơn đúng hoàn toàn: {perfect}/{total}")
    print(f"Bị chuyển sang duyệt tay: {needs_review}/{total}")
    if average is not None:
        print(f"Thời gian trung bình: {average:.1f}s mỗi hóa đơn")
    print("\nĐộ chính xác theo trường:")
    for field in ALL_FIELDS:
        print(f"  {field:<16} {correct[field]}/{total}  ({correct[field] / total:.0%})")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "model": settings.llm_model,
        "invoices": total,
        "perfect": perfect,
        "needs_review": needs_review,
        "avg_seconds": round(average, 2) if average is not None else None,
        "field_accuracy": {field: round(correct[field] / total, 3) for field in ALL_FIELDS},
        "failures": failures,
    }
    output_path = RESULTS_DIR / f"{settings.llm_model}.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nĐã lưu báo cáo: {output_path}")


if __name__ == "__main__":
    main()