"""内存向量存储与相似度计算模块"""

import math
from typing import List, Optional, Tuple

from src.knowledge.embeddings import BaseEmbedding
from src.knowledge.schema import Chunk


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """计算两个浮点向量之间的余弦相似度

    参数:
        v1: 第一个向量
        v2: 第二个向量

    返回:
        余弦相似度得分 (-1.0 ~ 1.0)，异常或零向量时安全返回 0.0
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class InMemoryVectorStore:
    """
    内存稠密向量存储库
    支持高效余弦距离检索、股票代码精确元数据过滤与批量切片自动补全索引
    """

    def __init__(self, embedding_model: BaseEmbedding):
        """初始化内存向量存储库

        参数:
            embedding_model: 向量嵌入模型实例
        """
        self.embedding_model = embedding_model
        self._chunks: List[Chunk] = []

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """追加切片并自动补全缺失的向量表示

        参数:
            chunks: 切片对象列表
        """
        for chunk in chunks:
            if chunk.vector is None:
                chunk.vector = self.embedding_model.embed_query(chunk.text)
            self._chunks.append(chunk)

    def similarity_search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        stock_code: Optional[str] = None,
    ) -> List[Tuple[Chunk, float]]:
        """基于查询向量检索最相似的切片

        参数:
            query_vector: 查询特征向量
            top_k: 返回的最大匹配数量
            stock_code: 可选的股票代码过滤条件

        返回:
            (Chunk, score) 二元组列表，按相似度降序排列
        """
        candidates = self._chunks
        if stock_code is not None:
            candidates = [c for c in candidates if c.stock_code == stock_code]

        scored: List[Tuple[Chunk, float]] = []
        for c in candidates:
            if c.vector is not None:
                sim = cosine_similarity(query_vector, c.vector)
                scored.append((c, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def similarity_search_by_text(
        self,
        query: str,
        top_k: int = 5,
        stock_code: Optional[str] = None,
    ) -> List[Tuple[Chunk, float]]:
        """基于文本直接编码并检索最相似的切片

        参数:
            query: 查询文本字符串
            top_k: 返回的最大匹配数量
            stock_code: 可选的股票代码过滤条件

        返回:
            (Chunk, score) 二元组列表，按相似度降序排列
        """
        query_vec = self.embedding_model.embed_query(query)
        return self.similarity_search(query_vec, top_k=top_k, stock_code=stock_code)

    def clear(self) -> None:
        """清空向量库中所有存储的切片"""
        self._chunks.clear()

    @property
    def total_chunks(self) -> int:
        """当前存储库中的切片总量"""
        return len(self._chunks)
