"""金融垂直领域 RAG 知识检索库端到端集成测试套件

测试场景覆盖：
1. 真实长文档（重大资产重组公告、券商行业深度研报）的分块、双路索引、混合检索与 Agent 上下文格式化
2. ToolRegistry 工具注册中心深度集成（Schema 自省、集中调度与参数传递）
3. A 股散户极端情绪与深层反讽黑话消歧端到端场景（字面多/实为空）
4. 突发公告 vs 历史研报的时间衰减动态排序与标的代码严格隔离
5. 极端边界与自愈容错能力验证
"""

import time
from typing import List

import pytest

from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.knowledge.schema import Document, KnowledgeType, RetrievalResult
from src.knowledge.tools import FinancialKnowledgeTool
from src.tools.base import ToolResult
from src.tools.registry import ToolRegistry, global_tool_registry


# ---------------------------------------------------------------------------
# 测试固件与样例长文档构建
# ---------------------------------------------------------------------------

SAMPLE_ANNOUNCEMENT_TEXT = """
【重要事项公告】证券代码：600667 证券简称：太极实业 公告编号：2026-088。
无锡市太极实业股份有限公司关于发行股份及支付现金购买资产并募集配套资金暨关联交易预案。

一、本次交易方案概述与交易背景说明
公司拟通过发行股份及支付现金的方式，向无锡市产业发展集团等特定对象购买其持有的半导体材料制造有限公司100%股权。
本次交易完成后，标的公司将成为上市公司的全资子公司，将大幅补强上市公司在上游半导体封装测试以及特种核心材料领域的自主研发与供应链保障能力。

二、标的资产估值与交易价格预估
截至本次预案签署日，标的公司的审计和资产评估工作尚未完成。经初步友好协商，标的公司预估值约为人民币35.50亿元。
最终交易价格将以符合《证券法》规定的资产评估机构出具的资产评估报告为依据，由交易各方在后续补充协议中正式确认。

三、审批风险与不确定性提示
本次交易尚需获得公司董事会二次审议、股东大会批准、上海证券交易所审核以及中国证监会同意注册。
由于涉及反垄断审查与产业安全评估，本次重组能否取得上述批复以及最终取得批复的时间均存在不确定性。
提醒广大投资者理性投资，防范二级市场盲目跟风与短期炒作风险。
特此公告。无锡市太极实业股份有限公司董事会。
"""

SAMPLE_RESEARCH_REPORT_TEXT = """
【行业深度研究报告】半导体先进封装与材料产业链2026年度展望：周期筑底确立，国产替代迈入深水区。

一、报告核心摘要与产业演进趋势
随着高性能计算（HPC）、端侧AI算力芯片以及汽车智能化的加速渗透，先进封装（Chiplet、2.5D/3D堆叠）已成为突破摩尔定律物理极限的核心支柱。
在产业链细分领域中，环氧塑封料（EMC）、硅微粉填料以及引线框架等核心半导体耗材需求迎来爆发式反弹。

二、重点龙头标的深度梳理与资产协同潜力
重点关注具备资产注入预期与自主可控能力的龙头企业，如太极实业（600667）、通富微电等核心封测与材料巨头。
随着国有资本产业整合提速，上游优质半导体资产置入有望带来显著估值弹性与利润增厚。

三、估值分析、投资评级与关键风险提示
当前行业整体动态市盈率处于历史25%分位数，安全边际充分，维持行业“强于大市”评级。
重大风险提示：下游消费电子需求不及预期风险；国际贸易摩擦升级与技术封锁加剧风险；并购整合与业务协同不及预期风险。
"""


@pytest.fixture
def empty_kb() -> FinancialRAGKnowledgeBase:
    """提供纯净空知识库实例，针对小文本使用更小分块以验证密集切片行为"""
    return FinancialRAGKnowledgeBase(chunk_size=180, chunk_overlap=30)


