import re
from typing import Any, Dict, List, Optional
from src.core.agent import Agent
from src.core.exceptions import AgentException
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.tools.registry import ToolRegistry, global_tool_registry

REACT_SYSTEM_PROMPT_TEMPLATE = """尽力回答以下问题。你可以使用以下工具：

{tools_desc}

回答请遵循以下格式规范：

Question: 必须回答的输入问题
Thought: 你应该思考下一步该做什么
Action: 采取的行动，格式为工具名称与参数，例如: action_name[action_input]
Observation: 行动的输出结果
... (上述 Thought/Action/Observation 可以重复多次)
Thought: 我现在知道最终答案了
Finish[最终对用户的回答]

开始！
"""


class ReActAgent(Agent):
    """
    Hello Agents 经典范式：ReAct 智能体 (Reasoning + Acting)
    基于 Thought-Action-Observation-Finish 格式实现思考与外部行动交互循环
    """
    def __init__(
        self,
        name: str = "ReActAgent",
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[ToolRegistry] = None,
        max_steps: int = 5,
    ):
        super().__init__(name=name, llm=llm, tools=tools or global_tool_registry)
        self.max_steps = max_steps
        self.action_pattern = re.compile(r"Action:\s*([a-zA-Z0-9_\-]+)\[(.*?)\]", re.DOTALL)
        self.finish_pattern = re.compile(r"Finish\[(.*?)\]", re.DOTALL)

    def _render_tools_description(self) -> str:
        """格式化可用工具的文本列表供提示词使用"""
        if not isinstance(self.tools, ToolRegistry):
            return "无可用工具"
        tool_lines = []
        for tool in self.tools.list_tools():
            params_str = ", ".join([f"{p.name}: {p.type}" for p in tool.parameters])
            tool_lines.append(f"- {tool.name}({params_str}): {tool.description}")
        return "\n".join(tool_lines) or "无可用工具"

    def run(self, input_text: str, **kwargs: Any) -> str:
        """执行 ReAct 思考与行动闭环"""
        tools_desc = self._render_tools_description()
        system_prompt = REACT_SYSTEM_PROMPT_TEMPLATE.format(tools_desc=tools_desc)

        self.clear_history()
        self.add_message(Message.system(system_prompt))
        self.add_message(Message.user(f"Question: {input_text}"))

        step = 0
        prompt_accumulator = f"Question: {input_text}\n"

        while step < self.max_steps:
            step += 1
            # 请求 LLM 产生下一步思考或行动
            response = self.llm.chat(messages=self.get_history(), **kwargs)
            self.add_message(Message.assistant(response))
            prompt_accumulator += response + "\n"

            # 检查是否达成最终结论 Finish[...]
            finish_match = self.finish_pattern.search(response)
            if finish_match:
                return finish_match.group(1).strip()

            # 解析 Action: tool[param]
            action_match = self.action_pattern.search(response)
            if not action_match:
                # 若未匹配出标准 Action 也未 Finish，返回最后一次生成内容作为解答
                return response.strip()

            tool_name = action_match.group(1).strip()
            tool_input = action_match.group(2).strip()

            # 执行工具调用
            try:
                if isinstance(self.tools, ToolRegistry):
                    # 尝试将参数作为单一参数或默认参数传递
                    observation = self.tools.execute(tool_name, query=tool_input)
                else:
                    observation = f"错误: 未配置有效的工具注册表"
            except Exception as e:
                observation = f"执行工具 {tool_name} 失败: {str(e)}"

            obs_text = f"Observation: {observation}"
            self.add_message(Message.user(obs_text))
            prompt_accumulator += obs_text + "\n"

        return f"达到最大步数 ({self.max_steps})，未得出确定答案。最后推理过程: {prompt_accumulator[-200:]}"
