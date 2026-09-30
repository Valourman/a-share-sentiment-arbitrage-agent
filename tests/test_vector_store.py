"""向量嵌入与内存向量数据库单元测试"""

from src.knowledge.schema import Chunk
from src.knowledge.embeddings import DeterministicHashEmbedding
from src.knowledge.vector_store import (
    InMemoryVectorStore,
    cosine_similarity,
)


def test_cosine_similarity_edge_cases():
    """测试余弦相似度边界条件：空向量、维度不一致、全零向量"""
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0, 0.0], []) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    # 正常正交与平行向量
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0]) - 0.0) < 1e-6
    assert abs(cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6
    assert abs(cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-6


def test_deterministic_hash_embedding():
    """测试确定性局部哈希向量生成器的确定性、维度与归一化"""
    embedder = DeterministicHashEmbedding(dimension=32)

    # 确定性
    v1 = embedder.embed_query("主力资金大幅流入")
    v2 = embedder.embed_query("主力资金大幅流入")
    assert v1 == v2
    assert len(v1) == 32

    # L2 归一化模长应接近 1.0
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-5

    # 空文本处理
    v_empty = embedder.embed_query("")
    assert len(v_empty) == 32
    assert all(x == 0.0 for x in v_empty)

    # 批量处理与别名支持
    batch_vecs = embedder.embed_documents(["主力资金大幅流入", "散户追高"])
    assert len(batch_vecs) == 2
    assert batch_vecs[0] == v1

    # embed_text / embed_batch 别名验证
    assert embedder.embed_text("主力资金大幅流入") == v1
    assert embedder.embed_batch(["主力资金大幅流入"]) == [v1]


def test_vector_store_indexing_and_search():
    """测试内存向量存储的索引构建、向量补充与相似度检索"""
    embedder = DeterministicHashEmbedding(dimension=32)
    store = InMemoryVectorStore(embedding_model=embedder)

    v1 = embedder.embed_query("主力资金大幅流入")

    chunk1 = Chunk(chunk_id="c1", doc_id="d1", text="主力资金大幅流入", vector=v1, stock_code="600667")
    # chunk2 不预先传入 vector，验证 store 是否能自动生成
    chunk2 = Chunk(chunk_id="c2", doc_id="d2", text="散户恐慌抛售割肉", vector=None, stock_code="600584")

    store.add_chunks([chunk1, chunk2])
    assert store.total_chunks == 2
    assert chunk2.vector is not None
    assert len(chunk2.vector) == 32

    # 查询与 chunk1 语义完全一致的文本
    results = store.similarity_search_by_text("主力资金大幅流入", top_k=2)
    assert len(results) == 2
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "c1"
    assert score > 0.99

    # 清空测试
    store.clear()
    assert store.total_chunks == 0
    assert store.similarity_search_by_text("主力资金", top_k=2) == []


def test_vector_store_filtering():
    """测试带有股票代码过滤的相似度检索"""
    embedder = DeterministicHashEmbedding(dimension=32)
    store = InMemoryVectorStore(embedding_model=embedder)

    c1 = Chunk(chunk_id="c1", doc_id="d1", text="半导体芯片主升浪", stock_code="600584")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="光伏设备主升浪", stock_code="600667")
    c3 = Chunk(chunk_id="c3", doc_id="d3", text="通用机械主升浪", stock_code=None)

    store.add_chunks([c1, c2, c3])
    assert store.total_chunks == 3

    # 仅过滤 600584
    results = store.similarity_search_by_text("主升浪", top_k=5, stock_code="600584")
    assert len(results) == 1
    assert results[0][0].chunk_id == "c1"
    assert results[0][0].stock_code == "600584"

    # 过滤不存在的代码
    empty_res = store.similarity_search_by_text("主升浪", top_k=5, stock_code="999999")
    assert len(empty_res) == 0
