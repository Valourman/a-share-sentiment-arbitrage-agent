from abc import abstractmethod
from typing import Any, Dict, List, Optional
from src.core.agent import Agent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.tools.registry import ToolRegistry, global_tool_registry

INITIAL_GENERATE_PROMPT = """请根据以下任务要求提供初步的解决方案或回答：
{task}
"""

REFLECT_CRITIQUE_PROMPT = """请对以下初步解答进行严谨、客观的批判性审查：
【原始任务】: {task}
【初步方案】: {solution}

请指出其中存在的潜在错误、事实矛盾、逻辑漏洞或不完善之处。
"""

REFINE_PROMPT = """结合审查批判意见，对初步方案进行迭代修正，提供最终完善的高质量成果：
【原始任务】: {task}
【初步方案】: {solution}
【批判意见】: {critique}

请输出修正后的最终完整解答：
"""


class ReflectionAgent(Agent):
    """
    Hello Agents 经典范式：ReflectionAgent (自我反思智能体)
    抽象通用闭环：
    1. 生成初稿/初步决策 (Initial Execution)
    2. 批判审查与事实校验 (Critique & Fact Verification)
    3. 自我反思与生成优化建议 (Self-Reflection & Refinement)
    """
    def __init__(
        self,
        name: str = "ReflectionAgent",
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[ToolRegistry] = None,
        max_iterations: int = 2,
    ):
        super().__init__(name=name, llm=llm, tools=tools or global_tool_registry)
        self.max_iterations = max_iterations

    def execute_initial(self, input_text: str, **kwargs: Any) -> Any:
        """步骤一：执行初步推理或感知采集 (默认基于 Prompt 初步生成)"""
        prompt = INITIAL_GENERATE_PROMPT.format(task=input_text)
        return self.llm.chat([Message.user(prompt)], **kwargs)

    def evaluate_critique(self, initial_result: Any, **kwargs: Any) -> Any:
        """步骤二：对照事实基准或验证规则进行评估审查 (默认基于 Prompt 批判)"""
        task = kwargs.get("input_text", "")
        prompt = REFLECT_CRITIQUE_PROMPT.format(task=task, solution=str(initial_result))
        return self.llm.chat([Message.user(prompt)], **kwargs)

    def reflect_and_refine(
        self,
        initial_result: Any,
        critique: Any,
        **kwargs: Any,
    ) -> Any:
        """步骤三：反思背离与矛盾，输出最终修订后的结构化决策报告 (默认基于 Prompt 修正)"""
        task = kwargs.get("input_text", "")
        prompt = REFINE_PROMPT.format(
            task=task,
            solution=str(initial_result),
            critique=str(critique),
        )
        return self.llm.chat([Message.user(prompt)], **kwargs)

    def run(self, input_text: str, **kwargs: Any) -> Any:
        """标准化反思执行流程"""
        self.add_message(Message.user(f"启动反思任务: {input_text}"))
        exec_kwargs = dict(kwargs)

        # 1. 初步执行
        initial_result = self.execute_initial(input_text, **exec_kwargs)

        # 2. 批判审查
        critique = self.evaluate_critique(initial_result, input_text=input_text, **exec_kwargs)

        # 3. 反思提炼
        final_decision = self.reflect_and_refine(
            initial_result, critique, input_text=input_text, **exec_kwargs
        )

        self.add_message(Message.assistant("完成自我反思与多源交叉校验决策"))
        return final_decision
