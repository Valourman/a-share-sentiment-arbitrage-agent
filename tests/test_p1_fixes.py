"""P1 协议与语法警告清理专项单元测试套件

涵盖:
1. DisambiguationNode 统一引擎分发路由 (_dispatch_single) 与降级逻辑验证
2. 串行与并发模式下 DisambiguationNode 输出与语料严格等长对应性
3. evals/public_benchmark.py 指标计算函数与混淆矩阵验证
"""

from unittest.mock import MagicMock
from src.core.schema import RawPost, SentimentAnalysisResult, SentimentStance
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.workflow.nodes import DisambiguationNode
from evals.public_benchmark import compute_metrics, build_confusion_matrix


def test_disambiguation_node_unified_dispatch_routing():
    """测试 DisambiguationNode._dispatch_single 统一路由分发"""
    mock_analyzer = MagicMock(spec=FinancialSentimentAnalyzer)
    expected_result = SentimentAnalysisResult(
        raw_title="测试发帖",
        stance=SentimentStance.BULLISH,
        sentiment_score=0.8,
        is_sarcasm=False,
        confidence=0.9,
        reasoning="看多情绪明确",
    )
    mock_analyzer.analyze.return_value = expected_result

    node = DisambiguationNode(analyzer=mock_analyzer)
    post = RawPost(title="测试发帖")

    res = node._dispatch_single(post, engine_mode="mock", use_llm=False)
    assert res == expected_result
    mock_analyzer.analyze.assert_called_once_with(post, engine_mode="mock", use_llm=False)


def test_disambiguation_node_dispatch_fallback_on_exception():
    """测试 DisambiguationNode._dispatch_single 遇到异常时自动降级到 mock 规则引擎"""
    mock_analyzer = MagicMock(spec=FinancialSentimentAnalyzer)
    mock_analyzer.analyze.side_effect = RuntimeError("网络异常")

    fallback_result = SentimentAnalysisResult(
        raw_title="异常发帖",
        stance=SentimentStance.NEUTRAL,
        sentiment_score=0.0,
        is_sarcasm=False,
        confidence=0.5,
        reasoning="网络异常降级",
        engine_used="mock",
    )
    mock_analyzer.analyze_mock.return_value = fallback_result

    node = DisambiguationNode(analyzer=mock_analyzer)
    post = RawPost(title="异常发帖")

    res = node._dispatch_single(post, engine_mode="llm", use_llm=True)
    assert res == fallback_result
    mock_analyzer.analyze_mock.assert_called_once_with(post)


def test_disambiguation_node_run_maintains_order_and_length():
    """测试 DisambiguationNode.run 无论是串行还是并发均严格保持结果等长与顺序对齐"""
    mock_analyzer = MagicMock(spec=FinancialSentimentAnalyzer)

    def side_effect_analyze(post, **kwargs):
        return SentimentAnalysisResult(
            raw_title=post.title,
            stance=SentimentStance.BULLISH,
            sentiment_score=0.5,
            is_sarcasm=False,
            confidence=0.8,
            reasoning="研判依据",
        )

    mock_analyzer.analyze.side_effect = side_effect_analyze
    node = DisambiguationNode(analyzer=mock_analyzer)

    # 1. 2条以内（串行）
    short_posts = [RawPost(title=f"短语料_{i}") for i in range(2)]
    res_short = node.run(short_posts, use_llm=False)
    assert len(res_short) == 2
    assert res_short[0].raw_title == "短语料_0"
    assert res_short[1].raw_title == "短语料_1"

    # 2. 5条（并发执行）
    long_posts = [RawPost(title=f"长语料_{i}") for i in range(5)]
    res_long = node.run(long_posts, use_llm=True, max_workers=2)
    assert len(res_long) == 5
    for i in range(5):
        assert res_long[i].raw_title == f"长语料_{i}"


def test_public_benchmark_compute_metrics():
    """测试 evals/public_benchmark.py 的指标计算准确性"""
    actuals = ["bullish", "bearish", "neutral", "bullish"]
    preds = ["bullish", "bearish", "bullish", "bullish"]
    classes = ["bullish", "bearish", "neutral"]

    acc, metrics, macro_f1 = compute_metrics(actuals, preds, classes)
    assert acc == 0.75  # 3/4
    assert "bullish" in metrics
    assert metrics["bullish"]["support"] == 2
    assert 0.0 <= macro_f1 <= 1.0

    matrix = build_confusion_matrix(actuals, preds, classes)
    assert matrix["bullish"]["bullish"] == 2
    assert matrix["neutral"]["bullish"] == 1
