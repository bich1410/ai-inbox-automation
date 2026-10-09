from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app, headers={"X-API-Key": settings.app_api_key})


def test_extract_rejects_non_pdf_upload():
    response = client.post("/extract", files={"file": ("note.txt", b"hello", "text/plain")})
    assert response.status_code == 400