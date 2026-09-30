"""金融知识库核心 Schema 单元测试"""

from src.knowledge.schema import KnowledgeType, Document, Chunk, RetrievalResult


def test_document_creation_and_validation():
    """测试原始文档实体的创建与字段校验"""
    doc = Document(
        doc_id="doc_001",
        title="测试研报",
        content="公司业绩大幅超预期，主升浪已现。",
        doc_type=KnowledgeType.REPORT,
        stock_code="600584",
        publish_time="2026-09-23 10:00:00",
        metadata={"author": "分析师A"}
    )
    assert doc.doc_id == "doc_001"
    assert doc.title == "测试研报"
    assert doc.content == "公司业绩大幅超预期，主升浪已现。"
    assert doc.doc_type == KnowledgeType.REPORT
    assert doc.stock_code == "600584"
    assert doc.publish_time == "2026-09-23 10:00:00"
    assert doc.metadata["author"] == "分析师A"
    assert doc.created_at > 0


def test_chunk_and_retrieval_result():
    """测试知识切片与检索结果实体的创建与校验"""
    chunk = Chunk(
        chunk_id="chunk_001",
        doc_id="doc_001",
        text="主升浪已现",
        chunk_index=0,
        stock_code="600584",
        metadata={"category": "多头黑话"}
    )
    assert chunk.chunk_id == "chunk_001"
    assert chunk.doc_id == "doc_001"
    assert chunk.text == "主升浪已现"
    assert chunk.chunk_index == 0
    assert chunk.stock_code == "600584"
    assert chunk.metadata == {"category": "多头黑话"}
    assert chunk.vector is None

    result = RetrievalResult(chunk=chunk, score=0.92, source_type="hybrid")
    assert result.score == 0.92
    assert result.chunk.chunk_id == "chunk_001"
    assert result.source_type == "hybrid"


def test_knowledge_type_enum():
    """测试知识类型枚举"""
    assert KnowledgeType.TERM.value == "term"
    assert KnowledgeType.ANNOUNCEMENT.value == "announcement"
    assert KnowledgeType.REPORT.value == "report"
    assert KnowledgeType.DISCLOSURE.value == "disclosure"
    assert KnowledgeType.RULE.value == "rule"
