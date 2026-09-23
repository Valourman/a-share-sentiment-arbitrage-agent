"""金融垂直知识检索智能体工具 (FinancialKnowledgeTool)

为各类金融智能体提供查询 A 股垂直黑话、心理动机、量化背离及公告规则的统一外部感知工具。
遵从 Hello-Agents '除 Agent 类外一切皆为 Tool' 的架构规范。
"""

from typing import Any, Dict, Optional
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.memory.knowledge import FinancialKnowledgeRetriever
from src.tools.base import BaseTool, ToolResult


class FinancialKnowledgeTool(BaseTool):
    """
    Hello-Agents 规范金融知识库检索工具
    供各类智能体在推理分析时自主调用，获取深层黑话解读、反讽动机与规则依据
    """
    name: str = "search_financial_knowledge"
    description: str = "查询A股垂直金融知识库，获取散户黑话定义、反讽心理动机解读、量化背离特征或重大规则。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "需要查询的关键词、术语或散户发帖原文",
            },
            "stock_code": {
                "type": "string",
                "description": "可选的标的股票代码 (例如 600667)",
            },
            "top_k": {
                "type": "integer",
                "description": "期望召回的最佳匹配条目数",
                "default": 3,
            },
        },
        "required": ["query"],
    }

    def __init__(self, kb: Optional[FinancialRAGKnowledgeBase] = None):
        """初始化金融知识检索工具

        参数:
            kb: 自定义金融 RAG 知识库，未提供时默认加载 FinancialKnowledgeRetriever.DEFAULT_KNOWLEDGE_BASE
        """
        super().__init__()
        self._kb = kb or self._build_default_kb()

    @staticmethod
    def _build_default_kb() -> FinancialRAGKnowledgeBase:
        """构建并填充默认金融领域黑话与反讽知识底座"""
        kb = FinancialRAGKnowledgeBase()
        for item in FinancialKnowledgeRetriever.DEFAULT_KNOWLEDGE_BASE:
            kb.add_knowledge_item(
                term=item.term,
                category=item.category,
                definition=item.definition,
                sentiment_bias=item.sentiment_bias,
            )
        return kb

    def execute(
        self,
        query: str = "",
        stock_code: Optional[str] = None,
        top_k: int = 3,
        **kwargs: Any,
    ) -> ToolResult:
        """执行垂直金融知识检索

        参数:
            query: 待检索的关键词或帖子原文
            stock_code: 可选的股票代码过滤
            top_k: 期望返回的结果上限

        返回:
            ToolResult 封装的标准工具响应对象
        """
        q = (query or kwargs.get("input", "")).strip()
        code = stock_code or kwargs.get("code")
        limit = int(kwargs.get("top_k", top_k))

        try:
            if not q:
                return ToolResult(success=True, output="未检索到高度相关的垂直金融知识条目。")
            results = self._kb.retrieve(query=q, top_k=limit, stock_code=code)
            if not results:
                return ToolResult(success=True, output="未检索到高度相关的垂直金融知识条目。")
            formatted = self._kb.format_context(results)
            return ToolResult(success=True, output=formatted)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"知识库检索异常: {str(e)}")
