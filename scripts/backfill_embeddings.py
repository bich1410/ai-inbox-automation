"""Tạo embedding cho mọi hóa đơn chưa có (chạy lại nhiều lần cũng không sao)."""

import time

from sqlalchemy import select

from app.db import InvoiceRecord, SessionLocal
from app.embeddings import EmbeddingError, build_embedding_text, embed_document


def main() -> None:
    done = failed = 0

    with SessionLocal() as session:
        records = session.scalars(
            select(InvoiceRecord).where(InvoiceRecord.embedding.is_(None)).order_by(InvoiceRecord.id)
        ).all()
        print(f"Cần tạo embedding cho {len(records)} hóa đơn")

        for record in records:
            try:
                record.embedding = embed_document(build_embedding_text(record))
                session.commit()
                done += 1
                print(f"[OK]    {record.invoice_number} - {record.vendor_name}")
            except EmbeddingError as error:
                session.rollback()
                failed += 1
                print(f"[ERROR] {record.invoice_number}: {error}")
            time.sleep(0.5)  # nhẹ tay với hạn mức miễn phí

    print(f"Xong: {done} thành công, {failed} lỗi")


if __name__ == "__main__":
    main()