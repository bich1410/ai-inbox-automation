"""Giao diện Streamlit cho AI Inbox.

Giao diện chỉ nói chuyện với server qua HTTP (không import code trong app/), nên sau này có thể
thay bằng giao diện khác mà không phải sửa server.
"""

import os

import httpx
import pandas as pd
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("API_KEY")  # dùng ở tuần 4, khi server có xác thực

st.set_page_config(page_title="AI Inbox", layout="wide")


def call_api(method: str, path: str, timeout: float = 30, show_error: bool = True, **kwargs):
    """Gọi server. Trả về httpx.Response, hoặc None nếu không kết nối được."""
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    try:
        return httpx.request(method, f"{API_BASE_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    except httpx.HTTPError as error:
        if show_error:
            st.error(f"Cannot reach the API at {API_BASE_URL}. Is uvicorn running? ({type(error).__name__})")
        return None


def error_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except (ValueError, AttributeError):
        detail = response.text
    return f"{response.status_code}: {detail}"


def render_text(text: str) -> None:
    """Hiển thị văn bản. Dấu $ bị Streamlit hiểu là công thức toán nên phải thoát ký tự."""
    st.markdown(text.replace("$", r"\$"))


# ---------------------------------------------------------------- Trang 1: danh sách hóa đơn
def show_invoices() -> None:
    st.subheader("Saved invoices")
    status = st.selectbox("Status", ["all", "auto_approved", "approved", "rejected"])

    params = {"limit": 100}
    if status != "all":
        params["status"] = status

    response = call_api("GET", "/invoices", params=params)
    if response is None:
        return
    if response.status_code != 200:
        st.error(error_detail(response))
        return

    rows = response.json()
    if not rows:
        st.info("No invoices yet.")
        return

    frame = pd.DataFrame(rows)
    frame["issues"] = frame["issues"].apply(lambda issues: "; ".join(issues))
    st.caption(f"{len(frame)} invoices (newest first)")
    st.dataframe(
        frame[["invoice_number", "vendor_name", "invoice_date", "currency", "total", "status", "issues", "source"]],
        hide_index=True,
    )


# ---------------------------------------------------------------- Trang 2: hỏi đáp
def show_chat() -> None:
    st.subheader("Ask about your invoices")
    st.caption("Each question is answered on its own. The agent does not remember earlier questions.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_text(message["content"])
            if message.get("tool_calls"):
                with st.expander("Tools used"):
                    st.json(message["tool_calls"])

    question = st.chat_input("Ask a question, for example: total amount per currency?")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        render_text(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = call_api("POST", "/ask", timeout=120, json={"question": question})
        if response is None:
            return
        if response.status_code != 200:
            st.error(error_detail(response))
            return

        data = response.json()
        render_text(data["answer"])
        with st.expander("Tools used"):
            st.json(data["tool_calls"])

    st.session_state.messages.append(
        {"role": "assistant", "content": data["answer"], "tool_calls": data["tool_calls"]}
    )


# ---------------------------------------------------------------- Trang 3: tải lên, trích xuất, duyệt
def save_invoice(status: str) -> None:
    payload = {"invoice": st.session_state.extraction["invoice"], "status": status, "source": "ui"}
    response = call_api("POST", "/invoices", timeout=90, json=payload)
    if response is None:
        return
    if response.status_code == 201:
        st.success(f"Saved with status: {status}.")
    elif response.status_code == 200:
        st.info("This invoice was already saved earlier. Nothing changed.")
    else:
        st.error(error_detail(response))


def show_upload() -> None:
    st.subheader("Extract data from an invoice PDF")
    uploaded = st.file_uploader("Invoice PDF", type="pdf")

    if uploaded is not None and st.button("Extract"):
        with st.spinner("Reading the invoice..."):
            response = call_api(
                "POST",
                "/extract",
                timeout=90,
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
            )
        if response is None:
            return
        if response.status_code == 200:
            st.session_state.extraction = response.json()
            st.session_state.extraction_file = uploaded.name
        else:
            st.session_state.pop("extraction", None)
            st.error(error_detail(response))

    result = st.session_state.get("extraction")
    if not result:
        return

    invoice = result["invoice"]
    st.caption(f"Result for: {st.session_state.get('extraction_file', '')}")

    columns = st.columns(4)
    columns[0].metric("Invoice", invoice["invoice_number"])
    columns[1].metric("Vendor", invoice["vendor_name"])
    columns[2].metric("Date", invoice["invoice_date"])
    columns[3].metric("Total", f"{invoice['total']:,.2f} {invoice['currency']}")
    st.dataframe(pd.DataFrame(invoice["line_items"]), hide_index=True)

    if result["needs_review"]:
        st.warning("This invoice needs human review:")
        for issue in result["issues"]:
            st.write(f"- {issue}")
        approve_column, reject_column = st.columns(2)
        if approve_column.button("Approve and save"):
            save_invoice("approved")
        if reject_column.button("Reject and save"):
            save_invoice("rejected")
    else:
        st.success("No problems found.")
        if st.button("Save to database"):
            save_invoice("auto_approved")


# ---------------------------------------------------------------- Khung chính
st.title("AI Inbox")

health = call_api("GET", "/health", timeout=5, show_error=False)
if health is not None and health.status_code == 200:
    st.sidebar.success("API online")
else:
    st.sidebar.error("API offline")

page = st.sidebar.radio("Page", ["Invoices", "Ask", "Upload"])
PAGES = {"Invoices": show_invoices, "Ask": show_chat, "Upload": show_upload}
PAGES[page]()