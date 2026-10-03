"""P0 阻断性缺陷修复专项单元测试套件

涵盖:
1. ReActAgent 工具传参重构（参数解析、类型转换、自省匹配与独立 execute_action 验证）
2. src/memory/tools.py 全局单例隐式注册机制移除与显式注册 / 依赖注入
3. RRF 倒数排名融合归一化（统一量纲、[0, 1] 范围保证、双路协同增益）
4. DivergenceType._missing_ 中文简写支持与空串防御
"""

import pytest
from unittest.mock import MagicMock

from src.core.llm import HelloAgentsLLM
from src.agents.react_agent import ReActAgent
from src.tools.base import Tool, ToolParameter
from src.tools.registry import ToolRegistry
from src.memory.manager import MemoryManager
from src.memory.knowledge import FinancialKnowledgeRetriever
from src.memory.tools import MemoryTool, RAGTool, register_memory_tools
from src.knowledge.schema import Document
from src.knowledge.embeddings import DeterministicHashEmbedding
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.agent.state import DivergenceType


# ==============================================================================
# P0-1: ReActAgent 工具传参逻辑重构与独立测试
# ==============================================================================

class MultiParamTool(Tool):
    """具有多参数与非 query 参数名的测试工具"""
    name = "stock_query"
    description = "查询股票行情"
    parameters = [
        ToolParameter(name="code", type="string", description="股票代码", required=True),
        ToolParameter(name="days", type="integer", description="查询天数", required=False, default=5),
        ToolParameter(name="include_news", type="boolean", description="是否包含新闻", required=False, default=False),
    ]

    def execute(self, code: str, days: int = 5, include_news: bool = False, **kwargs):
        return f"查询成功: code={code}, days={days}, news={include_news}"


class SingleExprCalcTool(Tool):
    """参数名为 expr 的计算工具"""
    name = "math_calc"
    description = "数学表达式计算"
    parameters = [
        ToolParameter(name="expr", type="string", description="计算表达式", required=True)
    ]

    def execute(self, expr: str, **kwargs):
        return f"计算表达式: {expr}"


def test_react_agent_parse_action_input_json():
    """测试 ReActAgent 对 JSON 格式结构化传参的精确解析"""
    registry = ToolRegistry()
    registry.register(MultiParamTool())
    agent = ReActAgent(name="TestAgent", tools=registry)

    # 1. 完整 JSON 字典传参
    parsed = agent._parse_action_input(
        "stock_query", '{"code": "600519", "days": 10, "include_news": true}'
    )
    assert parsed == {"code": "600519", "days": 10, "include_news": True}

    # 2. 独立调用 execute_action
    obs = agent.execute_action("stock_query", '{"code": "600519", "days": 10, "include_news": true}')
    assert obs == "查询成功: code=600519, days=10, news=True"


def test_react_agent_parse_action_input_single_value_adaptation():
    """测试单值传参自动适配到工具的首个非 query 参数并做类型推导"""
    registry = ToolRegistry()
    registry.register(SingleExprCalcTool())
    agent = ReActAgent(name="TestAgent", tools=registry)

    # 单值字符串传参自动映射到 expr
    parsed = agent._parse_action_input("math_calc", "100 * 20")
    assert parsed == {"expr": "100 * 20"}

    obs = agent.execute_action("math_calc", "100 * 20")
    assert obs == "计算表达式: 100 * 20"


def test_react_agent_full_run_with_custom_param_tool():
    """测试 ReActAgent 完整 run 闭环能够成功调用非 query 参数工具"""
    mock_llm = MagicMock(spec=HelloAgentsLLM)
    mock_llm.chat.side_effect = [
        'Thought: 需要计算数值\nAction: math_calc[3.14 * 2]',
        'Thought: 得到结果\nFinish[计算完毕]',
    ]

    registry = ToolRegistry()
    registry.register(SingleExprCalcTool())

    agent = ReActAgent(name="TestReAct", llm=mock_llm, tools=registry, max_steps=3)
    reply = agent.run("计算圆周率两倍")

    assert reply == "计算完毕"
    assert mock_llm.chat.call_count == 2
    # 验证 Observation 消息正确传入上下文
    history = agent.get_history()
    obs_msgs = [m for m in history if "Observation: 计算表达式: 3.14 * 2" in m.content]
    assert len(obs_msgs) == 1


