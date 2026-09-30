"""针对 BM25 稀疏关键词检索器的单元测试"""

from src.knowledge.schema import Chunk
from src.knowledge import BM25Retriever


def test_bm25_exact_keyword_retrieval():
    """测试中文金融专有术语与黑话的精确关键词召回"""
    retriever = BM25Retriever()
    c1 = Chunk(chunk_id="c1", doc_id="d1", text="中芯国际发布重大重组公告，主力强烈看好", stock_code="688981")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="关灯吃面，今日跌幅超预期", stock_code="600667")
    c3 = Chunk(chunk_id="c3", doc_id="d3", text="天地板诱多陷阱出现，谨防踩踏", stock_code="600584")

    retriever.add_chunks([c1, c2, c3])
    results = retriever.search("天地板", top_k=2)

    assert len(results) > 0
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "c3"
    assert score > 0.0

    # 测试英文与数字股票代号匹配
    results_stock = retriever.search("688981", top_k=1)
    assert len(results_stock) == 1
    assert results_stock[0][0].chunk_id == "c1"


def test_bm25_stock_code_filter():
    """测试股票代码元数据过滤功能"""
    retriever = BM25Retriever()
    c1 = Chunk(chunk_id="c1", doc_id="d1", text="业绩大增超预期，净利润翻倍", stock_code="600667")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="业绩大增超预期，净利润翻倍", stock_code="600584")
    retriever.add_chunks([c1, c2])

    results = retriever.search("业绩", top_k=5, stock_code="600667")
    assert len(results) == 1
    assert results[0][0].stock_code == "600667"
    assert results[0][0].chunk_id == "c1"


def test_bm25_edge_cases():
    """测试各种边界输入条件：空索引、空查询、未登录词及空文本"""
    retriever = BM25Retriever()

    # 1. 空索引库检索
    assert retriever.search("量化交易") == []
    assert retriever.total_chunks == 0

    # 2. 添加包含空文本的切片
    empty_chunk = Chunk(chunk_id="c_empty", doc_id="d_empty", text="", stock_code="000001")
    normal_chunk = Chunk(chunk_id="c_normal", doc_id="d_normal", text="北向资金净流入50亿", stock_code="000002")
    retriever.add_chunks([empty_chunk, normal_chunk])
    assert retriever.total_chunks == 2

    # 3. 空查询与空白字符查询
    assert retriever.search("") == []
    assert retriever.search("   \n\t  ") == []
    assert retriever.search("!@#$%^&*()") == []

    # 4. 未登录词检索（完全不匹配）
    assert retriever.search("美联储加息降息周期") == []

    # 5. 命中正常切片
    hit = retriever.search("北向资金", top_k=1)
    assert len(hit) == 1
    assert hit[0][0].chunk_id == "c_normal"


def test_bm25_clear_and_total_chunks():
    """测试切片计数属性与清空重置逻辑"""
    retriever = BM25Retriever()
    c1 = Chunk(chunk_id="c1", doc_id="d1", text="游资接力涨停")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="机构高位出货")

    retriever.add_chunks([c1])
    assert retriever.total_chunks == 1
    retriever.add_chunks([c2])
    assert retriever.total_chunks == 2

    retriever.clear()
    assert retriever.total_chunks == 0
    assert retriever.search("涨停") == []
