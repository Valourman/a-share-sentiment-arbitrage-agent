from typing import Any, Generator, Optional
from src.core.agent import Agent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message


class SimpleAgent(Agent):
    """
    Hello Agents 基础智能体 (SimpleAgent)
    支持系统提示词注入、多轮会话状态维护与流式生成
    """
    def __init__(
        self,
        name: str = "SimpleAgent",
        system_prompt: Optional[str] = None,
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[Any] = None,
    ):
        super().__init__(name=name, llm=llm, tools=tools)
        self.system_prompt = system_prompt or "你是一个乐于助人且专业的 AI 智能体助手。"
        if self.system_prompt:
            self.add_message(Message.system(self.system_prompt))

    def run(self, input_text: str, **kwargs: Any) -> str:
        """执行单轮或多轮标准问答交互"""
        user_msg = Message.user(input_text)
        self.add_message(user_msg)

        reply_content = self.llm.chat(messages=self.get_history(), **kwargs)
        assistant_msg = Message.assistant(reply_content)
        self.add_message(assistant_msg)

        return reply_content

    def stream_run(self, input_text: str, **kwargs: Any) -> Generator[str, None, None]:
        """执行流式响应输出"""
        user_msg = Message.user(input_text)
        self.add_message(user_msg)

        full_reply = []
        for chunk in self.llm.stream_chat(messages=self.get_history(), **kwargs):
            full_reply.append(chunk)
            yield chunk

        self.add_message(Message.assistant("".join(full_reply)))
