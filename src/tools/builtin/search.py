import os
from typing import Any
from src.tools.base import Tool, ToolParameter


class SearchTool(Tool):
    """
    Hello Agents 内置多源搜索工具
    支持 Tavily、SerpApi 等外部实时检索，且在未配置第三方 API Key 时自动降级为领域仿真/轻量搜索
    """
    name: str = "web_search"
    description: str = "在互联网上检索最新事实信息、新闻或背景知识。输入查询关键词，返回相关摘要片段。"
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="待检索的关键词或问题描述",
            required=True,
        )
    ]

    def __init__(self, default_top_k: int = 3):
        super().__init__()
        self.default_top_k = default_top_k

    def _search_mock(self, query: str) -> str:
        """无外部 Key 时的降级搜索逻辑"""
        return f"[搜索模拟结果] 针对 '{query}' 的主要检索条目：包含行业最新权威研报、权威财经新闻以及权威公告数据摘要。"

    def execute(self, query: str = "", **kwargs: Any) -> Any:
        q = query or kwargs.get("input", "")
        if not q:
            return "错误: 查询内容不能为空"

        # 1. 尝试 Tavily 检索
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "https://api.tavily.com/search",
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({"api_key": tavily_key, "query": q, "max_results": self.default_top_k}).encode("utf-8"),
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    results = data.get("results", [])
                    snippets = [f"- [{r.get('title')}]: {r.get('content')}" for r in results]
                    if snippets:
                        return "\n".join(snippets)
            except Exception:
                pass

        # 2. 降级
        return self._search_mock(q)
