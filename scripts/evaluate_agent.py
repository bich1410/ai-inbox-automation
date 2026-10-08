"""Đo agent /ask trên bộ câu hỏi có đáp án tính trực tiếp từ database."""

import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import AgentError, ask_agent
from app.config import settings
from app.db import InvoiceRecord, SessionLocal

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "eval_results"
NUMBER_PATTERN = re.compile(r"\d[\d.,]*\d|\d")
TOLERANCE = 0.011
PAUSE_SECONDS = 2  # nghỉ giữa các câu hỏi để nhẹ tay với hạn mức miễn phí


@dataclass
class Case:
    name: str
    question: str
    expected_tools: set[str] | None  # None nghĩa là agent không được gọi công cụ nào
    numbers: list[float] = field(default_factory=list)  # tất cả phải xuất hiện trong câu trả lời
    all_invoices: list[str] = field(default_factory=list)  # tất cả số hóa đơn này phải xuất hiện
    any_invoices: list[str] = field(default_factory=list)  # ít nhất một số hóa đơn trong danh sách phải xuất hiện


def candidate_values(token: str) -> list[float]:
    """Một chuỗi số có thể viết kiểu 1,234.50 hoặc 1.234,50, nên thử cả hai cách đọc."""
    values = []
    for decimal_separator, thousands_separator in ((".", ","), (",", ".")):
        cleaned = token.replace(thousands_separator, "").replace(decimal_separator, ".")
        try:
            values.append(float(cleaned))
        except ValueError:
            pass
    return values


def contains_number(answer: str, expected: float) -> bool:
    for token in NUMBER_PATTERN.findall(answer):
        if any(abs(value - expected) <= TOLERANCE for value in candidate_values(token)):
            return True
    return False


def group(invoices, key_function) -> dict:
    """Gom hóa đơn theo khóa, trả về {khóa: [số hóa đơn, tổng tiền]}."""
    groups = defaultdict(lambda: [0, 0.0])
    for invoice in invoices:
        entry = groups[key_function(invoice)]
        entry[0] += 1
        entry[1] += float(invoice.total)
    return groups


def month_of(invoice) -> str:
    return invoice.invoice_date.strftime("%Y-%m")