@pytest.fixture
def populated_rag_kb() -> FinancialRAGKnowledgeBase:
    """构建包含重组公告、深度研报与多条 A 股核心情绪黑话的高保真知识库"""
    kb = FinancialRAGKnowledgeBase(chunk_size=200, chunk_overlap=40)

    now_ts = time.time()
    fresh_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts - 1800))
    old_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts - 86400 * 60))

    # 1. 录入上市公司重组公告长文档 (新鲜公告)
    announcement_doc = Document(
        doc_id="ann_600667_088",
        title="太极实业重大资产购买预案公告",
        content=SAMPLE_ANNOUNCEMENT_TEXT.strip(),
        doc_type=KnowledgeType.ANNOUNCEMENT,
        stock_code="600667",
        publish_time=fresh_time_str,
        metadata={"category": "重大重组", "importance": "high"},
    )
    kb.add_document(announcement_doc)

    # 2. 录入行业研报长文档 (60天前历史研报)
    report_doc = Document(
        doc_id="rep_semi_2026",
        title="半导体先进封装行业深度研究报告",
        content=SAMPLE_RESEARCH_REPORT_TEXT.strip(),
        doc_type=KnowledgeType.REPORT,
        stock_code="600667",
        publish_time=old_time_str,
        metadata={"category": "券商研报", "rating": "买入"},
    )
    kb.add_document(report_doc)

    # 3. 录入典型 A 股散户黑话与反讽特征
    kb.add_knowledge_item(
        term="关灯吃面",
        category="情绪黑话",
        definition="源于散户在重度亏损暴跌当晚极度悲观绝望的情绪表征，属于极度恐慌见底信号，真实立场为极度看空。",
        sentiment_bias=-0.95,
        stock_code=None,
    )
    kb.add_knowledge_item(
        term="主力又送钱了",
        category="反讽模式",
        definition="散户在股票连续跌停破防后的赌气反讽。字面看似感谢主力，本质是极度愤怒与绝望，真实立场极度看空。",
        sentiment_bias=-0.90,
        stock_code=None,
    )
    kb.add_knowledge_item(
        term="牛回速归",
        category="情绪黑话",
        definition="市场短期微涨时部分散户盲目亢奋、跟风诱多的情绪口号，常伴随流动性衰竭与主力出货风险，需警惕诱多陷阱。",
        sentiment_bias=0.80,
        stock_code=None,
    )
    kb.add_knowledge_item(
        term="利好出尽",
        category="量化规则",
        definition="重大利好消息正式落地兑现后，获利盘集中抛压兑现，股价反而大概率大幅低开或高开低走，俗称见光死。",
        sentiment_bias=-0.60,
        stock_code=None,
    )

    return kb


# ---------------------------------------------------------------------------
# 测试用例 1: 长文档加载、智能切片、双路索引、混合检索与 Agent 上下文格式化
# ---------------------------------------------------------------------------

def test_e2e_long_document_announcement_and_report_rag_pipeline(empty_kb):
    """端到端长文档处理流水线：分块切片 -> 稠密/稀疏双路索引 -> RRF 融合召回 -> 格式化输出"""
    kb = empty_kb

    # 注入长篇重组公告
    doc = Document(
        doc_id="doc_ann_600667",
        title="太极实业资产重组预案",
        content=SAMPLE_ANNOUNCEMENT_TEXT.strip(),
        doc_type=KnowledgeType.ANNOUNCEMENT,
        stock_code="600667",
    )

    chunks = kb.add_document(doc)
    assert len(chunks) >= 3, f"长文本应通过滑动窗口切片为不少于3个切片，实际生成 {len(chunks)}"
    assert kb.total_chunks == len(chunks)

    # 验证切片具备正确的父文档标识与股票代码
    for chunk in chunks:
        assert chunk.doc_id == "doc_ann_600667"
        assert chunk.stock_code == "600667"
        assert len(chunk.text) > 0

    # 针对长文档中的特定核心章节发起精确关键词与语义检索
    results: List[RetrievalResult] = kb.retrieve(
        query="重大资产重组 拟购买资产 审批风险与不确定性",
        top_k=3,
        stock_code="600667",
    )

    assert len(results) > 0
    top_result = results[0]
    assert top_result.score > 0.0
    # 顶部检索切片必须切中审批风险或资产购买核心段落
    assert any(
        kw in top_result.chunk.text
        for kw in ["审批风险", "购买资产", "不确定性", "交易方案", "重组"]
    )

    # 将检索结果转换为供 Agent 推理阅读的结构化上下文 Prompt
    formatted_context = kb.format_context(results)
    assert "【相关金融知识库上下文参考】" in formatted_context
    assert "600667" in formatted_context
    assert "来源:" in formatted_context


