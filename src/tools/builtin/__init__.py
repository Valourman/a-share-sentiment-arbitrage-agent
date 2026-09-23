from src.tools.builtin.calculator import CalculatorTool
from src.tools.builtin.search import SearchTool
from src.tools.registry import global_tool_registry

# 自动注册内置标准工具
calculator_tool = CalculatorTool()
search_tool = SearchTool()

global_tool_registry.register(calculator_tool)
global_tool_registry.register(search_tool)

__all__ = [
    "CalculatorTool",
    "SearchTool",
    "calculator_tool",
    "search_tool",
]
