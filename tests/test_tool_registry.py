from src.tools.base import Tool, ToolParameter
from src.tools.registry import ToolRegistry, global_tool_registry
from src.tools.scraper import StockForumScraper
from src.tools.market import MarketDataTool


class MockEchoTool(Tool):
    name = "mock_echo"
    description = "回显工具"
    parameters = [
        ToolParameter(name="text", type="string", description="待回显内容", required=True)
    ]

    def execute(self, **kwargs):
        return kwargs.get("text", "")


def test_tool_schema_generation():
    tool = MockEchoTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "mock_echo"
    assert "text" in schema["function"]["parameters"]["properties"]
    assert "text" in schema["function"]["parameters"]["required"]


def test_tool_registry_registration_and_execution():
    registry = ToolRegistry()
    registry.register(MockEchoTool())

    tool = registry.get("mock_echo")
    assert tool is not None
    assert tool.name == "mock_echo"

    res = registry.execute("mock_echo", text="test_value")
    assert res == "test_value"

    schemas = registry.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "mock_echo"


def test_global_builtin_tools_present():
    scraper = global_tool_registry.get("stock_scraper")
    market = global_tool_registry.get("market_data")
    analyzer = global_tool_registry.get("sentiment_analyzer")

    assert isinstance(scraper, StockForumScraper)
    assert isinstance(market, MarketDataTool)
    assert analyzer is not None


def test_tool_registry_decorator_and_missing_tool_error():
    registry = ToolRegistry()

    @registry.register_func(name="add_numbers", description="两数相加")
    def add(a: int, b: int) -> int:
        return a + b

    assert registry.get("add_numbers") is not None
    assert registry.execute("add_numbers", a=3, b=5) == 8

    # 测试未注册工具
    import pytest
    with pytest.raises(KeyError) as exc_info:
        registry.execute("non_existent_tool")
    assert "未找到名称为" in str(exc_info.value)

