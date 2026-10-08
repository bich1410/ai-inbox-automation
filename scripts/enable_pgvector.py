"""Bật pgvector, thêm cột embedding và chỉ mục vào bảng invoices (chạy lại nhiều lần cũng không sao)."""

from sqlalchemy import text

from app.db import EMBEDDING_DIM, engine

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions",
    f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})",
    "CREATE INDEX IF NOT EXISTS invoices_embedding_idx ON invoices USING hnsw (embedding vector_cosine_ops)",
]


def main() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))
            print("OK:", statement)


if __name__ == "__main__":
    main()