def build_cases(session: Session) -> list[Case]:
    invoices = session.scalars(select(InvoiceRecord).order_by(InvoiceRecord.id)).all()
    if len(invoices) < 5:
        raise SystemExit("Cần ít nhất 5 hóa đơn trong database. Chạy python -m scripts.seed_all trước.")

    cases: list[Case] = []
    stats_or_search = {"invoice_stats", "search_invoices"}

    # 1-2. Số hóa đơn và tổng tiền theo từng loại tiền tệ (tiếng Anh và tiếng Việt)
    by_currency = group(invoices, lambda i: i.currency)
    currency_numbers = [value for count, total in by_currency.values() for value in (count, round(total, 2))]
    cases.append(Case(
        "currency_totals_en",
        "How many invoices are there, and what is the total amount per currency?",
        {"invoice_stats"},
        numbers=currency_numbers,
    ))
    cases.append(Case(
        "currency_totals_vi",
        "Có tất cả bao nhiêu hóa đơn, và tổng tiền theo từng loại tiền tệ là bao nhiêu?",
        {"invoice_stats"},
        numbers=currency_numbers,
    ))

    # 3. Tổng tiền của một nhà cung cấp
    vendor = invoices[0].vendor_name
    vendor_invoices = [i for i in invoices if vendor.lower() in i.vendor_name.lower()]
    vendor_totals = group(vendor_invoices, lambda i: i.currency)
    cases.append(Case(
        "vendor_total",
        f"What is the total amount invoiced by {vendor}?",
        stats_or_search,
        numbers=[round(total, 2) for _, total in vendor_totals.values()],
    ))

    # 4. Các hóa đơn của một khách hàng
    customer = next((i.customer_name for i in invoices if i.customer_name), None)
    if customer:
        customer_invoices = [i.invoice_number for i in invoices if i.customer_name == customer]
        cases.append(Case(
            "customer_invoices",
            f"Which invoices were issued to {customer}?",
            {"search_invoices"},
            all_invoices=customer_invoices,
        ))

    # 5. Số hóa đơn trong tháng có nhiều hóa đơn nhất
    month, month_count = Counter(month_of(i) for i in invoices).most_common(1)[0]
    cases.append(Case(
        "month_count",
        f"How many invoices have an invoice date in {month}?",
        stats_or_search,
        numbers=[month_count],
    ))

    # 6. Tổng tiền theo từng tháng
    by_month = group(invoices, lambda i: (month_of(i), i.currency))
    cases.append(Case(
        "monthly_totals",
        "Show the total amount per month.",
        {"invoice_stats"},
        numbers=[round(total, 2) for _, total in by_month.values()],
    ))

    # 7. Lọc theo ngưỡng tiền trong loại tiền phổ biến nhất
    top_currency = max(by_currency, key=lambda c: by_currency[c][0])
    ranked = sorted((i for i in invoices if i.currency == top_currency), key=lambda i: float(i.total), reverse=True)
    k = min(4, len(ranked) - 1)
    if k >= 1:
        threshold = float(ranked[k].total)
        above = [i.invoice_number for i in ranked if float(i.total) > threshold]
        cases.append(Case(
            "amount_filter",
            f"Which invoices have a total above {threshold:.2f} {top_currency}?",
            {"search_invoices"},
            all_invoices=above,
        ))

    # 8. Số hóa đơn theo trạng thái duyệt
    by_status = group(invoices, lambda i: i.status)
    cases.append(Case(
        "status_counts",
        "How many invoices are there in each review status?",
        {"invoice_stats"},
        numbers=[count for count, _ in by_status.values()],
    ))

    # 9-12. Tìm theo nghĩa: câu hỏi cố ý không dùng đúng chữ trong dữ liệu
    semantic_questions = [
        ("semantic_hosting", "Which invoices are about server hosting fees?", "hosting"),
        ("semantic_advertising", "Which invoices relate to advertising?", "marketing"),
        ("semantic_website", "Show me invoices for website work", "web design"),
        ("semantic_equipment_vi", "Hóa đơn nào liên quan đến thuê thiết bị?", "equipment rental"),
    ]
    for name, question, keyword in semantic_questions:
        matching = [
            i.invoice_number
            for i in invoices
            if any(keyword in item.description.lower() for item in i.line_items)
        ]
        if matching:
            cases.append(Case(name, question, {"semantic_search_invoices"}, any_invoices=matching))

    # 13. Khoảng ngày tuyệt đối
    dates = sorted(i.invoice_date for i in invoices)
    date_from, date_to = dates[0], dates[len(dates) // 2]
    in_range = sum(1 for d in dates if date_from <= d <= date_to)
    cases.append(Case(
        "date_range",
        f"How many invoices are dated between {date_from} and {date_to}, inclusive?",
        stats_or_search,
        numbers=[in_range],
    ))

    # 14. Ngày tương đối (agent phải tự đổi "30 ngày gần đây" thành ngày cụ thể)
    today = date.today()
    recent = sum(1 for i in invoices if today - timedelta(days=30) <= i.invoice_date <= today)
    if recent > 0:
        cases.append(Case(
            "relative_date_vi",
            "Có bao nhiêu hóa đơn được lập trong 30 ngày gần đây?",
            stats_or_search,
            numbers=[recent],
        ))

    # 15. Câu hỏi ngoài phạm vi: agent không được gọi công cụ nào
    cases.append(Case("out_of_scope", "What is the capital of France?", None))

    return cases


def judge(case: Case, answer: str, tools_used: list[str]) -> tuple[bool, bool, list[str]]:
    """Trả về (chọn đúng công cụ, trả lời đúng, danh sách vấn đề)."""
    problems = []

    if case.expected_tools is None:
        tool_ok = not tools_used
        if not tool_ok:
            problems.append(f"gọi công cụ dù không cần: {tools_used}")
    else:
        tool_ok = any(tool in case.expected_tools for tool in tools_used)
        if not tool_ok:
            problems.append(f"dùng {tools_used or 'không công cụ nào'}, kỳ vọng một trong {sorted(case.expected_tools)}")

    missing_numbers = [n for n in case.numbers if not contains_number(answer, n)]
    if missing_numbers:
        problems.append(f"thiếu số: {missing_numbers}")
    missing_invoices = [n for n in case.all_invoices if n not in answer]
    if missing_invoices:
        problems.append(f"thiếu hóa đơn: {missing_invoices}")
    if case.any_invoices and not any(n in answer for n in case.any_invoices):
        problems.append("không nhắc tới hóa đơn đúng nào")

    return tool_ok, not (missing_numbers or missing_invoices) and not (
        case.any_invoices and not any(n in answer for n in case.any_invoices)
    ), problems


def main() -> None:
    model = settings.agent_model or settings.llm_model
    results = []

    with SessionLocal() as session:
        cases = build_cases(session)
        print(f"Chạy {len(cases)} câu hỏi với model {model}\n")

        for case in cases:
            started = time.perf_counter()
            try:
                result = ask_agent(session, case.question)
                answer, tools_used = result.answer, [call["name"] for call in result.tool_calls]
                error = None
            except AgentError as agent_error:
                answer, tools_used, error = "", [], str(agent_error)
            seconds = time.perf_counter() - started

            if error:
                tool_ok, answer_ok, problems = False, False, [f"lỗi agent: {error}"]
            else:
                tool_ok, answer_ok, problems = judge(case, answer, tools_used)

            passed = tool_ok and answer_ok
            print(f"[{'PASS' if passed else 'FAIL'}] {case.name:<24} công cụ={tools_used} ({seconds:.1f}s)")
            for problem in problems:
                print(f"         - {problem}")

            results.append({
                "name": case.name,
                "question": case.question,
                "tools_used": tools_used,
                "tool_ok": tool_ok,
                "answer_ok": answer_ok,
                "problems": problems,
                "seconds": round(seconds, 2),
                "answer": answer,
            })
            time.sleep(PAUSE_SECONDS)

    total = len(results)
    tool_correct = sum(r["tool_ok"] for r in results)
    answer_correct = sum(r["answer_ok"] for r in results)
    both = sum(r["tool_ok"] and r["answer_ok"] for r in results)
    average_seconds = sum(r["seconds"] for r in results) / total
    average_calls = sum(len(r["tools_used"]) for r in results) / total

    print(f"\n=== Kết quả agent ({model}) ===")
    print(f"Chọn đúng công cụ: {tool_correct}/{total}")
    print(f"Trả lời đúng:      {answer_correct}/{total}")
    print(f"Đúng cả hai:       {both}/{total}")
    print(f"Thời gian trung bình: {average_seconds:.1f}s mỗi câu, {average_calls:.1f} lần gọi công cụ mỗi câu")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"agent_{model}.json"
    report = {
        "model": model,
        "questions": total,
        "tool_correct": tool_correct,
        "answer_correct": answer_correct,
        "both_correct": both,
        "avg_seconds": round(average_seconds, 2),
        "cases": results,
    }
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nĐã lưu báo cáo: {output_path}")


if __name__ == "__main__":
    main()