# ---------------------------------------------------------------------------
# 测试用例 2: ToolRegistry 工具系统深度集成测试
# ---------------------------------------------------------------------------

def test_e2e_tool_registry_financial_knowledge_integration(populated_rag_kb):
    """验证 FinancialKnowledgeTool 与 ToolRegistry 的无缝挂载、Schema 导出与集中调度"""
    kb = populated_rag_kb
    registry = ToolRegistry()

    # 方式一：实例化工具后直接调用 registry.register
    knowledge_tool = FinancialKnowledgeTool(kb=kb)
    registry.register(knowledge_tool)

    # 验证工具在注册中心正常索引
    retrieved_tool = registry.get("search_financial_knowledge")
    assert retrieved_tool is not None
    assert retrieved_tool.name == "search_financial_knowledge"

    # 验证导出 OpenAI 标准 Function Calling JSON Schema
    schemas = registry.get_schemas()
    assert len(schemas) == 1
    func_def = schemas[0]["function"]
    assert func_def["name"] == "search_financial_knowledge"
    assert "query" in func_def["parameters"]["properties"]
    assert "stock_code" in func_def["parameters"]["properties"]
    assert "top_k" in func_def["parameters"]["properties"]
    assert "query" in func_def["parameters"]["required"]

    # 通过 ToolRegistry 集中调度执行知识库检索
    result: ToolResult = registry.execute(
        "search_financial_knowledge",
        query="主力又在做慈善了，接着砸盘",
        top_k=2,
    )
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "主力又送钱了" in result.output
    assert "赌气反讽" in result.output

    # 方式二：使用 ToolRegistry 提供的便捷注册方法 register_financial_knowledge
    another_registry = ToolRegistry()
    registered_tool = another_registry.register_financial_knowledge(kb=kb)
    assert registered_tool.name == "search_financial_knowledge"
    assert another_registry.get("search_financial_knowledge") is not None

    res2 = another_registry.execute(
        "search_financial_knowledge",
        query="关灯吃面极度亏损",
    )
    assert res2.success is True
    assert "关灯吃面" in res2.output


def test_e2e_global_tool_registry_financial_knowledge_compatibility():
    """测试全局默认注册中心 global_tool_registry 对 FinancialKnowledgeTool 的扩展能力"""
    # 验证可向全局注册中心便捷注入金融知识检索工具
    tool = global_tool_registry.register_financial_knowledge()
    assert global_tool_registry.get("search_financial_knowledge") is not None
    assert tool.name == "search_financial_knowledge"

    # 确保已有基础工具不受影响
    assert global_tool_registry.get("stock_scraper") is not None
    assert global_tool_registry.get("market_data") is not None
    assert global_tool_registry.get("sentiment_analyzer") is not None

    # 执行全局调用验证默认知识库回退正常
    exec_result: ToolResult = global_tool_registry.execute(
        "search_financial_knowledge",
        query="利好出尽 见光死",
        top_k=1,
    )
    assert exec_result.success is True
    assert len(exec_result.output) > 0


# ---------------------------------------------------------------------------
# 测试用例 3: A 股散户极端情绪与反讽黑话消歧场景
# ---------------------------------------------------------------------------

