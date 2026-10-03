"""金融垂直领域 RAG 双路混合检索引擎模块

融合稠密向量余弦检索与 BM25 稀疏关键词检索，基于 RRF (Reciprocal Rank Fusion)
倒数排名融合算法与半衰期时间衰减机制，为金融智能体提供高精度、具备时间敏感性的知识召回底座。
"""

import time
from typing import Dict, List, Optional

from src.knowledge.chunker import FinancialChunker
from src.knowledge.embeddings import BaseEmbedding, DeterministicHashEmbedding
from src.knowledge.schema import Chunk, Document, KnowledgeType, RetrievalResult
from src.knowledge.sparse_retriever import BM25Retriever
from src.knowledge.vector_store import InMemoryVectorStore


class FinancialRAGKnowledgeBase:
    """
    金融垂直领域双路 RAG 混合检索知识库
    内置向量模型与 BM25 稀疏索引，支持多格式文档摄入、结构化金融术语录入、
    RRF 多路召回融合、指数级时间衰减及元数据过滤。
    """

    def __init__(
        self,
        embedding_model: Optional[BaseEmbedding] = None,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
    ):
        """初始化金融混合检索知识库

        参数:
            embedding_model: 向量嵌入模型实例，默认使用 DeterministicHashEmbedding()
            chunk_size: 智能切片目标字符大小，默认 300
            chunk_overlap: 切片滑动窗口重叠字符大小，默认 50
        """
        self.embedding_model = embedding_model or DeterministicHashEmbedding()
        self.chunker = FinancialChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store = InMemoryVectorStore(embedding_model=self.embedding_model)
        self.sparse_retriever = BM25Retriever()
        self._documents: Dict[str, Document] = {}

    def add_document(self, doc: Document) -> List[Chunk]:
        """向知识库摄入完整文档，自动完成智能切片、向量编码与双路索引构建

        参数:
            doc: 待摄入的文档实体

        返回:
            生成的知识切片 Chunk 列表
        """
        self._documents[doc.doc_id] = doc
        chunks = self.chunker.split(doc)
        if chunks:
            self.vector_store.add_chunks(chunks)
            self.sparse_retriever.add_chunks(chunks)
        return chunks

    def add_knowledge_item(
        self,
        term: str,
        category: str,
        definition: str,
        sentiment_bias: float = 0.0,
        stock_code: Optional[str] = None,
    ) -> List[Chunk]:
        """录入金融行业专有术语、情绪黑话或规则条目

        参数:
            term: 术语/黑话关键词（例如 "关灯吃面"）
            category: 类别标签（例如 "情绪黑话"、"财务造假"、"量化规则"）
            definition: 详细概念定义或行为释义
            sentiment_bias: 情绪倾向性分值 (-1.0 ~ 1.0)
            stock_code: 关联股票代码，可选

        返回:
            生成的切片 Chunk 列表
        """
        doc_id = f"item_{term}_{int(time.time() * 1000)}"
        doc = Document(
            doc_id=doc_id,
            title=f"[{category}] {term}",
            content=f"{term}（{category}）：{definition}",
            doc_type=KnowledgeType.TERM,
            stock_code=stock_code,
            metadata={
                "category": category,
                "sentiment_bias": sentiment_bias,
                "term": term,
            },
        )
        return self.add_document(doc)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        stock_code: Optional[str] = None,
        decay_half_life_days: Optional[float] = 30.0,
    ) -> List[RetrievalResult]:
        """执行稠密向量与 BM25 稀疏双路召回，通过 RRF 与时间衰减完成混合排序

        参数:
            query: 用户或智能体查询语句
            top_k: 返回的最佳匹配结果数量，默认 3
            stock_code: 股票代码元数据过滤条件，可选
            decay_half_life_days: 指数衰减半衰期天数，默认 30 天，传入 None 则关闭衰减

        返回:
            按综合得分降序排列的 RetrievalResult 列表
        """
        query_text = query.strip()
        if not query_text or top_k <= 0 or self.total_chunks == 0:
            return []

        # 双路召回扩展候选池
        candidate_limit = max(top_k * 4, 20)
        dense_hits = self.vector_store.similarity_search_by_text(
            query=query_text, top_k=candidate_limit, stock_code=stock_code
        )
        sparse_hits = self.sparse_retriever.search(
            query=query_text, top_k=candidate_limit, stock_code=stock_code
        )

        if not dense_hits and not sparse_hits:
            return []

        # RRF (Reciprocal Rank Fusion) 倒数排名融合计算与量纲归一化
        # 各候选列表单路理论最大得分为 1.0 / (rrf_constant + 1.0)
        # 将各路候选列表分数对齐归一化到 [0, 1] 量纲，再加权融合至 [0, 1] 综合相关度量纲
        rrf_constant = 60.0
        max_single_rrf = 1.0 / (rrf_constant + 1.0)
        num_channels = 2.0  # 双路检索（Dense 向量通道 + Sparse 关键词通道）

        chunk_map: Dict[str, Chunk] = {}
        dense_ranks: Dict[str, int] = {}
        sparse_ranks: Dict[str, int] = {}
        dense_norm_scores: Dict[str, float] = {}
        sparse_norm_scores: Dict[str, float] = {}

        for rank, (chunk, _) in enumerate(dense_hits, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            dense_ranks[cid] = rank
            raw_rrf = 1.0 / (rrf_constant + rank)
            dense_norm_scores[cid] = raw_rrf / max_single_rrf

        for rank, (chunk, _) in enumerate(sparse_hits, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            sparse_ranks[cid] = rank
            raw_rrf = 1.0 / (rrf_constant + rank)
            sparse_norm_scores[cid] = raw_rrf / max_single_rrf

        # 统一量纲融合：双路协同命中得分显著高于单路，且最终分值严格收敛在 [0.0, 1.0]
        all_cids = set(dense_norm_scores.keys()) | set(sparse_norm_scores.keys())
        rrf_scores: Dict[str, float] = {}
        for cid in all_cids:
            s_dense = dense_norm_scores.get(cid, 0.0)
            s_sparse = sparse_norm_scores.get(cid, 0.0)
            rrf_scores[cid] = (s_dense + s_sparse) / num_channels

        # 时间衰减与结果封装
        now_ts = time.time()
        scored_candidates: List[RetrievalResult] = []

        for cid, raw_score in rrf_scores.items():
            chunk = chunk_map[cid]
            decay_factor = 1.0

            # 对具有历史发布时间戳的切片应用半衰期指数衰减
            if (
                decay_half_life_days is not None
                and decay_half_life_days > 0
                and chunk.publish_timestamp is not None
                and chunk.publish_timestamp <= now_ts
            ):
                age_days = (now_ts - chunk.publish_timestamp) / 86400.0
                if age_days > 0:
                    decay_factor = 0.5 ** (age_days / decay_half_life_days)

            final_score = raw_score * decay_factor

            # 标记召回通道来源
            in_dense = cid in dense_ranks
            in_sparse = cid in sparse_ranks
            if in_dense and in_sparse:
                source = "hybrid"
            elif in_dense:
                source = "dense"
            else:
                source = "sparse"

            scored_candidates.append(
                RetrievalResult(
                    chunk=chunk,
                    score=round(final_score, 6),
                    source_type=source,
                )
            )

        # 按最终得分降序排序并截断 top_k
        scored_candidates.sort(key=lambda r: r.score, reverse=True)
        return scored_candidates[:top_k]

    def format_context(self, results: List[RetrievalResult]) -> str:
        """将检索命中的知识切片格式化为结构化 LLM 提示词上下文

        参数:
            results: 检索结果列表

        返回:
            格式化上下文文本字符串
        """
        if not results:
            return "【相关上下文】：暂无相关知识切片参考。"

        formatted_lines = ["【相关金融知识库上下文参考】："]
        for idx, item in enumerate(results, start=1):
            chunk = item.chunk
            stock_info = f" [股票代码: {chunk.stock_code}]" if chunk.stock_code else ""
            time_info = ""
            if chunk.publish_timestamp:
                try:
                    time_str = time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(chunk.publish_timestamp)
                    )
                    time_info = f" [发布时间: {time_str}]"
                except Exception:
                    pass

            meta_header = (
                f"[{idx}] [来源: {item.source_type} | 相关度得分: {item.score:.4f}]"
                f"{stock_info}{time_info}"
            )
            formatted_lines.append(f"{meta_header}\n{chunk.text.strip()}\n")

        return "\n".join(formatted_lines).strip()

    def clear(self) -> None:
        """清空知识库全部文档、切片及双路索引"""
        self._documents.clear()
        self.vector_store.clear()
        self.sparse_retriever.clear()

    @property
    def total_documents(self) -> int:
        """获取当前摄入的文档总数"""
        return len(self._documents)

    @property
    def total_chunks(self) -> int:
        """获取当前索引库中的知识切片总数"""
        return self.vector_store.total_chunks
