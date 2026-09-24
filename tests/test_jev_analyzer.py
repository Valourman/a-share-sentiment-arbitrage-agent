import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
import pytest
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.core.schema import RawPost, SentimentStance

# Jev 在线引擎测试依赖 TYPESAFE_API_KEY，未配置时自动跳过（离线 CI 环境保持全绿）
requires_jev_key = pytest.mark.skipif(
    not os.getenv('TYPESAFE_API_KEY'),
    reason='需要配置 TYPESAFE_API_KEY 才能运行 Jev 在线引擎测试'
)


@requires_jev_key
def test_jev_initialization():
    """验证 Jev 引擎环境变量加载与基础初始化"""
    analyzer = FinancialSentimentAnalyzer()
    assert analyzer.typesafe_api_key is not None
    assert 'typesafe' in analyzer.typesafe_base_url
    assert analyzer.typesafe_model == 'jev-latest'


@requires_jev_key
def test_jev_bullish_classification():
    """验证 Jev 对典型看多黑话的单步决策"""
    analyzer = FinancialSentimentAnalyzer()
    post = RawPost(title="主力吸筹完毕，明天直接主升浪起飞！")
    result = analyzer.analyze(post, engine_mode="jev")

    assert result.engine_used == "jev"
    assert result.stance == SentimentStance.BULLISH
    assert result.is_sarcasm is False
    assert result.sentiment_score > 0.0
    assert result.latency_ms is not None
    assert result.confidence is not None


@requires_jev_key
def test_jev_sarcasm_and_bearish():
    """验证 Jev 对复杂反讽与正话反说的消歧能力"""
    analyzer = FinancialSentimentAnalyzer()
    post = RawPost(title="好耶，主力又给老子送钱了，接着跌，不跌满10个点我不姓张！")
    result = analyzer.analyze(post, engine_mode="jev")

    assert result.engine_used == "jev"
    assert result.stance == SentimentStance.BEARISH
    assert result.is_sarcasm is True
    assert result.sentiment_score < 0.0
    assert result.sarcasm_probability is not None
    assert result.sarcasm_probability >= 0.5


@requires_jev_key
def test_jev_neutral_news():
    """验证 Jev 对中性公告的客观研判"""
    analyzer = FinancialSentimentAnalyzer()
    post = RawPost(title="关于召开2026年第一次临时股东大会的通知。")
    result = analyzer.analyze(post, engine_mode="jev")

    assert result.engine_used == "jev"
    assert result.stance == SentimentStance.NEUTRAL
    assert abs(result.sentiment_score) <= 0.35


def test_graceful_fallback():
    """验证当缺少 Key 或指定 mock 时的平滑降级"""
    analyzer = FinancialSentimentAnalyzer()
    post = RawPost(title="明天开盘直接割肉出货")
    result = analyzer.analyze(post, engine_mode="mock")

    assert result.engine_used == "mock"
    assert result.stance == SentimentStance.BEARISH


if __name__ == "__main__":
    test_jev_initialization()
    print("test_jev_initialization: PASSED")
    test_jev_bullish_classification()
    print("test_jev_bullish_classification: PASSED")
    test_jev_sarcasm_and_bearish()
    print("test_jev_sarcasm_and_bearish: PASSED")
    test_jev_neutral_news()
    print("test_jev_neutral_news: PASSED")
    test_graceful_fallback()
    print("test_graceful_fallback: PASSED")
    print("\n 所有 Jev 引擎测试用例全部通过！")
