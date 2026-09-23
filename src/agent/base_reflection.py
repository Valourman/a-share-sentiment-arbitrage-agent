from abc import abstractmethod
from typing import Any, Dict, List, Optional
from src.core.agent import BaseAgent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.tools.registry import ToolRegistry, global_tool_registry


class ReflectionAgent(BaseAgent):
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

    @abstractmethod
    def execute_initial(self, input_text: str, **kwargs: Any) -> Any:
        """步骤一：执行初步推理或感知采集"""
        pass

    @abstractmethod
    def evaluate_critique(self, initial_result: Any, **kwargs: Any) -> Dict[str, Any]:
        """步骤二：对照事实基准或验证规则进行评估审查"""
        pass

    @abstractmethod
    def reflect_and_refine(
        self,
        initial_result: Any,
        critique: Dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """步骤三：反思背离与矛盾，输出最终修订后的结构化决策报告"""
        pass

    def run(self, input_text: str, **kwargs: Any) -> Any:
        """标准化反思执行流程"""
        self.add_message(Message.user(f"启动反思任务: {input_text}"))

        # 1. 初步执行
        initial_result = self.execute_initial(input_text, **kwargs)

        # 2. 批判审查
        critique = self.evaluate_critique(initial_result, **kwargs)

        # 3. 反思提炼
        final_decision = self.reflect_and_refine(initial_result, critique, **kwargs)

        self.add_message(Message.assistant("完成自我反思与多源交叉校验决策"))
        return final_decision
