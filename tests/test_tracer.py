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
