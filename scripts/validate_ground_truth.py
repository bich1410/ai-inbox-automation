"""Kiểm tra schema Invoice có đọc được toàn bộ ground_truth.json không."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas import Invoice

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"


def main() -> None:
    records = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    ok_count = 0

    for record in records:
        try:
            invoice = Invoice.model_validate(record)
        except ValidationError as error:
            print(f"[SCHEMA ERROR] {record['file']}\n{error}\n")
            continue

        issues = invoice.totals_issues()
        if issues:
            print(f"[LOGIC ISSUE] {record['file']}: {issues}")
        else:
            ok_count += 1
            print(f"[OK] {record['file']}  {invoice.vendor_name} - {invoice.total:.2f} {invoice.currency}")

    print(f"\n{ok_count}/{len(records)} hóa đơn hợp lệ")


if __name__ == "__main__":
    main()