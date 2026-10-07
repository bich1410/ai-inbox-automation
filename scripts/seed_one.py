"""Gửi một hóa đơn mẫu tới POST /invoices. Chạy hai lần để thấy lỗi 409 (trùng)."""

import json
from pathlib import Path

import httpx

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"


def main() -> None:
    # Dùng hóa đơn thứ hai (invoice_002), để hóa đơn 001 dành cho thử nghiệm qua n8n
    record = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))[1]
    payload = {"invoice": record, "status": "auto_approved", "source": "seed_script"}

    response = httpx.post("http://127.0.0.1:8000/invoices", json=payload, timeout=30)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()