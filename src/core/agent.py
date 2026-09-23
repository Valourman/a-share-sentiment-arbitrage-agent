from abc import ABC, abstractmethod
from typing import Any, Generator, List, Optional
from src.core.llm import HelloAgentsLLM
from src.core.message import Message


class Agent(ABC):
    """
    Hello Agents 顶层抽象智能体基类
    统一规范智能体的生命周期、状态存储、大模型中枢绑定与工具调度机制
    """
    def __init__(
        self,
        name: str = "Agent",
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[Any] = None,
    ):
        self.name = name
        self.llm = llm or HelloAgentsLLM()
        self.tools = tools
        self._history: List[Message] = []

    @property
    def history(self) -> List[Message]:
        """获取内部历史会话消息引用"""
        return self._history

    def add_message(self, message: Message) -> None:
        """记录一条会话到内部历史"""
        self._history.append(message)

    def get_history(self) -> List[Message]:
        """获取所有历史会话只读副本"""
        return list(self._history)

    def clear_history(self) -> None:
        """清空会话历史"""
        self._history.clear()

    def reset(self) -> None:
        """重置上下文与历史记忆"""
        self.clear_history()

    @abstractmethod
    def run(self, input_text: str, **kwargs: Any) -> Any:
        """
        核心任务执行入口
        子类必须实现具体的思考规划、工具调用或状态转移逻辑
        """
        pass

    def stream_run(self, input_text: str, **kwargs: Any) -> Generator[str, None, None]:
        """
        流式生成执行入口 (可选重写)
        默认退化为一次性生成并迭代产生
        """
        result = self.run(input_text, **kwargs)
        yield str(result)


# 向后兼容别名
BaseAgent = Agent