def test_e2e_sentiment_and_sarcasm_retrieval_scenario(populated_rag_kb):
    """端到端验证散户反讽隐喻识别场景（表面正面赞赏，深层破防看空）"""
    kb = populated_rag_kb
    tool = FinancialKnowledgeTool(kb=kb)

    # 场景 1：散户极端破防发帖：“主力真是大善人，又给我们送钱了，明天接着跌停！”
    sarcasm_post = "主力真是大善人，又给我们送钱了，明天接着跌停！"
    result = tool.execute(query=sarcasm_post, top_k=2)

    assert result.success is True
    output = result.output
    # 必须精准检索出反讽黑话条目“主力又送钱了”
    assert "主力又送钱了" in output
    assert "赌气反讽" in output
    assert "真实立场极度看空" in output

    # 场景 2：散户暴亏发帖：“今天账户又爆仓了，准备晚上关灯吃面了”
    despair_post = "今天账户又爆仓了，准备晚上关灯吃面了"
    res_despair = tool.execute(query=despair_post, top_k=1)
    assert res_despair.success is True
    assert "关灯吃面" in res_despair.output
    assert "极度恐慌" in res_despair.output

    # 场景 3：行情反弹初期的诱多发帖：“牛回速归，兄弟们满仓干”
    bull_trap_post = "牛回速归，兄弟们满仓干"
    res_bull = tool.execute(query=bull_trap_post, top_k=1)
    assert res_bull.success is True
    assert "牛回速归" in res_bull.output
    assert "诱多陷阱" in res_bull.output


# ---------------------------------------------------------------------------
# 测试用例 4: 突发公告 vs 历史研报的时间衰减与股票代码过滤
# ---------------------------------------------------------------------------

def test_e2e_time_decay_with_breaking_news_vs_historical_report(populated_rag_kb):
    """时间衰减动态排序与多维度股票代码隔离测试"""
    kb = populated_rag_kb

    # 查询共有关键词“先进封装”或“太极实业”
    # 公告为 30分钟前发布，研报为 60 天前发布，两者均匹配，时间衰减使新鲜突发公告保持优势
    results = kb.retrieve(query="太极实业 半导体", top_k=4, stock_code="600667")
    assert len(results) >= 2

    # 验证排名前列的切片包含来自重组公告的内容
    announcement_hits = [r for r in results if r.chunk.doc_id == "ann_600667_088"]
    assert len(announcement_hits) > 0
    # 突发公告的时间衰减惩罚几乎为 1.0 (仅半小时前)，得分保持高位
    assert announcement_hits[0].score > 0.01

    # 验证股票代码隔离：查询不存在代码或其它代码时安全过滤
    filtered_results = kb.retrieve(query="半导体 资产重组", stock_code="000001")
    # 库中仅有 600667 的标的文档和通用黑话 (stock_code=None)
    # 因此过滤 000001 时绝对不能返回 600667 的专属文档切片
    for r in filtered_results:
        assert r.chunk.stock_code != "600667"


# ---------------------------------------------------------------------------
# 测试用例 5: 边界异常与稳健性容错测试
# ---------------------------------------------------------------------------

def test_e2e_rag_edge_cases_and_robustness(empty_kb):
    """极端输入与边界防御测试：空文本、超长无意义字符串、空检索结果"""
    kb = empty_kb
    tool = FinancialKnowledgeTool(kb=kb)

    # 1. 空查询自愈处理
    res_empty = tool.execute(query="   ")
    assert res_empty.success is True
    assert "未检索到" in res_empty.output

    # 2. 空知识库无匹配
    res_none = tool.execute(query="量子纠缠与宏观调控关系")
    assert res_none.success is True
    assert "未检索到" in res_none.output

    # 3. 超长无意义随机字符串
    nonsense_query = "xyzqwk" * 100
    results = kb.retrieve(query=nonsense_query, top_k=5)
    # 应稳定返回空或低分候选列表，绝不崩溃
    assert isinstance(results, list)

    # 4. 格式化空结果
    empty_context = kb.format_context([])
    assert "暂无相关知识切片参考" in empty_context
