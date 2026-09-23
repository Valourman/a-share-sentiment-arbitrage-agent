"""
Hello Agents - 开源通用大语言模型智能体轻量级框架
遵循分层解耦、职责单一、除了核心 Agent 类一切皆为 Tools 的设计理念
"""

# 核心底座层
from src.core.agent import Agent, BaseAgent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message, RoleType
from src.core.config import AgentConfig, global_config
from src.core.exceptions import (
    HelloAgentsException,
    AgentException,
    LLMException,
    ToolException,
    ToolNotFoundException,
    ConfigurationException,
    ProtocolException,
)

# 经典范式层
from src.agents.simple_agent import SimpleAgent
from src.agents.react_agent import ReActAgent
from src.agents.reflection_agent import ReflectionAgent
from src.agents.plan_solve_agent import PlanAndSolveAgent
from src.agents.function_call_agent import FunctionCallAgent

# 工具调度层
from src.tools.base import Tool, ToolParameter
from src.tools.registry import ToolRegistry, global_tool_registry
from src.tools.chain import ToolChain, ToolStep
from src.tools.async_executor import AsyncToolExecutor

# 记忆与检索增强层
from src.memory.manager import MemoryManager, WorkingMemory, MemoryEntry
from src.memory.buffer import ConversationBufferMemory
from src.memory.tools import MemoryTool, RAGTool

# 通信协议层
from src.protocols.mcp.client import MCPClient, MCPServer
from src.protocols.mcp.tool import MCPTool
from src.protocols.a2a.implementation import A2AServer, A2AClient, A2ATool

__all__ = [
    # Core
    "Agent",
    "BaseAgent",
    "HelloAgentsLLM",
    "Message",
    "RoleType",
    "AgentConfig",
    "global_config",
    "HelloAgentsException",
    "AgentException",
    "LLMException",
    "ToolException",
    "ToolNotFoundException",
    "ConfigurationException",
    "ProtocolException",
    # Agents
    "SimpleAgent",
    "ReActAgent",
    "ReflectionAgent",
    "PlanAndSolveAgent",
    "FunctionCallAgent",
    # Tools
    "Tool",
    "ToolParameter",
    "ToolRegistry",
    "global_tool_registry",
    "ToolChain",
    "ToolStep",
    "AsyncToolExecutor",
    # Memory
    "MemoryManager",
    "WorkingMemory",
    "MemoryEntry",
    "ConversationBufferMemory",
    "MemoryTool",
    "RAGTool",
    # Protocols
    "MCPClient",
    "MCPServer",
    "MCPTool",
    "A2AServer",
    "A2AClient",
    "A2ATool",
]
