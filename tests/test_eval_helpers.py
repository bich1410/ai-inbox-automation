from scripts.evaluate_agent import contains_number


def test_contains_number_handles_both_number_formats():
    assert contains_number("The total is 1,234.50 GBP", 1234.50)  # kiểu Anh
    assert contains_number("Tổng cộng là 1.234,50 GBP", 1234.50)  # kiểu Việt
    assert contains_number("Total: 722.14.", 722.14)  # dấu chấm câu ở cuối


def test_contains_number_rejects_wrong_values():
    assert not contains_number("The total is 722.14 GBP", 722.41)
    assert not contains_number("No numbers here", 5)