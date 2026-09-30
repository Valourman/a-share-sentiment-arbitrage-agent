import json
from typing import Any, Dict, Optional
from src.core.agent import Agent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message, RoleType
from src.tools.registry import ToolRegistry, global_tool_registry


class FunctionCallAgent(Agent):
    """
    Hello Agents 原生函数调用智能体 (FunctionCallAgent)
    基于 OpenAI 标准 tool_calls 协议，实现自动参数装配、工具调用与结果回传闭环
    """
    def __init__(
        self,
        name: str = "FunctionCallAgent",
        system_prompt: Optional[str] = None,
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[ToolRegistry] = None,
        max_turns: int = 5,
    ):
        super().__init__(name=name, llm=llm, tools=tools or global_tool_registry)
        self.system_prompt = system_prompt or "你是一个具备调用外部工具能力的专业智能体助手。"
        self.max_turns = max_turns

    def run(self, input_text: str, **kwargs: Any) -> str:
        """执行原生工具调用循环"""
        self.clear_history()
        if self.system_prompt:
            self.add_message(Message.system(self.system_prompt))
        self.add_message(Message.user(input_text))

        tools_schemas = self.tools.get_schemas() if isinstance(self.tools, ToolRegistry) else None

        turn = 0
        while turn < self.max_turns:
            turn += 1

            if not self.llm.client:
                # 若未配置真实客户端，进行降级防护
                return "[FunctionCallAgent] LLM 客户端未就绪。"

            # 组装请求参数
            formatted_messages = [m.to_openai_dict() for m in self.get_history()]
            request_params: Dict[str, Any] = {
                "model": self.llm.config.default_model,
                "messages": formatted_messages,
                "temperature": self.llm.config.temperature,
            }
            if tools_schemas:
                request_params["tools"] = tools_schemas

            response = self.llm.client.chat.completions.create(**request_params)
            msg = response.choices[0].message

            # 如果模型给出了常规文本且没有发起 tool_calls
            if not msg.tool_calls:
                content = msg.content or ""
                self.add_message(Message.assistant(content))
                return content

            # 处理 tool_calls：必须作为一等字段写入消息，
            # 否则下一轮 to_openai_dict() 序列化时会丢失并被 API 拒绝
            assistant_msg = Message(
                role=RoleType.ASSISTANT,
                content=msg.content or "",
                tool_calls=[tc.model_dump() for tc in msg.tool_calls],
            )
            self.add_message(assistant_msg)

            for tool_call in msg.tool_calls:
                function_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception as e:
                    # 参数解析失败时把错误作为 tool 结果回传，让 LLM 自我修正
                    args = None
                    self.add_message(Message(
                        role=RoleType.TOOL,
                        name=function_name,
                        content=f"错误: 工具参数 JSON 解析失败: {e}",
                        tool_call_id=tool_call.id,
                    ))
                    continue

                # 执行工具
                try:
                    if isinstance(self.tools, ToolRegistry):
                        result = self.tools.execute(function_name, **args)
                    else:
                        result = "错误: 未配置工具注册中心"
                except Exception as e:
                    result = f"工具 {function_name} 执行异常: {str(e)}"

                # 回传 tool 角色消息（携带 tool_call_id 以满足协议配对要求）
                tool_msg = Message(
                    role=RoleType.TOOL,
                    name=function_name,
                    content=str(result),
                    tool_call_id=tool_call.id,
                )
                self.add_message(tool_msg)

        return "已达最大多轮工具调用轮数。"
