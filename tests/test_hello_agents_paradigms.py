from unittest.mock import MagicMock
import pytest
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.agents.simple_agent import SimpleAgent
from src.agents.react_agent import ReActAgent
from src.agents.reflection_agent import ReflectionAgent
from src.agents.plan_solve_agent import PlanAndSolveAgent
from src.agents.function_call_agent import FunctionCallAgent
from src.tools.registry import ToolRegistry
from src.tools.base import Tool, ToolParameter


class DummyCalcTool(Tool):
    name = "add"
    description = "加法计算"
    parameters = [ToolParameter(name="query", type="string", description="加数")]

    def execute(self, **kwargs):
        return "计算结果为 10"


def test_simple_agent():
    mock_llm = MagicMock(spec=HelloAgentsLLM)
    mock_llm.chat.return_value = "这是智能体的测试回复"

    agent = SimpleAgent(name="TestSimple", system_prompt="助手提示词", llm=mock_llm)
    reply = agent.run("你好")

    assert reply == "这是智能体的测试回复"
    assert len(agent.get_history()) == 3  # system, user, assistant
    assert agent.get_history()[0].content == "助手提示词"


def test_react_agent():
    mock_llm = MagicMock(spec=HelloAgentsLLM)
    # 模拟两轮交互：第一轮 Action 调用 add，第二轮 Finish
    mock_llm.chat.side_effect = [
        "Thought: 我需要计算\nAction: add[5+5]",
        "Thought: 拿到计算结果了\nFinish[答案是10]",
    ]

    registry = ToolRegistry()
    registry.register(DummyCalcTool())

    agent = ReActAgent(name="TestReAct", llm=mock_llm, tools=registry, max_steps=3)
    res = agent.run("5+5等于几？")

    assert res == "答案是10"
    assert mock_llm.chat.call_count == 2


def test_reflection_agent():
    mock_llm = MagicMock(spec=HelloAgentsLLM)
    mock_llm.chat.side_effect = [
        "初步方案：快速买入",
        "批判意见：存在高位追涨风险，未看成交量",
        "最终优化方案：暂且观望，等待放量企稳后再做布局",
    ]

    agent = ReflectionAgent(name="TestReflection", llm=mock_llm)
    final_res = agent.run("针对标的股票给出策略")

    assert "最终优化方案" in final_res
    assert mock_llm.chat.call_count == 3


def test_plan_solve_agent():
    mock_llm = MagicMock(spec=HelloAgentsLLM)
    mock_llm.chat.side_effect = [
        '["步骤1: 数据清洗", "步骤2: 趋势研判"]',  # Planner
        "步骤1完成，已去除空值",                 # Step 1
        "步骤2完成，趋势向上",                 # Step 2
        "综合报告：标的健康且向上",             # Summary
    ]

    agent = PlanAndSolveAgent(name="TestPlanSolve", llm=mock_llm)
    res = agent.run("分析数据集")

    assert res == "综合报告：标的健康且向上"
    assert mock_llm.chat.call_count == 4
