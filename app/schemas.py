"""Schema (khuôn dữ liệu) cho hóa đơn: dùng cho LLM, kiểm tra và đánh giá."""

from datetime import date

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """Một dòng hàng trong hóa đơn."""

    description: str = Field(description="Name or description of the product or service")
    quantity: float = Field(ge=0, description="Number of units")
    unit_price: float = Field(ge=0, description="Price of one unit, before tax")
    line_total: float = Field(ge=0, description="quantity multiplied by unit_price")

    def is_consistent(self, tolerance: float = 0.01) -> bool:
        """quantity x unit_price có khớp line_total không (cho phép lệch do làm tròn)."""
        return abs(self.quantity * self.unit_price - self.line_total) <= tolerance


class Invoice(BaseModel):
    """Thông tin cần trích xuất từ một hóa đơn."""

    # Trường bắt buộc: hóa đơn nào cũng phải có
    invoice_number: str = Field(description="Invoice number or ID as printed on the document")
    vendor_name: str = Field(description="Name of the company issuing the invoice")
    invoice_date: date = Field(description="Invoice issue date, format YYYY-MM-DD")
    currency: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="3-letter ISO currency code, e.g. USD, EUR, GBP",
    )
    line_items: list[LineItem] = Field(min_length=1, description="All line items on the invoice")
    subtotal: float = Field(ge=0, description="Sum of all line totals, before tax")
    total: float = Field(ge=0, description="Final amount due, including tax")

    # Trường tùy chọn: hóa đơn ngoài đời có thể không ghi
    vendor_address: str | None = Field(default=None, description="Address of the vendor")
    customer_name: str | None = Field(default=None, description="Name of the customer being billed")
    due_date: date | None = Field(default=None, description="Payment due date, format YYYY-MM-DD")
    tax_rate: float | None = Field(default=None, ge=0, le=100, description="Tax rate in percent")
    tax_amount: float = Field(default=0, ge=0, description="Tax amount; 0 if the invoice has no tax")

    def totals_issues(self, tolerance: float = 0.01) -> list[str]:
        """Kiểm tra logic số liệu. Trả về danh sách vấn đề, rỗng nghĩa là ổn."""
        issues = []

        for position, item in enumerate(self.line_items, start=1):
            if not item.is_consistent(tolerance):
                issues.append(f"Line {position}: quantity x unit_price does not match line_total")

        items_sum = sum(item.line_total for item in self.line_items)
        if abs(items_sum - self.subtotal) > tolerance:
            issues.append(f"Sum of line totals ({items_sum:.2f}) does not match subtotal ({self.subtotal:.2f})")

        if abs(self.subtotal + self.tax_amount - self.total) > tolerance:
            issues.append("subtotal + tax_amount does not match total")

        if self.due_date and self.due_date < self.invoice_date:
            issues.append("due_date is earlier than invoice_date")

        return issues