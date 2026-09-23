import inspect
from typing import Any, Callable, Dict, List, Optional
from src.tools.base import Tool, ToolParameter


class FunctionTool(Tool):
    """用于快速将普通函数封装为标准 Tool 的适配器"""
    def __init__(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[List[ToolParameter]] = None,
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = description or (inspect.getdoc(func) or f"执行函数 {self.name}")
        self.parameters = parameters or []
        super().__init__()

    def execute(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)


class ToolRegistry:
    """
    Hello Agents 标准工具注册与调度中心
    支持实例注册、装饰器注册、元数据自省导出与集中式执行
    """
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        """注册一个 Tool 实例"""
        self._tools[tool.name] = tool
        return tool

    def register_func(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[List[ToolParameter]] = None,
    ) -> Callable[[Callable[..., Any]], Tool]:
        """装饰器：将任意 Python 函数注册为标准 Tool"""
        def decorator(func: Callable[..., Any]) -> Tool:
            tool_instance = FunctionTool(
                func=func,
                name=name,
                description=description,
                parameters=parameters,
            )
            self.register(tool_instance)
            return tool_instance
        return decorator

    def get(self, name: str) -> Optional[Tool]:
        """按名称查找工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """列出所有已注册工具"""
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """批量获取所有工具的 OpenAI Function Calling Schemas 列表"""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> Any:
        """集中式路由执行工具"""
        tool = self.get(name)
        if not tool:
            raise KeyError(f"未找到名称为 '{name}' 的已注册工具。当前可用工具: {list(self._tools.keys())}")
        return tool.execute(**kwargs)

    def register_financial_knowledge(self, kb: Optional[Any] = None) -> Tool:
        """便捷注册金融领域垂直 RAG 检索工具 (FinancialKnowledgeTool)"""
        from src.knowledge.tools import FinancialKnowledgeTool
        tool = FinancialKnowledgeTool(kb=kb)
        return self.register(tool)


# 全局默认工具注册中心
global_tool_registry = ToolRegistry()
