from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="AI Inbox Automation")


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.llm_provider}