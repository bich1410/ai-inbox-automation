from app.agent import TOOL_DECLARATIONS
from app.queries import TOOLS, run_tool


def test_tool_declarations_match_argument_models():
    declared = {tool["name"]: set(tool["parameters"]["properties"]) for tool in TOOL_DECLARATIONS}
    assert set(declared) == set(TOOLS)
    for name, (args_model, _) in TOOLS.items():
        assert declared[name] == set(args_model.model_fields)


def test_invalid_arguments_return_error_without_touching_database():
    # status không hợp lệ bị chặn ngay ở bước kiểm tra tham số, session=None chứng minh không đụng tới database
    result = run_tool(None, "search_invoices", {"status": "banana"})
    assert "error" in result


def test_unknown_tool_returns_error():
    assert "error" in run_tool(None, "drop_all_tables", {})