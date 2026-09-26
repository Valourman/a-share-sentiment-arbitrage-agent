from unittest.mock import patch

from src.core.market_schema import MarketSnapshot
from src.core.schema import AnnouncementItem, NewsArticle, RawPost, SentimentAnalysisResult, SentimentStance
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState, DivergenceType
from src.workflow.nodes import (
    ArbitrageArbitrationNode,
    CatalystType,
    FundamentalCatalystNode,
    MultiAgentDebateNode,
)
from src.workflow.pipeline import FinancialWorkflowPipeline
from src.workflow.state import DebateStance


def test_fundamental_catalyst_node():
    """测试基本面催化剂与风险项提取节点"""
    node = FundamentalCatalystNode()

    mock_news = [
        NewsArticle(
            title="太极实业签署重大战略合作协议，业绩有望实现高增长突破",
            source="新浪财经",
            publish_time="2026-09-25",
        ),
        NewsArticle(
            title="行业面临短期需求下滑与减持风险警示",
            source="证券时报",
            publish_time="2026-09-25",
        ),
    ]
    mock_announcements = [
        AnnouncementItem(
            title="关于中标重大工程项目暨签订日常经营重大合同的公告",
            publish_time="2026-09-25",
        ),
    ]

    catalysts, risks = node.run(mock_news, mock_announcements, stock_name="太极实业")

    assert len(catalysts) >= 2
    assert any(c.catalyst_type == CatalystType.POSITIVE for c in catalysts)
    assert any("中标" in c.source_title or "增长" in c.source_title for c in catalysts)

    assert len(risks) >= 1
    assert any(r.catalyst_type == CatalystType.NEGATIVE for r in risks)
    assert any("下滑" in r.source_title or "减持" in r.source_title for r in risks)


def test_multi_agent_debate_node_bull_and_bear():
    """测试多智能体多空对抗辩论节点 (BullAnalyst vs BearAnalyst)"""
    node = MultiAgentDebateNode()

    state = AgentState(stock_code="600584", stock_name="长电科技")
    state.average_sentiment = 0.35  # 散户狂热看多
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=28.0,
        pre_close=30.0,
        change_percent=-6.67,  # 盘面大跌，形成背离
        turnover_amount_yi=12.0,
        is_trading=True,
    )
    state.sentiment_list = [
        SentimentAnalysisResult(
            stance=SentimentStance.BULLISH,
            sentiment_score=0.8,
            is_sarcasm=True,  # 存在反讽
            reasoning="表面看多实际反讽主力出货",
        )
    ]

    mock_catalyst_node = FundamentalCatalystNode()
    cats, risks = mock_catalyst_node.run([], [])

    debate_res = node.run(state, cats, risks)

    # 验证多头观点
    assert debate_res.bull_opinion.agent_name.startswith("BullAnalyst")
    assert debate_res.bull_opinion.stance == DebateStance.BULLISH
    assert len(debate_res.bull_opinion.arguments) > 0

    # 验证空头观点
    assert debate_res.bear_opinion.agent_name.startswith("BearAnalyst")
    assert debate_res.bear_opinion.stance == DebateStance.BEARISH
    assert any("诱多" in arg or "反讽" in arg for arg in debate_res.bear_opinion.arguments)

    # 验证分歧与态势
    assert "背离" in debate_res.key_divergence_point or "多空" in debate_res.key_divergence_point
    assert "诱多" in debate_res.consensus_bias or "空方" in debate_res.consensus_bias
    assert "风控委员会" in debate_res.arbitration_summary


def test_arbitrage_arbitration_node():
    """测试终审风控背离裁决节点"""
    debate_node = MultiAgentDebateNode()
    arbitration_node = ArbitrageArbitrationNode()

    state = AgentState(stock_code="600584", stock_name="长电科技")
    state.average_sentiment = 0.30
    state.sentiment_sample_count = 5
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=28.0,
        pre_close=30.0,
        change_percent=-6.67,
        turnover_amount_yi=12.0,
        is_trading=True,
    )

    debate_res = debate_node.run(state, [], [])
    decision = arbitration_node.run(state, debate_res)

    assert decision.is_divergent is True
    assert decision.divergence_type == DivergenceType.BULL_TRAP
    assert "多智能体辩论决议" in decision.reflection_narrative
    assert len(decision.action_suggestion) > 0


def test_financial_workflow_pipeline_execution():
    """测试 FinancialWorkflowPipeline 端到端完整多智能体工作流"""
    pipeline = FinancialWorkflowPipeline()

    mock_posts = [
        RawPost(title="主力洗盘充分，明天涨停！", author="股神", publish_time="10:00"),
        RawPost(title="好耶，跌停又送钱了！", author="散户", publish_time="10:01"),
    ]
    mock_news = [
        NewsArticle(title="太极实业重组预案获批准", source="新浪财经", publish_time="2026-09-25"),
    ]
    mock_ann = [
        AnnouncementItem(title="关于获得重大产业基金投资的公告", publish_time="2026-09-25"),
    ]
    mock_market = MarketSnapshot(
        stock_code="600667",
        stock_name="太极实业",
        current_price=10.0,
        pre_close=9.5,
        change_percent=5.26,
        turnover_amount_yi=5.0,
        is_trading=True,
    )

    with patch.object(pipeline.scraper, "fetch_guba_posts", return_value=mock_posts), \
         patch.object(pipeline.scraper, "fetch_financial_news", return_value=mock_news), \
         patch.object(pipeline.scraper, "fetch_announcements", return_value=mock_ann), \
         patch.object(pipeline.market_tool, "fetch_snapshot", return_value=mock_market):

        progress_calls = []

        def on_progress(p, msg):
            progress_calls.append((p, msg))

        state = pipeline.run(
            stock_code="600667",
            max_posts=2,
            use_llm=False,
            progress_callback=on_progress,
        )

        assert state.stock_code == "600667"
        assert state.stock_name == "太极实业"
        assert len(state.sentiment_list) == 2
        assert len(state.catalysts) >= 1
        assert state.debate_result is not None
        assert state.debate_result.bull_opinion is not None
        assert state.debate_result.bear_opinion is not None
        assert state.reflection is not None
        assert any("[工作流 Phase 1]" in log for log in state.execution_logs)
        assert any("[工作流 Phase 4]" in log for log in state.execution_logs)
        assert len(progress_calls) >= 4
        assert progress_calls[-1][0] == 1.0


def test_sentiment_arbitrage_agent_workflow_mode():
    """测试通过 SentimentArbitrageAgent 启动 workflow_mode"""
    agent = SentimentArbitrageAgent()

    mock_posts = [RawPost(title="长电科技拉升在即！")]
    mock_market = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=30.0,
        pre_close=30.0,
        change_percent=0.0,
        turnover_amount_yi=5.0,
        is_trading=True,
    )

    with patch.object(agent.scraper, "fetch_guba_posts", return_value=mock_posts), \
         patch.object(agent.scraper, "fetch_financial_news", return_value=[]), \
         patch.object(agent.scraper, "fetch_announcements", return_value=[]), \
         patch.object(agent.market_tool, "fetch_snapshot", return_value=mock_market):

        state = agent.run("600584", max_posts=1, use_llm=False, workflow_mode=True)
        assert state.stock_code == "600584"
        assert state.debate_result is not None
        assert state.reflection is not None
        summary = agent.tracer.get_summary()
        assert summary["total_spans"] >= 4
