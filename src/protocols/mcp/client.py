from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """MCP 工具能力定义"""
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class MCPServer:
    """
    Hello Agents MCP 服务提供端 (Server)
    负责向 Host/Client 暴露标准化的 Tools、Resources 与 Prompts
    """
    def __init__(self, name: str = "HelloAgentsMCPServer"):
        self.name = name
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        input_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发布一个 MCP 工具能力"""
        self._tools[name] = MCPToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object", "properties": {}},
        )
        self._handlers[name] = handler

    def list_tools(self) -> List[MCPToolDefinition]:
        """返回已注册的全部工具契约"""
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """执行特定工具调用"""
        if name not in self._handlers:
            raise KeyError(f"MCP Server 未找到工具: {name}")
        return self._handlers[name](**arguments)


class MCPClient:
    """
    Hello Agents MCP 客户端 (Client)
    与本地内存、Stdio 或远端 HTTP/SSE MCP Server 建立通信
    """
    def __init__(self, server: Optional[MCPServer] = None):
        self.server = server

    def list_tools(self) -> List[MCPToolDefinition]:
        if not self.server:
            return []
        return self.server.list_tools()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self.server:
            raise RuntimeError("MCPClient 未绑定有效 MCPServer 连接")
        return self.server.call_tool(name, arguments)
