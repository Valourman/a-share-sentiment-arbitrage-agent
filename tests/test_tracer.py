"""AgentTracer 链路追踪器单元测试 (合并自 gallant-satoshi worktree)"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from src.core.tracer import AgentTracer, TraceSpan


def test_span_success_records_duration():
    tracer = AgentTracer()
    with tracer.span('fetch_market', 'tool', inputs={'code': '600519'}) as s:
        time.sleep(0.01)
        s.outputs = {'price': 1700.0}

    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.status == 'success'
    assert span.duration >= 0.01
    assert span.inputs == {'code': '600519'}
    assert span.outputs == {'price': 1700.0}


def test_span_failure_captures_error_and_reraises():
    tracer = AgentTracer()
    with pytest.raises(ValueError):
        with tracer.span('llm_call', 'llm'):
            raise ValueError('schema broken')

    span = tracer.spans[0]
    assert span.status == 'failed'
    assert 'schema broken' in span.error


def test_summary_aggregates_latency_tokens_and_failures():
    tracer = AgentTracer()
    with tracer.span('step1', 'loop_step') as s:
        s.tokens_used = 100
    with tracer.span('step2', 'tool') as s:
        s.tokens_used = 50
    try:
        with tracer.span('step3', 'reflect'):
            raise RuntimeError('boom')
    except RuntimeError:
        pass

    summary = tracer.get_summary()
    assert summary['total_spans'] == 3
    assert summary['total_tokens'] == 150
    assert summary['total_latency_seconds'] == tracer.get_total_latency()
    assert summary['has_error'] is True
    assert summary['failed_spans'] == ['step3']


def test_tracespan_defaults():
    span = TraceSpan(name='x', span_type='tool')
    assert span.status == 'running'
    assert span.end_time is None
    assert span.tokens_used == 0


def test_engine_run_populates_tracer_spans():
    """集成测试: engine.run 全流程应产出 4 个链路跨度且写入审计日志"""
    from unittest.mock import patch
    from src.agent.engine import SentimentArbitrageAgent
    from src.core.market_schema import MarketSnapshot
    from src.core.schema import RawPost

    agent = SentimentArbitrageAgent()
    mock_posts = [
        RawPost(title='主力吸筹完毕，明天直接主升浪起飞！'),
        RawPost(title='好耶，主力又送钱了，接着跌！'),
    ]
    mock_snapshot = MarketSnapshot(
        stock_code='600584', stock_name='长电科技', current_price=28.5,
        pre_close=30.0, change_percent=-5.0, turnover_amount_yi=10.0, is_trading=True,
    )
    with patch.object(agent.scraper, 'fetch_guba_posts', return_value=mock_posts), \
         patch.object(agent.scraper, 'fetch_financial_news', return_value=[]), \
         patch.object(agent.scraper, 'fetch_announcements', return_value=[]), \
         patch.object(agent.market_tool, 'fetch_snapshot', return_value=mock_snapshot):
        final_state = agent.run(stock_code='600584', max_posts=2, use_llm=False)

    summary = agent.tracer.get_summary()
    span_names = [s.name for s in agent.tracer.spans]
    assert summary['total_spans'] == 4
    assert span_names == ['intel_collection', 'sentiment_disambiguation', 'market_snapshot', 'divergence_reflection']
    assert summary['has_error'] is False
    assert all(s.status == 'success' and s.duration >= 0 for s in agent.tracer.spans)
    assert any('[链路追踪]' in line for line in final_state.execution_logs)


def test_engine_tracer_resets_between_runs():
    """连续两次 run 之间 tracer 应自动重置，不累计跨度"""
    from unittest.mock import patch
    from src.agent.engine import SentimentArbitrageAgent
    from src.core.market_schema import MarketSnapshot
    from src.core.schema import RawPost

    agent = SentimentArbitrageAgent()
    mock_posts = [RawPost(title='突破年线压制，放量换手充分！')]
    mock_snapshot = MarketSnapshot(
        stock_code='600519', stock_name='贵州茅台', current_price=1700.0,
        pre_close=1690.0, change_percent=0.6, turnover_amount_yi=50.0, is_trading=True,
    )
    with patch.object(agent.scraper, 'fetch_guba_posts', return_value=mock_posts), \
         patch.object(agent.scraper, 'fetch_financial_news', return_value=[]), \
         patch.object(agent.scraper, 'fetch_announcements', return_value=[]), \
         patch.object(agent.market_tool, 'fetch_snapshot', return_value=mock_snapshot):
        agent.run(stock_code='600519', max_posts=1, use_llm=False)
        agent.run(stock_code='600519', max_posts=1, use_llm=False)

    assert agent.tracer.get_summary()['total_spans'] == 4
