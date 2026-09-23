from src.tools.base import Tool, ToolParameter
from src.tools.registry import ToolRegistry, FunctionTool, global_tool_registry
from src.tools.scraper import StockForumScraper
from src.tools.market import MarketDataTool
from src.tools.analyzer import FinancialSentimentAnalyzer

# 将默认内置工具注册到全局注册中心
global_tool_registry.register(StockForumScraper())
global_tool_registry.register(MarketDataTool())
global_tool_registry.register(FinancialSentimentAnalyzer())

__all__ = [
    "Tool",
    "ToolParameter",
    "ToolRegistry",
    "FunctionTool",
    "global_tool_registry",
    "StockForumScraper",
    "MarketDataTool",
    "FinancialSentimentAnalyzer",
]
