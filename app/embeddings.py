"""Tạo embedding (vector ngữ nghĩa) bằng Gemini cho hóa đơn và câu hỏi."""

from google import genai
from google.genai import types

from app.config import settings
from app.db import EMBEDDING_DIM

client = genai.Client(api_key=settings.llm_api_key)


class EmbeddingError(Exception):
    """Gọi API embedding thất bại."""


def build_embedding_text(record) -> str:
    """Đoạn mô tả ngắn của một hóa đơn đã lưu. Vector được tạo từ đoạn này."""
    items = "; ".join(
        f"{item.description} (qty {item.quantity:g} x {item.unit_price})" for item in record.line_items
    )
    customer = record.customer_name or "unknown customer"
    return (
        f"Invoice {record.invoice_number} from {record.vendor_name} to {customer}. "
        f"Date: {record.invoice_date}. Total: {record.total} {record.currency}. "
        f"Items: {items}"
    )


def _embed(text: str, task_type: str) -> list[float]:
    try:
        response = client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM),
        )
    except Exception as error:
        raise EmbeddingError(f"Embedding call failed: {error}") from error
    return list(response.embeddings[0].values)


def embed_document(text: str) -> list[float]:
    """Vector cho nội dung được lưu để tìm sau này (hóa đơn)."""
    return _embed(text, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Vector cho câu hỏi của người dùng."""
    return _embed(text, "RETRIEVAL_QUERY")