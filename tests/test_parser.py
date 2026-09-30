"""
单元测试: RobustAgentParser 容错自愈解析器测试套件
命名规范: test_<功能>_<场景>_<期望结果>
"""
from src.core.parser import RobustAgentParser
from src.core.schema import SentimentAnalysisResult, SentimentStance

def test_parser_standard_json_returns_model_instance():
    """测试标准纯 JSON 字符串能够成功解析为 Pydantic 实例"""
    raw_json = '''{
        "stance": "bullish",
        "sentiment_score": 0.85,
        "is_sarcasm": false,
        "slang_detected": ["主力建仓", "主升浪"],
        "reasoning": "散户对后市走势充满信心"
    }'''
    instance, feedback = RobustAgentParser.parse_or_build_feedback(raw_json, SentimentAnalysisResult)
    assert feedback is None
    assert instance is not None
    assert instance.stance == SentimentStance.BULLISH
    assert instance.sentiment_score == 0.85
    assert instance.is_sarcasm is False
    assert "主力建仓" in instance.slang_detected

def test_parser_markdown_code_block_stripping_succeeds():
    """测试带有 ```json 代码块及前后置自然语言解释时，能正确剥除并成功解析"""
    raw_output = '''好的，我已经完成了对该发帖的深度语义消歧，结果如下：
    ```json
    {
        "stance": "bearish",
        "sentiment_score": -0.75,
        "is_sarcasm": true,
        "slang_detected": ["好耶", "关灯吃面"],
        "reasoning": "明夸实贬，具有强烈的反向嘲讽特征"
    }
    ```
    希望上述分析对您的研判策略有帮助！'''
    instance, feedback = RobustAgentParser.parse_or_build_feedback(raw_output, SentimentAnalysisResult)
    assert feedback is None
    assert instance is not None
    assert instance.stance == SentimentStance.BEARISH
    assert instance.sentiment_score == -0.75
    assert instance.is_sarcasm is True

def test_parser_raw_text_without_code_block_extracts_outer_curly_brackets():
    """测试没有 markdown 代码块但夹杂在文本中的 json 对象能被正则贪婪提取"""
    raw_output = (
        '分析结果为: {"stance": "neutral", "sentiment_score": 0.0, '
        '"is_sarcasm": false, "slang_detected": [], "reasoning": "纯客观中立公告"} 以上！'
    )
    instance, feedback = RobustAgentParser.parse_or_build_feedback(raw_output, SentimentAnalysisResult)
    assert feedback is None
    assert instance is not None
    assert instance.stance == SentimentStance.NEUTRAL
    assert instance.sentiment_score == 0.0

def test_parser_syntax_error_returns_informative_feedback():
    """测试畸变或截断的不合法 JSON 能被安全捕获并返回语法错误提示"""
    broken_json = '{"stance": "bullish", "sentiment_score": 0.85, "reasoning": '
    instance, feedback = RobustAgentParser.parse_or_build_feedback(broken_json, SentimentAnalysisResult)
    assert instance is None
    assert feedback is not None
    assert "JSON 语法解析失败" in feedback

def test_parser_pydantic_validation_error_returns_field_guidance():
    """测试字段取值越界（如 sentiment_score > 1.0）时，能够精准定位错误字段生成反思 Prompt"""
    out_of_bound_json = '''{
        "stance": "bullish",
        "sentiment_score": 99.9,
        "is_sarcasm": false,
        "slang_detected": [],
        "reasoning": "越界的分数"
    }'''
    instance, feedback = RobustAgentParser.parse_or_build_feedback(out_of_bound_json, SentimentAnalysisResult)
    assert instance is None
    assert feedback is not None
    assert "sentiment_score" in feedback
    assert "校验不通过" in feedback

def test_parser_empty_or_none_input_safely_returns_feedback():
    """测试模型输出 None 或纯空白字符时安全返回反馈，不抛出 AttributeError"""
    instance1, feedback1 = RobustAgentParser.parse_or_build_feedback(None, SentimentAnalysisResult)
    assert instance1 is None
    assert "模型输出为空" in feedback1

    instance2, feedback2 = RobustAgentParser.parse_or_build_feedback("   ", SentimentAnalysisResult)
    assert instance2 is None
    assert "模型输出为空" in feedback2
