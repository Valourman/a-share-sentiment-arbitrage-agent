from typing import List, Optional
from src.core.message import Message, RoleType


class ConversationBufferMemory:
    """
    Hello Agents 规范短期会话记忆管理
    维护多轮交互历史，支持滑动窗口截断、格式化上下文拼接与消息状态维护
    """
    def __init__(self, max_messages: Optional[int] = 20):
        self.max_messages = max_messages
        self._messages: List[Message] = []

    def add_message(self, message: Message) -> None:
        """追加一条消息"""
        self._messages.append(message)
        if self.max_messages and len(self._messages) > self.max_messages:
            # 保留系统提示词(若有首条为system)，再滑动窗口截断
            if self._messages[0].role == RoleType.SYSTEM:
                if self.max_messages == 1:
                    # 边界防护：max_messages=1 时只保留 system 提示词
                    # ([-0:] 在 Python 中等价于全量切片，会导致窗口永不截断)
                    self._messages = [self._messages[0]]
                else:
                    self._messages = [self._messages[0]] + self._messages[-(self.max_messages - 1):]
            else:
                self._messages = self._messages[-self.max_messages:]

    def add_user_message(self, content: str) -> None:
        self.add_message(Message.user(content))

    def add_assistant_message(self, content: str) -> None:
        self.add_message(Message.assistant(content))

    def get_messages(self) -> List[Message]:
        return list(self._messages)

    def get_context_string(self) -> str:
        """拼接为适合注入 Prompt 的历史对白上下文字符串"""
        lines = []
        for msg in self._messages:
            lines.append(f"{msg.role.value.upper()}: {msg.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        """清空历史记忆"""
        self._messages.clear()
