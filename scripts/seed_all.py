"""Nạp toàn bộ hóa đơn mẫu vào database qua POST /invoices (hóa đơn đã có thì bỏ qua)."""

import json
from pathlib import Path

import httpx

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"


def main() -> None:
    records = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    created = existing = 0

    with httpx.Client(timeout=30) as client:
        for record in records:
            payload = {"invoice": record, "status": "auto_approved", "source": "seed_script"}
            response = client.post("http://127.0.0.1:8000/invoices", json=payload)
            if response.status_code == 201:
                created += 1
            elif response.status_code == 200:
                existing += 1
            else:
                print(f"[ERROR] {record['file']}: {response.status_code} {response.text}")

    print(f"Đã tạo mới: {created}, đã có sẵn: {existing}")


if __name__ == "__main__":
    main()