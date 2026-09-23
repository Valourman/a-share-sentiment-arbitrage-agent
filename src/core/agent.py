from abc import ABC, abstractmethod
from typing import Any, List, Optional
from src.core.llm import HelloAgentsLLM
from src.core.message import Message


class BaseAgent(ABC):
    """
    Hello Agents 顶层抽象基类
    统一规范智能体的生命周期、状态存储、大模型中枢绑定与工具调度机制
    """
    def __init__(
        self,
        name: str = "BaseAgent",
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[Any] = None,
    ):
        self.name = name
        self.llm = llm or HelloAgentsLLM()
        self.tools = tools
        self.history: List[Message] = []

    def add_message(self, message: Message) -> None:
        """记录一条会话到内部历史"""
        self.history.append(message)

    def get_history(self) -> List[Message]:
        """获取所有历史会话"""
        return self.history

    def reset(self) -> None:
        """重置上下文与历史记忆"""
        self.history.clear()

    @abstractmethod
    def run(self, input_text: str, **kwargs: Any) -> Any:
        """
        核心任务执行入口
        子类必须实现具体的思考规划、工具调用或状态转移逻辑
        """
        pass
