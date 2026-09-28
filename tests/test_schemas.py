import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import Invoice

TRUTH_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "ground_truth.json"


@pytest.fixture
def record() -> dict:
    """Lấy hóa đơn đầu tiên trong đáp án chuẩn, mỗi test nhận một bản riêng."""
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))[0]


def test_ground_truth_record_is_valid(record):
    invoice = Invoice.model_validate(record)
    assert invoice.totals_issues() == []


def test_wrong_total_is_flagged(record):
    record["total"] += 50  # cố tình làm sai tổng tiền
    invoice = Invoice.model_validate(record)
    assert invoice.totals_issues() != []


def test_bad_currency_is_rejected(record):
    record["currency"] = "dollars"  # sai định dạng, phải bị từ chối
    with pytest.raises(ValidationError):
        Invoice.model_validate(record)
        