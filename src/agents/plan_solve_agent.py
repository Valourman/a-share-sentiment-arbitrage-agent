import json
import logging
import re
from typing import Any, List, Optional
from src.core.agent import Agent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message

logger = logging.getLogger(__name__)

PLANNER_PROMPT_TEMPLATE = """针对给定的复杂问题，制定一个清晰、精炼、按步骤分解的执行计划。
请严格输出一个 JSON 格式的字符串列表，不要输出任何多余的解释或包裹文字。
格式示例:
["步骤1: 分析用户核心诉求", "步骤2: 检索相关背景资料与数据", "步骤3: 汇总并生成最终分析报告"]

用户问题: {question}
"""

EXECUTOR_STEP_PROMPT_TEMPLATE = """你正在按规划步骤解决以下问题：
【总体问题】: {question}
【当前步骤】: {step}
【先前步骤执行结果】:
{previous_context}

请聚焦于当前步骤，给出这一步的具体分析、计算或执行产出：
"""

SUMMARY_PROMPT_TEMPLATE = """请基于以下所有步骤的执行过程与结果，汇总输出给用户的最终完整答案：
【总体问题】: {question}
【各步骤执行记录】:
{all_steps_context}

最终答案:
"""


class PlanAndSolveAgent(Agent):
    """
    Hello Agents 经典范式：PlanAndSolveAgent (规划与求解智能体)
    包含两阶段机制：
    1. Planner：将宏观任务分解为严谨有序的步骤列表
    2. Executor：结合历史执行上下文，逐步求解每一步骤并最终汇总
    """
    def __init__(
        self,
        name: str = "PlanAndSolveAgent",
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[Any] = None,
    ):
        super().__init__(name=name, llm=llm, tools=tools)

    def plan(self, question: str, **kwargs: Any) -> List[str]:
        """第一阶段：调用 LLM 分解规划步骤"""
        planner_prompt = PLANNER_PROMPT_TEMPLATE.format(question=question)
        response = self.llm.chat([Message.user(planner_prompt)], **kwargs)

        # 尝试从响应中提取 JSON 数组
        try:
            # 去除可能存在的 markdown 代码块标记
            cleaned = re.sub(r"^```json\s*", "", response.strip())
            cleaned = re.sub(r"^```\s*", "", cleaned)
            cleaned = re.sub(r"```$", "", cleaned).strip()
            steps = json.loads(cleaned)
            if isinstance(steps, list) and steps:
                return [str(s) for s in steps]
        except Exception as e:
            logger.debug(f"计划 JSON 解析失败，退化为按行提取。原始响应片段: {response[:120]!r} ({e})")

        # 兜底按行提取非空行（仅剥除列表前缀符号，避免把数字开头的正文一并剥掉）
        lines = [re.sub(r"^[\s\-\d\.、]+(?=\S)", "", line).strip() for line in response.splitlines() if line.strip()]
        return lines if lines else [question]

    def execute_step(self, question: str, step: str, previous_context: str, **kwargs: Any) -> str:
        """第二阶段：单步执行"""
        step_prompt = EXECUTOR_STEP_PROMPT_TEMPLATE.format(
            question=question,
            step=step,
            previous_context=previous_context or "暂无先前步骤",
        )
        return self.llm.chat([Message.user(step_prompt)], **kwargs)

    def run(self, input_text: str, **kwargs: Any) -> str:
        """执行规划与逐步求解流程"""
        self.clear_history()
        self.add_message(Message.user(f"复杂任务规划输入: {input_text}"))

        # 1. 制定计划
        steps = self.plan(input_text, **kwargs)
        plan_summary = f"规划完成，共拆解为 {len(steps)} 个子步骤:\n" + "\n".join(
            [f"{i+1}. {s}" for i, s in enumerate(steps)]
        )
        self.add_message(Message.assistant(plan_summary))

        # 2. 依次执行
        execution_records = []
        for i, step in enumerate(steps):
            prev_ctx = "\n".join(execution_records)
            step_result = self.execute_step(input_text, step, prev_ctx, **kwargs)
            record = f"[步骤 {i+1}: {step}]\n执行结果: {step_result.strip()}"
            execution_records.append(record)
            self.add_message(Message.assistant(record))

        # 3. 最终汇总
        all_steps_context = "\n\n".join(execution_records)
        summary_prompt = SUMMARY_PROMPT_TEMPLATE.format(
            question=input_text,
            all_steps_context=all_steps_context,
        )
        final_answer = self.llm.chat([Message.user(summary_prompt)], **kwargs)
        self.add_message(Message.assistant(final_answer))

        return final_answer
