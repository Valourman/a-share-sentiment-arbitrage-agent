"""
单元测试: 工具层 (Tools) 功能与边界测试套件
命名规范: test_<功能>_<场景>_<期望结果>
"""
import pytest
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.market import MarketDataTool
from src.tools.scraper import StockForumScraper
from src.core.schema import RawPost, SentimentStance

@pytest.fixture
def analyzer():
    return FinancialSentimentAnalyzer()

@pytest.fixture
def market_tool():
    return MarketDataTool()

@pytest.fixture
def scraper():
    return StockForumScraper()

def test_analyzer_mock_bullish_slang_detected(analyzer):
    """测试 mock 模式下正确检测多头黑话并判定看多立场"""
    post = RawPost(
        title="主力资金大笔建仓，即将启动主升浪翻倍！",
        author="股神",
        publish_time="09:30",
        read_count=100,
        comment_count=10
    )
    res = analyzer.analyze_mock(post)
    assert res.stance == SentimentStance.BULLISH
    assert res.sentiment_score > 0
    assert "主力建仓" in res.slang_detected or "主升浪" in res.slang_detected

def test_analyzer_mock_sarcasm_detected(analyzer):
    """测试反讽关键词并存时判定为反语看空"""
    post = RawPost(
        title="好耶，主力送钱，天天跌停太棒了！",
        author="韭菜小张",
        publish_time="15:00",
        read_count=50,
        comment_count=5
    )
    res = analyzer.analyze_mock(post)
    assert res.is_sarcasm is True
    assert res.stance == SentimentStance.BEARISH
    assert res.sentiment_score < 0

def test_market_tool_format_secid_prefixes(market_tool):
    """测试不同市场个股代码前缀的正确映射规则"""
    assert market_tool._format_secid("600519") == "sh600519"
    assert market_tool._format_secid("900901") == "sh900901"
    assert market_tool._format_secid("002594") == "sz002594"
    assert market_tool._format_secid("300750") == "sz300750"
    assert market_tool._format_secid("832000") == "bj832000"
    assert market_tool._format_secid("sh600000") == "sh600000"

def test_scraper_spam_filtering(scraper):
    """测试水军推广与违规导流文本的准确过滤"""
    assert scraper._is_spam("加微信进群领取牛股推荐") is True
    assert scraper._is_spam("私信免费领取涨停战法") is True
    assert scraper._is_spam("长电科技三季报业绩符合预期，机构调高评级") is False
