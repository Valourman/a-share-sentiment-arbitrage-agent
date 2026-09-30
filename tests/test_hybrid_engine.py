"""针对双路 RRF 混合检索引擎与金融知识库的单元测试"""

import time
from src.knowledge.embeddings import DeterministicHashEmbedding
from src.knowledge.schema import Document, KnowledgeType
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase


def test_hybrid_engine_add_and_counts():
    """测试知识库添加文档与单条结构化知识项，以及切片总量与文档总量计数"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model, chunk_size=100, chunk_overlap=20)

    assert kb.total_documents == 0
    assert kb.total_chunks == 0

    # 1. 添加完整文档
    doc1 = Document(
        doc_id="doc_report_1",
        title="贵州茅台深度研究报告",
        content="贵州茅台发布最新经营数据，高端白酒批价保持平稳，直销渠道占比持续提升。\n\n公司稳健推进扩产计划，长期护城河深厚。",
        doc_type=KnowledgeType.REPORT,
        stock_code="600519",
        publish_time="2026-03-01 10:00:00",
    )
    chunks1 = kb.add_document(doc1)
    assert len(chunks1) >= 1
    assert kb.total_documents == 1
    assert kb.total_chunks == len(chunks1)

    # 2. 添加单条金融术语知识项
    kb.add_knowledge_item(
        term="关灯吃面",
        category="情绪黑话",
        definition="股民散户在遭遇市场剧烈下跌或暴跌套牢后无可奈何的悲伤自我调侃。",
        sentiment_bias=-0.8,
        stock_code=None,
    )
    assert kb.total_documents == 2
    assert kb.total_chunks >= 2


def test_hybrid_retrieval_and_rrf_fusion():
    """测试双路密集向量 + 稀疏 BM25 检索以及 RRF 倒数排名融合"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model, chunk_size=200, chunk_overlap=30)

    # 录入具有特定关键词与语义特征的文档
    doc_a = Document(
        doc_id="doc_a",
        title="新能源车电池技术研报",
        content="宁德时代发布超级快充电池神行Plus，磷酸铁锂突破千公里续航，全产业链技术壁垒深厚。",
        stock_code="300750",
    )
    doc_b = Document(
        doc_id="doc_b",
        title="白酒批价动态简报",
        content="飞天茅台批价回暖，终端动销稳步恢复，经销商打款积极性保持高位。",
        stock_code="600519",
    )
    doc_c = Document(
        doc_id="doc_c",
        title="半导体芯片公告",
        content="中芯国际发布资本开支扩充公告，加速推进成熟制程晶圆代工产能扩张。",
        stock_code="688981",
    )

    kb.add_document(doc_a)
    kb.add_document(doc_b)
    kb.add_document(doc_c)

    # 检索关键词 "宁德时代 快充电池"
    results = kb.retrieve(query="宁德时代 快充电池", top_k=2)

    assert len(results) > 0
    top_result = results[0]
    # 验证命中宁德时代相关切片
    assert top_result.chunk.stock_code == "300750"
    assert top_result.score > 0.0
    # 验证召回来源标记为 hybrid/dense/sparse
    assert top_result.source_type in {"hybrid", "dense", "sparse"}


