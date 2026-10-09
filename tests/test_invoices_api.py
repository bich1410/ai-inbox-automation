import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app, headers={"X-API-Key": settings.app_api_key})

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"


def sample_record() -> dict:
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))[0]


def test_invoice_with_issues_cannot_be_auto_approved():
    record = sample_record()
    record["total"] += 50  # cố tình làm lệch tổng tiền
    response = client.post("/invoices", json={"invoice": record, "status": "auto_approved"})
    assert response.status_code == 422
    assert "reviewed by a human" in response.json()["detail"]


def test_unknown_status_is_rejected():
    response = client.post("/invoices", json={"invoice": sample_record(), "status": "banana"})
    assert response.status_code == 422