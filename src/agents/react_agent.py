import inspect
import json
import logging
import re
from typing import Any, Dict, Optional
from src.core.agent import Agent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.tools.base import Tool, ToolParameter
from src.tools.registry import ToolRegistry, global_tool_registry

logger = logging.getLogger(__name__)

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

    def _parse_action_input(self, tool_name: str, action_input: str) -> Dict[str, Any]:
        """解析 ReAct Action[input] 的传参，支持 JSON 字典、键值对及自省单参类型匹配。

        参数:
            tool_name: 工具名称
            action_input: Action 原始输入文本

        返回:
            传递给工具执行的 kwargs 字典
        """
        raw = action_input.strip()
        if not raw:
            return {}

        # 1. 优先尝试解析为合法 JSON 字典
        if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
                elif isinstance(parsed, list):
                    return {"items": parsed}
            except Exception:
                pass

        # 2. 检查 tool 实例与参数自描述
        tool: Optional[Tool] = self.tools.get(tool_name) if isinstance(self.tools, ToolRegistry) else None

        # 检查是否为 key=value 形式，且 key 存在于工具参数中
        if "=" in raw and not raw.startswith("="):
            possible_key, possible_val = raw.split("=", 1)
            possible_key = possible_key.strip()
            if possible_key.isidentifier() and tool and hasattr(tool, "parameters"):
                param_names = [p.name for p in tool.parameters if isinstance(p, ToolParameter)]
                if possible_key in param_names:
                    return {possible_key: possible_val.strip()}

        # 3. 单值传参：自动推导工具目标参数名与类型
        target_param_name = "query"
        target_param_type = "string"

        if tool is not None:
            if hasattr(tool, "parameters") and tool.parameters:
                first_param = tool.parameters[0]
                if isinstance(first_param, ToolParameter):
                    target_param_name = first_param.name
                    target_param_type = first_param.type
                elif isinstance(first_param, dict) and "name" in first_param:
                    target_param_name = first_param["name"]
                    target_param_type = first_param.get("type", "string")
            else:
                # 通过函数签名自省获取首个非 self 显式参数名
                try:
                    sig = inspect.signature(tool.execute)
                    for p_name, p in sig.parameters.items():
                        if p_name not in ("self", "args", "kwargs") and p.kind in (
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                            inspect.Parameter.KEYWORD_ONLY,
                        ):
                            target_param_name = p_name
                            break
                except Exception as e:
                    logger.debug(f"自省工具签名失败: {e}")

        # 4. 根据目标类型进行安全类型转换
        converted_val: Any = raw
        if target_param_type in ("integer", "int"):
            try:
                converted_val = int(raw)
            except ValueError:
                pass
        elif target_param_type in ("number", "float"):
            try:
                converted_val = float(raw)
            except ValueError:
                pass
        elif target_param_type in ("boolean", "bool"):
            if raw.lower() in ("true", "1", "yes"):
                converted_val = True
            elif raw.lower() in ("false", "0", "no"):
                converted_val = False

        return {target_param_name: converted_val}

    def execute_action(self, tool_name: str, action_input: str) -> str:
        """执行工具调用并返回观察文本，对外提供可独立单元测试的标准入口"""
        if not isinstance(self.tools, ToolRegistry):
            return "错误: 未配置有效的工具注册表"

        try:
            kwargs = self._parse_action_input(tool_name, action_input)
            observation = self.tools.execute(tool_name, **kwargs)
            return str(observation)
        except Exception as e:
            return f"执行工具 {tool_name} 失败: {str(e)}"

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
            observation = self.execute_action(tool_name, tool_input)

            obs_text = f"Observation: {observation}"
            self.add_message(Message.user(obs_text))
            prompt_accumulator += obs_text + "\n"

        return f"达到最大步数 ({self.max_steps})，未得出确定答案。最后推理过程: {prompt_accumulator[-200:]}"
