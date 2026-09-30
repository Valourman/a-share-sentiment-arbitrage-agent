from typing import Any, List, Optional
from src.tools.base import Tool, ToolParameter
from src.protocols.mcp.client import MCPClient


class MCPTool(Tool):
    """
    Hello Agents MCP 协议适配工具
    将远程或进程间 MCP 服务端点包装为当前智能体可直接调用的标准 Tool
    """
    def __init__(
        self,
        client: MCPClient,
        tool_name: str,
        description: str = "",
        parameters: Optional[List[ToolParameter]] = None,
    ):
        self.client = client
        self.name = tool_name
        self.description = description
        self.parameters = parameters or []
        super().__init__()

    def execute(self, **kwargs: Any) -> Any:
        return self.client.call_tool(self.name, kwargs)
