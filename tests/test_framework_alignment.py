"""Regression tests for the framework/business boundary and data quality."""

from unittest.mock import patch

from src.agent.base_reflection import ReflectionAgent as LegacyReflectionAgent
from src.agent.conversational import ConversationalArbitrageAgent
from src.agent.decision import assess_divergence, build_reflection_decision
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState, DivergenceType, RiskLevel
from src.agents.reflection_agent import ReflectionAgent
from src.core.config import AgentConfig
from src.core.llm import HelloAgentsLLM
from src.core.market_schema import MarketSnapshot
from src.core.schema import RawPost
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.registry import ToolRegistry


def snapshot(*, valid: bool, change: float = 0.0) -> MarketSnapshot:
    return MarketSnapshot(
        stock_code="600584", stock_name="长电科技" if valid else "未识别标的",
        current_price=30.0 if valid else 0.0,
        pre_close=30.0 if valid else 0.0,
        change_percent=change, turnover_amount_yi=10.0 if valid else 0.0,
        is_trading=valid,
    )


def test_legacy_reflection_path_reexports_canonical_paradigm():
    assert LegacyReflectionAgent is ReflectionAgent


def test_agent_binds_its_own_configured_llm_to_sentiment_tool():
    llm = HelloAgentsLLM(config=AgentConfig(default_model="unit-test-model"))
    agent = SentimentArbitrageAgent(llm=llm)
    assert agent.analyzer.llm is llm
    assert agent.analyzer.model_name == "unit-test-model"


def test_explicit_registry_can_override_sentiment_tool():
    llm = HelloAgentsLLM(config=AgentConfig(default_model="injected-model"))
    analyzer = FinancialSentimentAnalyzer(llm=llm)
    registry = ToolRegistry()
    registry.register(analyzer)
    agent = SentimentArbitrageAgent(tools=registry)
    assert agent.analyzer is analyzer


def test_failed_quote_never_turns_zero_into_panic_bottom_signal():
    agent = SentimentArbitrageAgent()
    posts = [RawPost(title="好耶，天天跌停又吃面了，主力送钱！")]
    with patch.object(agent.scraper, "fetch_guba_posts", return_value=posts), \
         patch.object(agent.scraper, "fetch_financial_news", return_value=[]), \
         patch.object(agent.scraper, "fetch_announcements", return_value=[]), \
         patch.object(agent.market_tool, "fetch_snapshot", return_value=snapshot(valid=False)):
        state = agent.run("600584", use_llm=False)

    assert state.sentiment_sample_count == 1
    assert state.reflection.divergence_type == DivergenceType.INSUFFICIENT_DATA
    assert state.reflection.risk_level == RiskLevel.UNKNOWN
    assert state.reflection.is_divergent is False
    assert "有效行情" in state.reflection.reflection_narrative
    assert any("未取得有效行情" in log for log in state.execution_logs)

    reply = ConversationalArbitrageAgent()._synthesize_stock_answer("能买入吗？", state)
    assert "数据不足" in reply and "成交额" in reply
    assert "暂不提供买卖判断" in reply


def test_zero_posts_does_not_pass_as_neutral_sentiment():
    state = AgentState(stock_code="600584", market_data=snapshot(valid=True), sentiment_sample_count=0)
    critique = assess_divergence(state)
    decision = build_reflection_decision(state, critique)
    assert decision.divergence_type == DivergenceType.INSUFFICIENT_DATA
    assert "有效舆情样本" in decision.reflection_narrative


def test_reflection_consumes_the_critique_instead_of_reclassifying():
    agent = SentimentArbitrageAgent()
    state = AgentState(stock_code="600584", average_sentiment=0.7, sentiment_sample_count=1)
    with patch.object(agent.market_tool, "fetch_snapshot", return_value=snapshot(valid=True, change=-2.0)):
        critique = agent.evaluate_critique(state)
    assert critique["divergence_label"] == DivergenceType.BULL_TRAP
    state.average_sentiment = -0.7  # A later mutation must not silently change the approved critique.
    final = agent.reflect_and_refine(state, critique)
    assert final.reflection.divergence_type == DivergenceType.BULL_TRAP
    assert "主力出货" in final.reflection.reflection_narrative
    assert "无法证实" in final.reflection.reflection_narrative
