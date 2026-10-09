from fastapi.testclient import TestClient

from app.main import app

anonymous = TestClient(app)  # client không gửi khóa


def test_health_is_public():
    assert anonymous.get("/health").status_code == 200


def test_protected_endpoints_reject_missing_key():
    assert anonymous.get("/invoices").status_code == 401
    assert anonymous.post("/ask", json={"question": "hello there"}).status_code == 401
    assert anonymous.post("/extract", files={"file": ("a.pdf", b"%PDF-", "application/pdf")}).status_code == 401


def test_wrong_key_is_rejected():
    response = anonymous.get("/invoices", headers={"X-API-Key": "this-is-not-the-key"})
    assert response.status_code == 401