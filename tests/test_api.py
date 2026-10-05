from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_extract_rejects_non_pdf_upload():
    response = client.post("/extract", files={"file": ("note.txt", b"hello", "text/plain")})
    assert response.status_code == 400