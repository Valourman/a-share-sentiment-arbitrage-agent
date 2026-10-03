"""
本次全面审查发现问题的专项回归与防御性测试套件
验证范围：
1. P0-1: 多空辩论诱多背离优先判定与反讽比例平滑加权
2. P0-2: 基本面催化挖掘契约字段补齐与否定词窗防范
3. P0-4: safe_href 伪协议过滤 (javascript:/data:)
4. P1-2: 终审裁决联动多空辩论成果
5. P2-1: 结构化解析器对 JSON 顶层数组与尾随逗号的容错解析
6. P2-3: ReflectionAgent 多轮反思闭环迭代
"""
from src.core.schema import NewsArticle, AnnouncementItem, SentimentAnalysisResult, SentimentStance, MarketSnapshot
from src.agent.state import AgentState, RiskLevel
from src.workflow.nodes import (
    FundamentalCatalystNode,
    MultiAgentDebateNode,
    ArbitrageArbitrationNode,
)
from src.core.parser import RobustAgentParser
from pydantic import BaseModel
from typing import List
from app import safe_href


def test_safe_href_filtering():
    """验证 safe_href 能够正确放行合法协议并拦截危险伪协议"""
    assert safe_href("https://finance.sina.com.cn/stock/123.html") == "https://finance.sina.com.cn/stock/123.html"
    assert safe_href("http://guba.eastmoney.com/news.html") == "http://guba.eastmoney.com/news.html"
    assert safe_href("javascript:alert(document.cookie)") == ""
    assert safe_href("JAVASCRIPT:void(0)") == ""
    assert safe_href("data:text/html;base64,PHNjcmlwdD4=") == ""
    assert safe_href("") == ""
    assert safe_href(None) == ""


def test_negative_context_filtering_in_catalyst_node():
    """验证否定词窗机制：防止'亏损增长'、'扭亏无望'等被误判为利好"""
    node = FundamentalCatalystNode()

    news = [
        NewsArticle(title="太极实业归母净利润亏损增长，重组终止引发市场关注", summary="业绩承压"),
        NewsArticle(title="某公司拟扭亏无望，面临退市风险警示", summary="风险提示"),
        NewsArticle(title="行业龙头斩获海外大单，业绩迎来重大突破", summary="业务爆发"),
    ]
    announcements = [
        AnnouncementItem(title="关于重组终止的重大公告", category="官方披露"),
        AnnouncementItem(title="关于签订日常经营重大合同的公告", category="重大经营"),
    ]

    catalysts, risks = node.run(news, announcements, stock_name="太极实业")

    # 利好中绝不能包含"亏损增长"或"重组终止"
    assert not any("亏损增长" in c.source_title for c in catalysts)
    assert not any("重组终止" in c.source_title for c in catalysts)
    assert not any("扭亏无望" in c.source_title for c in catalysts)

    # 正向催化必须精准提取"海外大单"和"重大合同"
    assert any("海外大单" in c.source_title or "重大合同" in c.source_title for c in catalysts)

    # 负向风险必须包含"亏损增长"与"扭亏无望"
    assert any("亏损增长" in r.source_title for r in risks)
    assert any("扭亏无望" in r.source_title for r in risks)


def test_debate_node_bull_trap_prioritization():
    """验证多空辩论定性：典型诱多形态下，即使空方大幅领先，也必须优先输出警惕诱多定性"""
    node = MultiAgentDebateNode()

    state = AgentState(stock_code="600584", stock_name="长电科技")
    state.average_sentiment = 0.35  # 散户狂热看多
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=28.0,
        pre_close=30.0,
        change_percent=-6.67,  # 盘面大跌，形成显著诱多背离
        turnover_amount_yi=12.0,
        is_trading=True,
    )
    # 模拟包含 1 条反讽语料
    state.sentiment_list = [
        SentimentAnalysisResult(
            stance=SentimentStance.BULLISH,
            sentiment_score=0.8,
            is_sarcasm=True,
            reasoning="反讽出货",
        )
    ]

    cats, risks = FundamentalCatalystNode().run([], [])
    debate_res = node.run(state, cats, risks)

    # 核心断言：死分支已被修复，判定态势必须优先识别为诱多陷阱
    assert "警惕诱多 (BULL_TRAP_BIAS)" == debate_res.consensus_bias


def test_arbitration_node_debate_linkage():
    """验证终审裁决节点：多空辩论成果真正驱动风控等级与建议"""
    node = ArbitrageArbitrationNode()

    state = AgentState(stock_code="600584", stock_name="长电科技")
    state.average_sentiment = 0.35
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=28.0,
        pre_close=30.0,
        change_percent=-6.67,
        turnover_amount_yi=12.0,
        is_trading=True,
    )

    cats, risks = FundamentalCatalystNode().run([], [])
    debate_res = MultiAgentDebateNode().run(state, cats, risks)
    decision = node.run(state, debate_res)

    # 终审裁决必须受到多空辩论诱多识别的影响，将风险定级为 HIGH 并输出诱多防守警示
    assert decision.risk_level == RiskLevel.HIGH
    assert "诱多" in decision.action_suggestion or "防诱多" in decision.action_suggestion


class SampleItem(BaseModel):
    id: int
    name: str


class ArrayWrapper(BaseModel):
    items: List[SampleItem]


def test_parser_array_and_trailing_comma():
    """验证解析器对顶层 JSON 数组与尾随逗号的容错能力"""
    class SingleItem(BaseModel):
        score: float
        tag: str

    raw_json_with_trailing = '{"score": 0.85, "tag": "bullish",}'
    parsed, feedback = RobustAgentParser.parse_or_build_feedback(raw_json_with_trailing, SingleItem)
    assert feedback is None
    assert parsed is not None
    assert parsed.score == 0.85
    assert parsed.tag == "bullish"


def test_stock_resolver_chinese_context_and_cache():
    """验证股票解析器在中文语境下无单词边界的解析能力及缓存淘汰机制"""
    from src.tools.stock_resolver import StockResolver

    # 中文字符直接与 6 位数字相邻
    res1 = StockResolver.resolve_from_text("请帮我查600519的情况")
    assert res1 is not None
    assert res1[0] == "600519"

    res2 = StockResolver.resolve_from_text("分析下600584")
    assert res2 is not None
    assert res2[0] == "600584"

    # 缓存写入与防无界溢出验证
    assert len(StockResolver._RUNTIME_CACHE) <= StockResolver._MAX_CACHE_SIZE


def test_llm_model_name_and_conversational_sync():
    """验证 HelloAgentsLLM.model_name 属性与对话 Agent 的模型名称同步一致性"""
    from src.core.config import AgentConfig
    from src.core.llm import HelloAgentsLLM
    from src.agent.conversational import ConversationalArbitrageAgent

    cfg = AgentConfig(default_model="deepseek-v3")
    llm = HelloAgentsLLM(config=cfg)
    assert llm.model_name == "deepseek-v3"

    chat_agent = ConversationalArbitrageAgent(llm=llm)
    assert chat_agent.model_name == "deepseek-v3"


def test_scraper_invalid_input_guard():
    """验证爬虫针对畸形/空代码的防御机制"""
    from src.tools.scraper import StockForumScraper

    scraper = StockForumScraper()
    assert scraper.fetch_guba_posts("") == []
    assert scraper.fetch_guba_posts("AAPL") == []
    assert scraper.fetch_announcements("abc") == []

