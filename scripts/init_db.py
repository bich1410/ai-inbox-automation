"""Tạo các bảng trong database, bật RLS, và kiểm tra kết nối."""

from sqlalchemy import inspect, text

from app.db import Base, engine


def main() -> None:
    with engine.connect() as connection:
        version = connection.execute(text("select version()")).scalar()
        print(f"Kết nối thành công: {version}")

    Base.metadata.create_all(engine)

    # Chặn truy cập qua API công khai của Supabase (server của ta kết nối trực tiếp nên không bị ảnh hưởng)
    with engine.begin() as connection:
        for table_name in ("invoices", "line_items"):
            connection.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))

    print("Các bảng hiện có:", inspect(engine).get_table_names())


if __name__ == "__main__":
    main()