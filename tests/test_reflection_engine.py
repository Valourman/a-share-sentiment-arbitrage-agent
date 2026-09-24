"""
单元测试: 反思研判与决策回路 (Reflection Loop) 测试套件
命名规范: test_<功能>_<场景>_<期望结果>
"""
import pytest
from unittest.mock import MagicMock, patch
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState, DivergenceType, RiskLevel
from src.core.market_schema import MarketSnapshot
from src.core.schema import RawPost, SentimentAnalysisResult, SentimentStance

@pytest.fixture
def agent_instance():
    return SentimentArbitrageAgent()

def test_reflection_bull_trap_when_sentiment_high_and_price_drops(agent_instance):
    """测试当散户情绪亢奋看多 (>=0.25) 但盘面大幅下挫 (< -0.5%) 时触发 BULL_TRAP"""
    state = AgentState(stock_code="600584")
    state.average_sentiment = 0.65
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=28.5,
        pre_close=30.0,
        change_percent=-5.0,
        turnover_amount_yi=10.0,
        is_trading=True
    )

    decision = agent_instance._reflect_on_divergence(state)
    assert decision.is_divergent is True
    assert decision.divergence_type == DivergenceType.BULL_TRAP
    assert decision.risk_level == RiskLevel.HIGH
    assert "多头诱多" in decision.reflection_narrative

def test_reflection_panic_bottom_when_sentiment_low_and_price_resilient(agent_instance):
    """测试当散户极度恐慌割肉 (<= -0.25) 但盘面抗跌红盘 (>= 0.0%) 时触发 PANIC_BOTTOM"""
    state = AgentState(stock_code="002594")
    state.average_sentiment = -0.55
    state.market_data = MarketSnapshot(
        stock_code="002594",
        stock_name="比亚迪",
        current_price=250.0,
        pre_close=248.0,
        change_percent=0.81,
        turnover_amount_yi=35.0,
        is_trading=True
    )

    decision = agent_instance._reflect_on_divergence(state)
    assert decision.is_divergent is True
    assert decision.divergence_type == DivergenceType.PANIC_BOTTOM
    assert decision.risk_level == RiskLevel.MEDIUM
    assert "悲观绝望" in decision.reflection_narrative
    assert "恐慌盘" in decision.action_suggestion

def test_reflection_consistent_when_sentiment_aligns_with_price(agent_instance):
    """测试散户情绪与盘面走势共振时判定为 CONSISTENT 平稳状态"""
    state = AgentState(stock_code="600519")
    state.average_sentiment = 0.40
    state.market_data = MarketSnapshot(
        stock_code="600519",
        stock_name="贵州茅台",
        current_price=1750.0,
        pre_close=1720.0,
        change_percent=1.74,
        turnover_amount_yi=60.0,
        is_trading=True
    )

    decision = agent_instance._reflect_on_divergence(state)
    assert decision.is_divergent is False
    assert decision.divergence_type == DivergenceType.CONSISTENT
    assert decision.risk_level == RiskLevel.LOW

def test_agent_run_pipeline_with_mock_tools(agent_instance):
    """测试通过 Mock 工具链执行 Agent.run 完整流水线"""
    mock_posts = [
        RawPost(title="长电科技主升浪启动！", author="股民小李", publish_time="10:00", read_count=100, comment_count=10),
        RawPost(title="好耶，又吃面了，太棒了主力送钱！", author="韭菜本菜", publish_time="10:05", read_count=200, comment_count=25),
    ]
    mock_snapshot = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=30.0,
        pre_close=30.0,
        change_percent=0.0,
        turnover_amount_yi=8.0,
        is_trading=True
    )

    with patch.object(agent_instance.scraper, "fetch_guba_posts", return_value=mock_posts), \
         patch.object(agent_instance.market_tool, "fetch_snapshot", return_value=mock_snapshot):

        final_state = agent_instance.run(stock_code="600584", max_posts=2, use_llm=False)
        assert final_state.stock_code == "600584"
        assert final_state.stock_name == "长电科技"
        assert len(final_state.sentiment_list) == 2
        assert final_state.reflection is not None
        assert final_state.iteration_count == 1


def test_agent_run_pipeline_with_progress_callback(agent_instance):
    """测试通过 progress_callback 实时报告执行进度与当前阶段"""
    mock_posts = [
        RawPost(title="主升浪启动", author="张三", publish_time="10:00", read_count=10, comment_count=1),
    ]
    mock_snapshot = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=30.0,
        pre_close=30.0,
        change_percent=1.0,
        turnover_amount_yi=10.0,
        is_trading=True
    )

    progress_records = []

    def dummy_callback(progress: float, desc: str):
        progress_records.append((progress, desc))

    with patch.object(agent_instance.scraper, "fetch_guba_posts", return_value=mock_posts), \
         patch.object(agent_instance.market_tool, "fetch_snapshot", return_value=mock_snapshot):

        agent_instance.run(
            stock_code="600584",
            max_posts=1,
            use_llm=False,
            progress_callback=dummy_callback
        )

    # 验证关键阶段均触发了进度更新且单调递增至 1.0 (100%)
    assert len(progress_records) >= 4
    percentages = [p[0] for p in progress_records]
    assert percentages[0] > 0.0
    assert percentages[-1] == 1.0
    assert percentages == sorted(percentages)


def test_agent_records_disambiguation_and_execution_logs(agent_instance):
    """测试 Agent 在研判全过程中将散户消歧依据与反思决策链路完整记入 execution_logs"""
    mock_posts = [
        RawPost(title="两点理由往后可以关注闽泰：国家介入是支撑利好", author="散户甲", publish_time="10:00", read_count=120, comment_count=5),
        RawPost(title="好耶，跌停又吃面了，感谢主力送钱！", author="散户乙", publish_time="10:05", read_count=210, comment_count=18),
    ]
    mock_snapshot = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=30.0,
        pre_close=30.0,
        change_percent=0.0,
        turnover_amount_yi=8.0,
        is_trading=True
    )

    with patch.object(agent_instance.scraper, "fetch_guba_posts", return_value=mock_posts), \
         patch.object(agent_instance.market_tool, "fetch_snapshot", return_value=mock_snapshot):

        final_state = agent_instance.run(stock_code="600584", max_posts=2, use_llm=False)

    # 验证执行日志完整记录
    logs = final_state.execution_logs
    assert len(logs) >= 5  # 采集 + 2条消歧 + 情绪聚合 + 行情对照 + 反思决策

    # 验证第一条语料消歧日志包含依据与标签
    disambiguate_logs = [l for l in logs if "[语料消歧 #" in l]
    assert len(disambiguate_logs) == 2
    assert "大模型消歧依据:" in disambiguate_logs[0]
    assert "大模型消歧依据:" in disambiguate_logs[1]
    assert "识别到反讽语义翻转" in disambiguate_logs[1]

    # 验证行情对照与反思推导阶段亦有日志归档
    assert any("[行情事实对照]" in l for l in logs)
    assert any("[多维反思决策]" in l for l in logs)

