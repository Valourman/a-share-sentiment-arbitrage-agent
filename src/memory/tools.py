from typing import Any, Optional
from src.tools.base import Tool, ToolParameter
from src.tools.registry import global_tool_registry
from src.memory.manager import MemoryManager
from src.memory.knowledge import FinancialKnowledgeRetriever


class MemoryTool(Tool):
    """
    Hello Agents 统一记忆交互工具 (MemoryTool)
    将智能体的记忆检索、固化、存储暴露为标准的外部工具接口，遵循'除了Agent类，一切皆为Tools'的设计准则
    """
    name: str = "memory_manager"
    description: str = "用于查询、写入或固化智能体上下文记忆的工具。操作模式包括：add (写入记忆), search (检索记忆), consolidate (记忆固化)。"
    parameters = [
        ToolParameter(
            name="action",
            type="string",
            description="操作类型: 'add' (写入), 'search' (检索), 'consolidate' (固化)",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="记忆正文或查询关键词",
            required=True,
        ),
        ToolParameter(
            name="importance",
            type="number",
            description="记忆重要性 (0.0 ~ 1.0)",
            required=False,
            default=0.5,
        ),
        ToolParameter(
            name="user_id",
            type="string",
            description="用户标识 (用于多租户与记忆隔离)",
            required=False,
            default="default_user",
        ),
    ]

    def __init__(self, manager: Optional[MemoryManager] = None):
        super().__init__()
        self.manager = manager or MemoryManager()

    def execute(
        self,
        action: str = "search",
        content: str = "",
        importance: float = 0.5,
        user_id: str = "default_user",
        **kwargs: Any,
    ) -> Any:
        act = (action or kwargs.get("operation", "search")).lower().strip()
        text = content or kwargs.get("query", "")

        if act == "add":
            entry = self.manager.add(content=text, importance=importance, user_id=user_id)
            return f"成功记录记忆条目: '{entry.content[:40]}...' (重要度: {entry.importance})"

        elif act == "search":
            results = self.manager.search(query=text, user_id=user_id)
            if not results:
                return f"未检索到与 '{text}' 相关的记忆记录。"
            lines = [f"- [{r.role}]: {r.content} (重要度: {r.importance})" for r in results]
            return "\n".join(lines)

        elif act == "consolidate":
            count = self.manager.consolidate(importance_threshold=importance, user_id=user_id)
            return f"成功固化 {count} 条短期工作记忆至长期记忆库。"

        return f"不支持的记忆操作: {act}"


class RAGTool(Tool):
    """
    Hello Agents 知识检索增强工具 (RAGTool)
    将领域专属知识检索、术语消歧与外部文档检索暴露给智能体
    """
    name: str = "rag_search"
    description: str = "检索内部专业知识库、行业术语词典及黑话定义，返回权威解读与参考上下文。"
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="待查询的专业概念、行业黑话或知识关键词",
            required=True,
        ),
        ToolParameter(
            name="top_k",
            type="integer",
            description="返回的最相关条目数",
            required=False,
            default=3,
        ),
    ]

    def __init__(self, retriever: Optional[FinancialKnowledgeRetriever] = None):
        super().__init__()
        self.retriever = retriever or FinancialKnowledgeRetriever()

    def execute(self, query: str = "", top_k: int = 3, **kwargs: Any) -> Any:
        q = query or kwargs.get("input", "")
        if not q:
            return "错误: 查询关键词为空"

        items = self.retriever.search(q, top_k=top_k)
        if not items:
            return f"知识库中未找到与 '{q}' 相关的专业条目。"

        return self.retriever.format_as_context(items)


# 注册实例至全局工具库
global_memory_tool = MemoryTool()
global_rag_tool = RAGTool()

global_tool_registry.register(global_memory_tool)
global_tool_registry.register(global_rag_tool)
