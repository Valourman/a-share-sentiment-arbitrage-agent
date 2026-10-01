from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RoleType(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"  # OpenAI 已废弃的旧协议角色，仅为兼容保留


class Message(BaseModel):
    """
    Hello Agents 规范标准消息协议载体
    封装角色、内容文本、时间戳及上下文元数据，提供到 OpenAI API 字典的标准转换
    """
    role: RoleType = Field(description="消息发送者角色")
    content: str = Field(description="消息正文内容")
    name: Optional[str] = Field(default=None, description="发送者姓名或工具名称")
    timestamp: datetime = Field(default_factory=datetime.now, description="消息生成时间戳")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="assistant 消息携带的工具调用列表（OpenAI tool-calling 协议）"
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="tool 角色消息对应的工具调用 ID（OpenAI tool-calling 协议）"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="业务扩展元数据")

    def to_openai_dict(self) -> Dict[str, Any]:
        """转换为 OpenAI API 兼容的消息字典格式"""
        payload: Dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            payload["name"] = self.name
        # OpenAI tool-calling 协议要求：assistant 消息携带 tool_calls 数组、
        # tool 消息携带 tool_call_id，缺失将导致后续请求被 400 拒绝
        if self.tool_calls:
            payload["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        return payload

    @classmethod
    def system(cls, content: str, **kwargs) -> "Message":
        return cls(role=RoleType.SYSTEM, content=content, **kwargs)

    @classmethod
    def user(cls, content: str, **kwargs) -> "Message":
        return cls(role=RoleType.USER, content=content, **kwargs)

    @classmethod
    def assistant(cls, content: str, **kwargs) -> "Message":
        return cls(role=RoleType.ASSISTANT, content=content, **kwargs)

    @classmethod
    def tool(cls, content: str, name: str, **kwargs) -> "Message":
        return cls(role=RoleType.TOOL, content=content, name=name, **kwargs)
