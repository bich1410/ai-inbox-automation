"""Thử tìm kiếm ngữ nghĩa: python -m scripts.try_search "your question here"."""

import sys

from sqlalchemy import select

from app.db import InvoiceRecord, SessionLocal
from app.embeddings import embed_query


def main() -> None:
    question = " ".join(sys.argv[1:]) or "website design work"
    query_vector = embed_query(question)

    with SessionLocal() as session:
        distance = InvoiceRecord.embedding.cosine_distance(query_vector)
        rows = session.execute(
            select(InvoiceRecord, distance.label("distance"))
            .where(InvoiceRecord.embedding.is_not(None))
            .order_by(distance)
            .limit(5)
        ).all()

        print(f'Câu hỏi: "{question}"\n')
        for record, dist in rows:
            items = ", ".join(item.description for item in record.line_items)
            print(f"{dist:.3f}  {record.invoice_number}  {record.vendor_name}  [{items}]")


if __name__ == "__main__":
    main()