def test_time_decay_mechanism():
    """测试时间衰减机制：相同/相似内容的新近文档得分高于历史陈旧文档"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model, chunk_size=200, chunk_overlap=30)

    now_ts = time.time()
    # 60 天前的历史时间戳
    old_ts = now_ts - (60 * 86400)
    old_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(old_ts))
    fresh_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts - 3600))

    # 添加一篇历史陈旧的突发公告
    old_doc = Document(
        doc_id="doc_old_alert",
        title="重要立案调查公告（历史）",
        content="某上市公司因涉嫌信息披露违法违规收到中国证监会立案告知书，敬请广大投资者防范风险。",
        stock_code="000001",
        publish_time=old_time_str,
    )
    # 添加一篇最新的突发公告
    fresh_doc = Document(
        doc_id="doc_fresh_alert",
        title="重要立案调查公告（最新）",
        content="某上市公司因涉嫌信息披露违法违规收到中国证监会立案告知书，敬请广大投资者防范风险。",
        stock_code="000002",
        publish_time=fresh_time_str,
    )

    kb.add_document(old_doc)
    kb.add_document(fresh_doc)

    # 1. 开启半衰期衰减 (半衰期 30 天，60 天前文档衰减因子约为 0.25)
    results_with_decay = kb.retrieve(
        query="涉嫌信息披露违法违规 立案调查",
        top_k=2,
        decay_half_life_days=30.0,
    )

    assert len(results_with_decay) == 2
    # 最新发布的文档得分应明显高于历史陈旧文档
    assert results_with_decay[0].chunk.doc_id == "doc_fresh_alert"
    assert results_with_decay[1].chunk.doc_id == "doc_old_alert"
    assert results_with_decay[0].score > results_with_decay[1].score

    # 2. 关闭时间衰减 (decay_half_life_days=None)
    results_no_decay = kb.retrieve(
        query="涉嫌信息披露违法违规 立案调查",
        top_k=2,
        decay_half_life_days=None,
    )
    assert len(results_no_decay) == 2
    # 关闭衰减时，由于文本内容完全相同，两者的得分差异仅来源于 RRF 并列名次位移 (< 0.001)
    diff = abs(results_no_decay[0].score - results_no_decay[1].score)
    assert diff < 1e-3
    # 相比之下，开启时间衰减时新鲜文档得分应为陈旧文档的数倍 (60天衰减后约为 3~4 倍)
    assert results_with_decay[0].score > results_with_decay[1].score * 3.0


def test_stock_code_filtering():
    """测试按股票代码进行精准元数据检索过滤"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model)

    doc_600519 = Document(
        doc_id="doc_moutai",
        title="白酒行业龙头报告",
        content="行业深度景气，业绩高弹性增长，现金流充沛稳定。",
        stock_code="600519",
    )
    doc_000858 = Document(
        doc_id="doc_wuliangye",
        title="白酒行业次席报告",
        content="行业深度景气，业绩高弹性增长，现金流充沛稳定。",
        stock_code="000858",
    )

    kb.add_document(doc_600519)
    kb.add_document(doc_000858)

    # 指定 stock_code="600519" 检索
    results = kb.retrieve(query="业绩高弹性增长", top_k=5, stock_code="600519")

    assert len(results) > 0
    for r in results:
        assert r.chunk.stock_code == "600519"


def test_format_context():
    """测试将检索切片结果格式化为 LLM 上下文 prompt 文本"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model)

    doc = Document(
        doc_id="doc_1",
        title="研报摘要",
        content="净利润同比增长45%，超市场一致预期。",
        stock_code="600667",
        publish_time="2026-03-15 14:00:00",
    )
    kb.add_document(doc)

    results = kb.retrieve(query="净利润同比增长", top_k=1)
    context_str = kb.format_context(results)

    assert "600667" in context_str
    assert "净利润同比增长45%" in context_str
    assert "相关度得分" in context_str or "得分" in context_str or "切片" in context_str

    # 测试空结果格式化
    empty_context = kb.format_context([])
    assert "暂无" in empty_context or len(empty_context.strip()) > 0


def test_edge_cases_and_clear():
    """测试边界情况：空库、空查询、top_k<=0 以及 clear 清空操作"""
    embedding_model = DeterministicHashEmbedding(dimension=32)
    kb = FinancialRAGKnowledgeBase(embedding_model=embedding_model)

    # 1. 空库检索
    assert kb.retrieve("行情趋势") == []

    # 2. 添加文档后进行空文本或纯空白字符检索
    doc = Document(doc_id="d1", title="行情分析", content="今日大盘缩量震荡整理。")
    kb.add_document(doc)

    assert kb.retrieve("") == []
    assert kb.retrieve("   \n\t  ") == []
    assert kb.retrieve("行情", top_k=0) == []

    # 3. 清空知识库
    assert kb.total_documents == 1
    assert kb.total_chunks >= 1
    kb.clear()
    assert kb.total_documents == 0
    assert kb.total_chunks == 0
    assert kb.retrieve("行情") == []
