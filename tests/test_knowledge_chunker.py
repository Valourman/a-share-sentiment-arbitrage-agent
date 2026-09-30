"""金融文本结构化分块器单元测试"""

import time
from src.knowledge.schema import Document, KnowledgeType
from src.knowledge.chunker import FinancialChunker


def test_chunker_short_text():
    """测试短文本（长度小于等于 chunk_size）不切分直接返回单个切片"""
    doc = Document(
        doc_id="doc_short",
        title="简短术语",
        content="天地板是指从涨停跌停，主力诱多出货。",
        doc_type=KnowledgeType.TERM,
        stock_code="600667",
        metadata={"author": "分析师A"}
    )
    chunker = FinancialChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.split(doc)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc_short_0"
    assert chunks[0].doc_id == "doc_short"
    assert chunks[0].text == doc.content
    assert chunks[0].chunk_index == 0
    assert chunks[0].stock_code == "600667"
    assert chunks[0].metadata == {"author": "分析师A"}


def test_chunker_empty_content():
    """测试空文本输入返回空切片列表"""
    doc = Document(
        doc_id="doc_empty",
        title="空文档",
        content="   \n\n  ",
        doc_type=KnowledgeType.REPORT
    )
    chunker = FinancialChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.split(doc)
    assert chunks == []


def test_chunker_long_text_overlap():
    """测试长篇研报按段落分块与滑动窗口重叠机制"""
    paragraphs = [f"第{i}段：关注主力资金流向，大单净流入显著。" for i in range(12)]
    long_content = "\n\n".join(paragraphs)
    doc = Document(
        doc_id="doc_long",
        title="长篇研报",
        content=long_content,
        doc_type=KnowledgeType.REPORT,
        stock_code="600584"
    )
    chunker = FinancialChunker(chunk_size=60, chunk_overlap=15)
    chunks = chunker.split(doc)

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_id == f"doc_long_{idx}"
        assert c.doc_id == "doc_long"
        assert c.chunk_index == idx
        assert c.stock_code == "600584"
        assert len(c.text) > 0


def test_chunker_metadata_and_timestamp_inheritance():
    """测试发布时间戳解析与元数据完整继承"""
    publish_str = "2026-09-23 10:30:00"
    expected_ts = time.mktime(time.strptime(publish_str, "%Y-%m-%d %H:%M:%S"))

    doc = Document(
        doc_id="doc_meta",
        title="研报元数据测试",
        content="第一段核心观点：业绩高增超预期。\n\n第二段估值分析：给予买入评级，目标价翻倍。\n\n第三段风险提示：宏观经济下行风险。",
        doc_type=KnowledgeType.REPORT,
        stock_code="000001",
        publish_time=publish_str,
        metadata={"source": "东方财富", "level": "深度"}
    )
    chunker = FinancialChunker(chunk_size=40, chunk_overlap=10)
    chunks = chunker.split(doc)

    assert len(chunks) >= 2
    for c in chunks:
        assert c.stock_code == "000001"
        assert c.publish_timestamp == expected_ts
        assert c.metadata == {"source": "东方财富", "level": "深度"}


def test_chunker_fallback_timestamp():
    """测试无显式 publish_time 时回退到 created_at"""
    doc = Document(
        doc_id="doc_no_ts",
        title="无时间研报",
        content="主力资金净流入突破十亿。",
        doc_type=KnowledgeType.REPORT
    )
    chunker = FinancialChunker()
    chunks = chunker.split(doc)
    assert len(chunks) == 1
    assert chunks[0].publish_timestamp == doc.created_at