# ==============================================================================
# P0-2: 移除全局单例隐式注册机制，改为显式注册或依赖注入
# ==============================================================================

def test_memory_tools_explicit_registration_and_isolation():
    """测试显式注册机制，隔离全局副作用"""
    custom_registry = ToolRegistry()
    custom_manager = MemoryManager()
    custom_retriever = FinancialKnowledgeRetriever()

    # 验证未注册前不存在对应工具
    assert custom_registry.get("memory_manager") is None
    assert custom_registry.get("rag_search") is None

    # 显式注入依赖与注册
    mem_tool, rag_tool = register_memory_tools(
        registry=custom_registry,
        manager=custom_manager,
        retriever=custom_retriever,
    )

    assert isinstance(mem_tool, MemoryTool)
    assert isinstance(rag_tool, RAGTool)
    assert custom_registry.get("memory_manager") is mem_tool
    assert custom_registry.get("rag_search") is rag_tool
    assert mem_tool.manager is custom_manager
    assert rag_tool.retriever is custom_retriever


# ==============================================================================
# P0-3: RRF 融合打分归一化与统一量纲
# ==============================================================================

def test_rrf_scores_normalized_to_unit_interval():
    """测试 RRF 融合打分严格归一化在 [0.0, 1.0] 区间内，且双路命中文档得分显著优于单路"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model, chunk_size=200, chunk_overlap=30)

    doc_target = Document(
        doc_id="doc_both",
        title="双路命中测试",
        content="长江电力发布年度分红预案，现金流充沛且股息率高，经营极为稳健。",
        stock_code="600900",
    )
    doc_other = Document(
        doc_id="doc_other",
        title="其他电力公司",
        content="华能国际发布火电上网电价调整公告，煤电联动平稳。",
        stock_code="600011",
    )
    kb.add_document(doc_target)
    kb.add_document(doc_other)

    results = kb.retrieve(query="长江电力 分红预案 股息率", top_k=2, decay_half_life_days=None)
    assert len(results) > 0

    for r in results:
        # 分数必须严格落在 0.0 到 1.0 之间
        assert 0.0 <= r.score <= 1.0

    # 最佳结果得分不应为微小的 0.033，而应达到可信的归一化高分 (> 0.5)
    assert results[0].score > 0.5


# ==============================================================================
# P0-4: DivergenceType._missing_ 中文简写支持与防御
# ==============================================================================

def test_divergence_type_supports_chinese_shorthands():
    """测试 DivergenceType 正确支持中文简写与别名输入"""
    # 1. 中文简写
    assert DivergenceType("诱多") == DivergenceType.BULL_TRAP
    assert DivergenceType("多头诱多") == DivergenceType.BULL_TRAP
    assert DivergenceType("磨底") == DivergenceType.PANIC_BOTTOM
    assert DivergenceType("恐慌磨底") == DivergenceType.PANIC_BOTTOM
    assert DivergenceType("一致") == DivergenceType.CONSISTENT
    assert DivergenceType("情绪与盘面一致") == DivergenceType.CONSISTENT
    assert DivergenceType("数据不足") == DivergenceType.INSUFFICIENT_DATA
    assert DivergenceType("不足") == DivergenceType.INSUFFICIENT_DATA

    # 2. 原生枚举名与完整值仍然兼容
    assert DivergenceType("BULL_TRAP") == DivergenceType.BULL_TRAP
    assert DivergenceType("多头诱多 (BULL_TRAP)") == DivergenceType.BULL_TRAP


def test_divergence_type_rejects_empty_and_unknown_strings():
    """测试 DivergenceType 拒绝空串与无效字符串，不静默判定为 BULL_TRAP"""
    with pytest.raises(ValueError):
        DivergenceType("")

    with pytest.raises(ValueError):
        DivergenceType("   ")

    with pytest.raises(ValueError):
        DivergenceType("UNKNOWN_RANDOM_VALUE")
