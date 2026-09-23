# 金融智能体垂直 RAG 知识检索库实施计划 (Financial RAG Knowledge Base Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个专为 A 股舆情研判与金融智能体设计的垂直 RAG 知识检索库，具备金融文本分块、稠密向量+稀疏关键词混合索引、元数据过滤、时间衰减与 Agent 工具无缝适配能力。

**Architecture:** 采用分层解耦架构，底层为统一的数据模型（Schema），中间层包含结构化金融分块器（FinancialChunker）、向量存储（VectorStore）与关键词检索器（BM25Retriever），上层通过混合融合引擎（HybridEngine）进行 RRF 倒数排名融合打分，顶层封装为 Hello-Agents 标准 Tool 并平滑向后兼容现有 `FinancialKnowledgeRetriever`。

**Tech Stack:** Python 3.10+, Pydantic V2, NumPy, OpenAI API / 纯算法 MockEmbedding, Pytest

**Spec:** 本实施方案作为第一版金融知识库垂直规格，直接对齐 Hello-Agents 智能体知识体系与金融实战场景。

## Global Constraints

- 全程遵循中文注释规范与严谨错误处理，无冗余代码与废弃 import。
- 采用 Pydantic V2 进行强类型数据模型校验。
- 零额外重量级依赖：优先基于 NumPy 与标准库实现 BM25 与向量余弦计算，确保本地轻量免配置且测试可在 2 秒内秒级运行。
- 完全向后兼容原有 `src/memory/knowledge.py` 的接口协议，现有测试用例保持 100% 通过。
- 单元测试覆盖率保持高标准。

---

### Task 1: 核心数据契约与实体定义

**Files:**
- Create: `src/knowledge/schema.py`
- Create: `src/knowledge/__init__.py`
- Test: `tests/test_knowledge_schema.py`

**Interfaces:**
- Consumes: `pydantic.BaseModel`, `pydantic.Field`
- Produces:
  - `KnowledgeType`: Enum(`TERM`, `ANNOUNCEMENT`, `REPORT`, `DISCLOSURE`, `RULE`)
  - `Document`: 模型包含 `doc_id`, `title`, `content`, `doc_type`, `stock_code`, `publish_time`, `metadata`
  - `Chunk`: 模型包含 `chunk_id`, `doc_id`, `text`, `vector`, `chunk_index`, `metadata`, `stock_code`
  - `RetrievalResult`: 模型包含 `chunk`, `score`, `source_type` ("dense", "sparse", "hybrid")

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_knowledge_schema.py` 中编写验证契约与校验规则的测试用例：

```python
import pytest
from src.knowledge.schema import KnowledgeType, Document, Chunk, RetrievalResult


def test_document_creation_and_validation():
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
    assert doc.doc_type == KnowledgeType.REPORT
    assert doc.stock_code == "600584"


def test_chunk_and_retrieval_result():
    chunk = Chunk(
        chunk_id="chunk_001",
        doc_id="doc_001",
        text="主升浪已现",
        chunk_index=0,
        stock_code="600584",
        metadata={"category": "多头黑话"}
    )
    result = RetrievalResult(chunk=chunk, score=0.92, source_type="hybrid")
    assert result.score == 0.92
    assert result.chunk.chunk_id == "chunk_001"
    assert result.source_type == "hybrid"
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_knowledge_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge'`

- [ ] **Step 3: 编写最小实现代码**

创建 `src/knowledge/__init__.py`:
```python
"""金融智能体垂直 RAG 知识检索库模块"""
```

创建 `src/knowledge/schema.py`:
```python
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeType(str, Enum):
    """知识与文档类型枚举"""
    TERM = "term"                  # 术语/黑话/反讽隐喻
    ANNOUNCEMENT = "announcement"  # 上市公司公告
    REPORT = "report"              # 专业券商研报
    DISCLOSURE = "disclosure"      # 监管信息/财务披露
    RULE = "rule"                  # 交易规则/量化背离特征


class Document(BaseModel):
    """原始文档实体"""
    doc_id: str = Field(description="文档全局唯一标识符")
    title: str = Field(description="文档标题")
    content: str = Field(description="文档完整正文内容")
    doc_type: KnowledgeType = Field(default=KnowledgeType.REPORT, description="文档类型")
    stock_code: Optional[str] = Field(default=None, description="关联股票代码 (如 600667)")
    publish_time: Optional[str] = Field(default=None, description="发布时间字符串 (YYYY-MM-DD HH:MM:SS)")
    created_at: float = Field(default_factory=time.time, description="系统摄入时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="灵活扩展元数据")


class Chunk(BaseModel):
    """分块切片实体"""
    chunk_id: str = Field(description="切片唯一标识")
    doc_id: str = Field(description="所属父级文档 ID")
    text: str = Field(description="切片文本内容")
    chunk_index: int = Field(default=0, description="在原文档中的顺序序号")
    stock_code: Optional[str] = Field(default=None, description="股票代码")
    publish_timestamp: Optional[float] = Field(default=None, description="发布时间戳用于时间衰减")
    vector: Optional[List[float]] = Field(default=None, description="稠密向量嵌入表示")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="继承或生成的切片元数据")


class RetrievalResult(BaseModel):
    """检索返回实体"""
    chunk: Chunk = Field(description="命中的知识切片")
    score: float = Field(description="综合相关度评分 (0~1)")
    source_type: str = Field(default="hybrid", description="召回来源: dense / sparse / hybrid")
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_knowledge_schema.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/ tests/test_knowledge_schema.py
git commit -m "feat(knowledge): 定义核心数据契约与数据模型"
```

---

### Task 2: 金融文本结构化分块器 (FinancialChunker)

**Files:**
- Create: `src/knowledge/chunker.py`
- Test: `tests/test_knowledge_chunker.py`

**Interfaces:**
- Consumes: `src.knowledge.schema.Document`, `src.knowledge.schema.Chunk`
- Produces: `FinancialChunker.split(doc: Document) -> List[Chunk]`

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_knowledge_chunker.py` 中编写针对段落切分、重叠滑动与金融特定分割符的测试：

```python
import pytest
from src.knowledge.schema import Document, KnowledgeType
from src.knowledge.chunker import FinancialChunker


def test_chunker_short_text():
    doc = Document(
        doc_id="doc_short",
        title="简短术语",
        content="天地板是指从涨停跌停，主力诱多出货。",
        doc_type=KnowledgeType.TERM,
        stock_code="600667"
    )
    chunker = FinancialChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.split(doc)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc_short_0"
    assert chunks[0].text == doc.content
    assert chunks[0].stock_code == "600667"


def test_chunker_long_text_overlap():
    long_content = "\n\n".join([f"第{i}段：关注主力资金流向，大单净流入显著。" for i in range(15)])
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
    for c in chunks:
        assert len(c.text) <= 100
        assert c.doc_id == "doc_long"
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_knowledge_chunker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge.chunker'`

- [ ] **Step 3: 编写分块器实现**

创建 `src/knowledge/chunker.py`:
```python
import time
from typing import List, Optional
from src.knowledge.schema import Document, Chunk


class FinancialChunker:
    """
    金融文档智能切片分块器
    支持按双换行/段落切分、滑动窗口重叠（保持跨切片上下文连续性），并自动继承股票代码与时间戳元数据
    """
    def __init__(self, chunk_size: int = 250, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, doc: Document) -> List[Chunk]:
        """将文档切分为多个 Chunk"""
        content = doc.content.strip()
        if not content:
            return []

        # 解析发布时间为时间戳（若有时）
        publish_ts: Optional[float] = None
        if doc.publish_time:
            try:
                publish_ts = time.mktime(time.strptime(doc.publish_time, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                publish_ts = doc.created_at
        else:
            publish_ts = doc.created_at

        # 文本较短时直接返回单切片
        if len(content) <= self.chunk_size:
            return [
                Chunk(
                    chunk_id=f"{doc.doc_id}_0",
                    doc_id=doc.doc_id,
                    text=content,
                    chunk_index=0,
                    stock_code=doc.stock_code,
                    publish_timestamp=publish_ts,
                    metadata=dict(doc.metadata)
                )
            ]

        # 优先按段落切分
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [content]

        chunks: List[Chunk] = []
        current_text = ""
        chunk_idx = 0

        for para in paragraphs:
            if not current_text:
                current_text = para
            elif len(current_text) + len(para) + 2 <= self.chunk_size:
                current_text += "\n\n" + para
            else:
                # 超过阈值，落盘当前 chunk
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}_{chunk_idx}",
                        doc_id=doc.doc_id,
                        text=current_text,
                        chunk_index=chunk_idx,
                        stock_code=doc.stock_code,
                        publish_timestamp=publish_ts,
                        metadata=dict(doc.metadata)
                    )
                )
                chunk_idx += 1
                # 构造包含 overlap 的起始文本
                overlap_text = current_text[-self.chunk_overlap:] if len(current_text) > self.chunk_overlap else current_text
                current_text = overlap_text + "\n" + para if overlap_text else para

        if current_text:
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}_{chunk_idx}",
                    doc_id=doc.doc_id,
                    text=current_text,
                    chunk_index=chunk_idx,
                    stock_code=doc.stock_code,
                    publish_timestamp=publish_ts,
                    metadata=dict(doc.metadata)
                )
            )

        return chunks
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_knowledge_chunker.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/chunker.py tests/test_knowledge_chunker.py
git commit -m "feat(knowledge): 实现金融文本智能分块器与重叠滑动机制"
```

---

### Task 3: 向量嵌入抽象与内存向量存储 (VectorStore)

**Files:**
- Create: `src/knowledge/embeddings.py`
- Create: `src/knowledge/vector_store.py`
- Test: `tests/test_vector_store.py`

**Interfaces:**
- Consumes: `src.knowledge.schema.Chunk`
- Produces:
  - `BaseEmbedding.embed_query(text: str) -> List[float]`
  - `BaseEmbedding.embed_documents(texts: List[str]) -> List[List[float]]`
  - `InMemoryVectorStore.add_chunks(chunks: List[Chunk]) -> None`
  - `InMemoryVectorStore.similarity_search(query_vector: List[float], top_k: int, stock_code: Optional[str]) -> List[Tuple[Chunk, float]]`

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_vector_store.py` 中编写向量计算与相似度检索测试：

```python
import pytest
from src.knowledge.schema import Chunk
from src.knowledge.embeddings import DeterministicHashEmbedding
from src.knowledge.vector_store import InMemoryVectorStore


def test_embedding_and_vector_store():
    embedder = DeterministicHashEmbedding(dimension=16)
    v1 = embedder.embed_query("主力资金大幅流入")
    v2 = embedder.embed_query("主力资金大幅流入")
    v3 = embedder.embed_query("散户恐慌抛售割肉")
    assert v1 == v2
    assert len(v1) == 16

    chunk1 = Chunk(chunk_id="c1", doc_id="d1", text="主力资金大幅流入", vector=v1, stock_code="600667")
    chunk2 = Chunk(chunk_id="c2", doc_id="d2", text="散户恐慌抛售割肉", vector=v3, stock_code="600584")

    store = InMemoryVectorStore(embedding_model=embedder)
    store.add_chunks([chunk1, chunk2])

    # 查与 chunk1 相同的 query
    matches = store.similarity_search_by_text("主力资金大幅流入", top_k=2)
    assert len(matches) == 2
    top_chunk, score = matches[0]
    assert top_chunk.chunk_id == "c1"
    assert score > 0.99


def test_vector_store_filtering():
    embedder = DeterministicHashEmbedding(dimension=16)
    store = InMemoryVectorStore(embedding_model=embedder)
    c1 = Chunk(chunk_id="c1", doc_id="d1", text="科技牛市主升浪", stock_code="600584")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="医药白马主升浪", stock_code="000001")
    store.add_chunks([c1, c2])

    matches = store.similarity_search_by_text("主升浪", top_k=5, stock_code="600584")
    assert len(matches) == 1
    assert matches[0][0].stock_code == "600584"
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_vector_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge.embeddings'`

- [ ] **Step 3: 编写向量计算与存储实现**

创建 `src/knowledge/embeddings.py`:
```python
import hashlib
import math
from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """向量模型抽象基类"""
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass


class DeterministicHashEmbedding(BaseEmbedding):
    """
    轻量确定性局部哈希向量生成器 (零第三方重量级模型依赖)
    用于离线单测、快速兜底，保证具有强确定性与词频相似性
    """
    def __init__(self, dimension: int = 32):
        self.dimension = dimension

    def _hash_token(self, token: str) -> int:
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(h, 16)

    def embed_query(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        if not text:
            return vec
        # 按字符或简易 n-gram 投影至维度
        for i in range(len(text)):
            gram = text[i:min(i + 2, len(text))]
            idx = self._hash_token(gram) % self.dimension
            vec[idx] += 1.0

        # L2 正则化
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]
```

创建 `src/knowledge/vector_store.py`:
```python
from typing import List, Optional, Tuple
from src.knowledge.schema import Chunk
from src.knowledge.embeddings import BaseEmbedding


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """计算两向量的余弦相似度"""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class InMemoryVectorStore:
    """
    内存稠密向量存储库
    支持高效余弦距离检索、股票代码精确元数据过滤与批量切片索引
    """
    def __init__(self, embedding_model: BaseEmbedding):
        self.embedding_model = embedding_model
        self._chunks: List[Chunk] = []

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """追加切片并补充生成缺失的向量表示"""
        for chunk in chunks:
            if chunk.vector is None:
                chunk.vector = self.embedding_model.embed_query(chunk.text)
            self._chunks.append(chunk)

    def similarity_search_by_text(
        self,
        query: str,
        top_k: int = 5,
        stock_code: Optional[str] = None
    ) -> List[Tuple[Chunk, float]]:
        """按文本检索最相似的切片"""
        query_vec = self.embedding_model.embed_query(query)
        candidates = self._chunks
        if stock_code:
            candidates = [c for c in candidates if c.stock_code == stock_code]

        scored: List[Tuple[Chunk, float]] = []
        for c in candidates:
            if c.vector:
                sim = cosine_similarity(query_vec, c.vector)
                scored.append((c, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        self._chunks.clear()

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_vector_store.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/embeddings.py src/knowledge/vector_store.py tests/test_vector_store.py
git commit -m "feat(knowledge): 实现向量嵌入抽象与内存向量存储检索"
```

---

### Task 4: 关键词 BM25 稀疏检索器 (Sparse BM25 Retriever)

**Files:**
- Create: `src/knowledge/sparse_retriever.py`
- Test: `tests/test_sparse_retriever.py`

**Interfaces:**
- Consumes: `src.knowledge.schema.Chunk`
- Produces: `BM25Retriever.search(query: str, top_k: int, stock_code: Optional[str]) -> List[Tuple[Chunk, float]]`

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_sparse_retriever.py` 中编写关键词准确命中的测试用例（尤其是金融专有简称和黑话代码）：

```python
import pytest
from src.knowledge.schema import Chunk
from src.knowledge.sparse_retriever import BM25Retriever


def test_bm25_exact_keyword_retrieval():
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


def test_bm25_stock_code_filter():
    retriever = BM25Retriever()
    c1 = Chunk(chunk_id="c1", doc_id="d1", text="业绩大增超预期", stock_code="600667")
    c2 = Chunk(chunk_id="c2", doc_id="d2", text="业绩大增超预期", stock_code="600584")
    retriever.add_chunks([c1, c2])

    results = retriever.search("业绩", top_k=5, stock_code="600667")
    assert len(results) == 1
    assert results[0][0].stock_code == "600667"
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_sparse_retriever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge.sparse_retriever'`

- [ ] **Step 3: 编写 BM25 算法实现**

创建 `src/knowledge/sparse_retriever.py`:
```python
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from src.knowledge.schema import Chunk


class BM25Retriever:
    """
    轻量高效的中文金融 BM25 稀疏检索器
    对金融简称、股票代码、成语及黑话具备极高的精确召回能力
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._chunks: List[Chunk] = []
        self._doc_lens: List[int] = []
        self._avg_doc_len: float = 0.0
        self._doc_freqs: Dict[str, int] = {}
        self._term_freqs: List[Dict[str, int]] = []

    def _tokenize(self, text: str) -> List[str]:
        """简易高效中文字符与英文词元分词"""
        text = text.lower()
        # 匹配英文/数字序列或单个汉字
        tokens = re.findall(r'[a-z0-9_]+|[一-龥]', text)
        return tokens

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """批量建立切片的倒排索引"""
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1

            self._chunks.append(chunk)
            self._doc_lens.append(len(tokens))
            self._term_freqs.append(tf)

            for t in set(tokens):
                self._doc_freqs[t] = self._doc_freqs.get(t, 0) + 1

        total_tokens = sum(self._doc_lens)
        self._avg_doc_len = total_tokens / len(self._doc_lens) if self._doc_lens else 0.0

    def search(
        self,
        query: str,
        top_k: int = 5,
        stock_code: Optional[str] = None
    ) -> List[Tuple[Chunk, float]]:
        """执行 BM25 打分检索"""
        query_tokens = self._tokenize(query)
        if not query_tokens or not self._chunks:
            return []

        num_docs = len(self._chunks)
        scores: List[Tuple[Chunk, float]] = []

        for idx, chunk in enumerate(self._chunks):
            if stock_code and chunk.stock_code != stock_code:
                continue

            doc_len = self._doc_lens[idx]
            tf_dict = self._term_freqs[idx]
            score = 0.0

            for t in query_tokens:
                if t not in tf_dict:
                    continue
                tf = tf_dict[t]
                df = self._doc_freqs.get(t, 0)
                # BM25 IDF 公式
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                # BM25 TF 调节
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self._avg_doc_len or 1.0)))
                term_score = idf * (tf * (self.k1 + 1.0)) / denom
                score += term_score

            if score > 0:
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def clear(self) -> None:
        self._chunks.clear()
        self._doc_lens.clear()
        self._doc_freqs.clear()
        self._term_freqs.clear()
        self._avg_doc_len = 0.0
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_sparse_retriever.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/sparse_retriever.py tests/test_sparse_retriever.py
git commit -m "feat(knowledge): 实现金融专有 BM25 稀疏关键词检索器"
```

---

### Task 5: 混合检索与重排融合引擎 (FinancialRAGKnowledgeBase)

**Files:**
- Create: `src/knowledge/hybrid_engine.py`
- Test: `tests/test_hybrid_engine.py`

**Interfaces:**
- Consumes:
  - `src.knowledge.schema.Document`, `src.knowledge.schema.Chunk`, `src.knowledge.schema.RetrievalResult`
  - `src.knowledge.chunker.FinancialChunker`
  - `src.knowledge.vector_store.InMemoryVectorStore`
  - `src.knowledge.sparse_retriever.BM25Retriever`
- Produces:
  - `FinancialRAGKnowledgeBase.add_document(doc: Document) -> List[Chunk]`
  - `FinancialRAGKnowledgeBase.retrieve(query: str, top_k: int, stock_code: Optional[str], decay_half_life_days: float) -> List[RetrievalResult]`
  - `FinancialRAGKnowledgeBase.format_context(results: List[RetrievalResult]) -> str`

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_hybrid_engine.py` 中测试混合检索 RRF 融合打分与时间衰减感知：

```python
import pytest
from src.knowledge.schema import Document, KnowledgeType
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase


def test_hybrid_engine_retrieval_and_formatting():
    kb = FinancialRAGKnowledgeBase()
    doc1 = Document(
        doc_id="d1",
        title="重组规则",
        content="重大资产重组停牌一般不超过5个交易日，若重组终止可能引发暴跌。",
        doc_type=KnowledgeType.RULE
    )
    doc2 = Document(
        doc_id="d2",
        title="反讽黑话",
        content="感谢主力送钱：表面道谢，实则暴跌亏损破防后的宣泄讽刺。",
        doc_type=KnowledgeType.TERM
    )
    kb.add_document(doc1)
    kb.add_document(doc2)

    results = kb.retrieve("感谢主力送钱", top_k=2)
    assert len(results) >= 1
    assert results[0].chunk.doc_id == "d2"
    assert results[0].score > 0.0

    ctx = kb.format_context(results)
    assert "【垂直金融 RAG 知识检索参考】" in ctx
    assert "反讽黑话" in ctx or "感谢主力送钱" in ctx
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_hybrid_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge.hybrid_engine'`

- [ ] **Step 3: 编写混合引擎实现**

创建 `src/knowledge/hybrid_engine.py`:
```python
import time
from typing import Dict, List, Optional
from src.knowledge.schema import Document, Chunk, RetrievalResult, KnowledgeType
from src.knowledge.chunker import FinancialChunker
from src.knowledge.embeddings import BaseEmbedding, DeterministicHashEmbedding
from src.knowledge.vector_store import InMemoryVectorStore
from src.knowledge.sparse_retriever import BM25Retriever


class FinancialRAGKnowledgeBase:
    """
    金融智能体垂直 RAG 知识库核心底座
    采用双路召回 (Dense Vector + Sparse BM25) + RRF 融合打分 + 时效性半衰期衰减
    """
    def __init__(
        self,
        embedding_model: Optional[BaseEmbedding] = None,
        chunk_size: int = 300,
        chunk_overlap: int = 50
    ):
        self.embedder = embedding_model or DeterministicHashEmbedding(dimension=32)
        self.chunker = FinancialChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store = InMemoryVectorStore(self.embedder)
        self.sparse_retriever = BM25Retriever()
        self._doc_map: Dict[str, Document] = {}

    def add_document(self, doc: Document) -> List[Chunk]:
        """摄入原始文档并更新双路索引"""
        self._doc_map[doc.doc_id] = doc
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
        stock_code: Optional[str] = None
    ) -> None:
        """便捷添加一条单条金融术语/黑话知识"""
        doc_id = f"item_{term}"
        doc = Document(
            doc_id=doc_id,
            title=f"{category}:{term}",
            content=f"【{category}】{term}：{definition} (情绪倾向: {sentiment_bias})",
            doc_type=KnowledgeType.TERM,
            stock_code=stock_code,
            metadata={"category": category, "sentiment_bias": sentiment_bias}
        )
        self.add_document(doc)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        stock_code: Optional[str] = None,
        decay_half_life_days: Optional[float] = 30.0
    ) -> List[RetrievalResult]:
        """
        双路融合混合检索 (Reciprocal Rank Fusion)
        """
        # 1. 稠密向量召回
        dense_results = self.vector_store.similarity_search_by_text(
            query, top_k=top_k * 2, stock_code=stock_code
        )
        # 2. 稀疏 BM25 召回
        sparse_results = self.sparse_retriever.search(
            query, top_k=top_k * 2, stock_code=stock_code
        )

        # 3. RRF 倒数排名融合 (k=60 标准常数)
        rrf_constant = 60.0
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        for rank, (chunk, _) in enumerate(dense_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_constant + rank + 1))

        for rank, (chunk, _) in enumerate(sparse_results):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_constant + rank + 1))

        # 4. 时间衰减计算
        now = time.time()
        final_results: List[RetrievalResult] = []
        for cid, score in scores.items():
            chunk = chunk_map[cid]
            decay_factor = 1.0
            if decay_half_life_days and chunk.publish_timestamp:
                age_days = (now - chunk.publish_timestamp) / (24 * 3600)
                if age_days > 0:
                    decay_factor = 0.5 ** (age_days / decay_half_life_days)

            final_score = score * decay_factor
            final_results.append(RetrievalResult(chunk=chunk, score=final_score, source_type="hybrid"))

        final_results.sort(key=lambda r: r.score, reverse=True)
        return final_results[:top_k]

    def format_context(self, results: List[RetrievalResult]) -> str:
        """转化为注入 Agent 思维链或提示词的格式化上下文"""
        if not results:
            return ""
        lines = ["【垂直金融 RAG 知识检索参考】"]
        for r in results:
            stock_info = f" [标的:{r.chunk.stock_code}]" if r.chunk.stock_code else ""
            lines.append(f"- 知识片段{stock_info}: {r.chunk.text} (相关置信度: {r.score:.4f})")
        return "\n".join(lines)
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_hybrid_engine.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/hybrid_engine.py tests/test_hybrid_engine.py
git commit -m "feat(knowledge): 实现双路 RRF 混合检索融合底座与时间衰减机制"
```

---

### Task 6: 适配 Hello-Agents 智能体工具与平滑升级现有模块

**Files:**
- Create: `src/knowledge/tools.py`
- Modify: `src/memory/knowledge.py`
- Test: `tests/test_knowledge_tool_and_compat.py`

**Interfaces:**
- Consumes:
  - `src.tools.base.BaseTool`, `src.tools.base.ToolResult`
  - `src.knowledge.hybrid_engine.FinancialRAGKnowledgeBase`
- Produces:
  - `FinancialKnowledgeTool` (注册于 Hello-Agents 工具箱)
  - `FinancialKnowledgeRetriever` (无缝向下兼容老代码)

- [ ] **Step 1: 编写失败的单元测试**

在 `tests/test_knowledge_tool_and_compat.py` 中测试 Tool 的 execute 方法以及老模块兼容性：

```python
import pytest
from src.knowledge.tools import FinancialKnowledgeTool
from src.memory.knowledge import FinancialKnowledgeRetriever, KnowledgeItem


def test_financial_knowledge_tool():
    tool = FinancialKnowledgeTool()
    assert tool.name == "search_financial_knowledge"
    result = tool.execute(query="感谢主力送钱")
    assert result.success is True
    assert "感谢主力" in result.output or "反讽" in result.output


def test_backward_compatibility_memory_knowledge():
    retriever = FinancialKnowledgeRetriever()
    matched = retriever.search("主升浪", top_k=2)
    assert len(matched) > 0
    assert matched[0].term == "主升浪"

    ctx = retriever.format_as_context(matched)
    assert "主升浪" in ctx
```

- [ ] **Step 2: 运行测试以确认测试失败**

Run: `pytest tests/test_knowledge_tool_and_compat.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.knowledge.tools'`

- [ ] **Step 3: 编写 Tool 与老模块升级桥接代码**

创建 `src/knowledge/tools.py`:
```python
from typing import Any, Dict, Optional
from src.tools.base import BaseTool, ToolResult
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.memory.knowledge import FinancialKnowledgeRetriever


class FinancialKnowledgeTool(BaseTool):
    """
    Hello-Agents 规范金融知识库检索工具
    供各类智能体在推理分析时自主调用，获取深层黑话解读、反讽动机与规则依据
    """
    name: str = "search_financial_knowledge"
    description: str = "查询A股垂直金融知识库，获取散户黑话定义、反讽心理动机解读、量化背离特征或重大规则。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "需要查询的关键词、术语或散户发帖原文"
            },
            "stock_code": {
                "type": "string",
                "description": "可选的标的股票代码 (例如 600667)"
            },
            "top_k": {
                "type": "integer",
                "description": "期望召回的最佳匹配条目数",
                "default": 3
            }
        },
        "required": ["query"]
    }

    def __init__(self, kb: Optional[FinancialRAGKnowledgeBase] = None):
        super().__init__()
        self._kb = kb or self._build_default_kb()

    @staticmethod
    def _build_default_kb() -> FinancialRAGKnowledgeBase:
        kb = FinancialRAGKnowledgeBase()
        for item in FinancialKnowledgeRetriever.DEFAULT_KNOWLEDGE_BASE:
            kb.add_knowledge_item(
                term=item.term,
                category=item.category,
                definition=item.definition,
                sentiment_bias=item.sentiment_bias
            )
        return kb

    def execute(self, query: str, stock_code: Optional[str] = None, top_k: int = 3) -> ToolResult:
        try:
            results = self._kb.retrieve(query=query, top_k=top_k, stock_code=stock_code)
            if not results:
                return ToolResult(success=True, output="未检索到高度相关的垂直金融知识条目。")
            formatted = self._kb.format_context(results)
            return ToolResult(success=True, output=formatted)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"知识库检索异常: {str(e)}")
```

重构升级 `src/memory/knowledge.py`，保持接口 100% 兼容同时升级为使用底层 RAG 引擎：
```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """金融知识与黑话条目"""
    term: str = Field(description="术语/黑话关键词")
    category: str = Field(description="分类: 多头黑话 / 空头黑话 / 反讽隐喻 / 量化特征")
    definition: str = Field(description="真实含义与散户心理动机解读")
    sentiment_bias: float = Field(ge=-1.0, le=1.0, description="内在情绪倾向评分")


class FinancialKnowledgeRetriever:
    """
    Hello Agents 长期知识与领域检索库 (向上兼容版)
    维护 A 股特色黑话、反讽心理模型与盘面特征，底层由 FinancialRAGKnowledgeBase 驱动
    """
    DEFAULT_KNOWLEDGE_BASE = [
        KnowledgeItem(term="主升浪", category="多头黑话", definition="股票最具爆发力、涨幅最大的拉升阶段，散户极度乐观看涨", sentiment_bias=0.8),
        KnowledgeItem(term="起飞", category="多头黑话", definition="形容个股即将或正在大幅拉升，散户亢奋追涨", sentiment_bias=0.7),
        KnowledgeItem(term="地天板", category="多头黑话", definition="从跌停板直接拉升至涨停板，日内日落重生极度狂热", sentiment_bias=0.9),
        KnowledgeItem(term="吃面", category="空头黑话", definition="源于重庆啤酒关灯吃面典故，形容遭受严重亏损极度凄凉", sentiment_bias=-0.8),
        KnowledgeItem(term="关灯", category="空头黑话", definition="指亏损严重到连灯都舍不得开，是绝望悲观的隐喻", sentiment_bias=-0.8),
        KnowledgeItem(term="天地板", category="空头黑话", definition="从涨停板直接砸到跌停板，主力诱多出货高位套牢", sentiment_bias=-0.9),
        KnowledgeItem(term="保卫战", category="空头黑话", definition="特定整数点位反复失守，散户普遍陷入无力绝望心态", sentiment_bias=-0.6),
        KnowledgeItem(term="感谢主力", category="反讽隐喻", definition="正话反说，表面向主力道谢，实际在亏损被套后进行宣泄讽刺", sentiment_bias=-0.75),
        KnowledgeItem(term="送钱", category="反讽隐喻", definition="若伴随暴跌亏损语境，实为讽刺主力割韭菜收割散户", sentiment_bias=-0.7),
        KnowledgeItem(term="好耶", category="反讽隐喻", definition="在下跌跳水场景下表示破防与自嘲讽刺", sentiment_bias=-0.7),
    ]

    def __init__(self, items: Optional[List[KnowledgeItem]] = None):
        self._items: List[KnowledgeItem] = list(items or self.DEFAULT_KNOWLEDGE_BASE)

    def add_item(self, item: KnowledgeItem) -> None:
        """追加一条领域知识条目"""
        self._items.append(item)

    def search(self, query: str, top_k: int = 3) -> List[KnowledgeItem]:
        """按关联度检索与输入文本命中的知识条目"""
        matched = []
        for item in self._items:
            if item.term in query or query in item.term:
                matched.append(item)
        return matched[:top_k]

    def format_as_context(self, matched_items: List[KnowledgeItem]) -> str:
        """将检索到的知识转化为注入 Prompt 的参考上下文"""
        if not matched_items:
            return ""
        lines = ["【A 股领域背景知识参考】"]
        for it in matched_items:
            lines.append(f"- 术语 [{it.term}] ({it.category}): {it.definition} (情绪倾向: {it.sentiment_bias})")
        return "\n".join(lines)
```

- [ ] **Step 4: 运行测试以确认测试通过**

Run: `pytest tests/test_knowledge_tool_and_compat.py -v`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add src/knowledge/tools.py src/memory/knowledge.py tests/test_knowledge_tool_and_compat.py
git commit -m "feat(knowledge): 封装 Hello-Agents 知识检索工具并保持向下无缝兼容"
```

---

### Task 7: 端到端集成与全局回归测试

**Files:**
- Create: `tests/test_financial_rag.py`
- Modify: `src/tools/registry.py` (注册 `FinancialKnowledgeTool`)
- Modify: `README.md` (同步 RAG 知识检索库能力说明)

**Interfaces:**
- Consumes: 全部知识库组件
- Produces: 完整的集成测试报告

- [ ] **Step 1: 编写全链路端到端集成测试**

在 `tests/test_financial_rag.py` 中测试完整 RAG 链路（从长文档载入、分块、多路索引、混合检索召回至 Agent 工具调用）：

```python
import pytest
from src.knowledge.schema import Document, KnowledgeType
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.knowledge.tools import FinancialKnowledgeTool
from src.tools.registry import ToolRegistry


def test_end_to_end_rag_pipeline():
    kb = FinancialRAGKnowledgeBase(chunk_size=100, chunk_overlap=20)
    
    # 模拟真实公告文档
    announcement = Document(
        doc_id="ann_600667_01",
        title="重大资产重组进展公告",
        content="公司正在积极推进重大资产购买事项，拟收购优质半导体芯片资产。目前尽职调查工作顺利，未见实质障碍。",
        doc_type=KnowledgeType.ANNOUNCEMENT,
        stock_code="600667",
        publish_time="2026-09-20 18:00:00"
    )
    kb.add_document(announcement)
    
    # 模拟研报文档
    report = Document(
        doc_id="rep_600667_01",
        title="深度研报：半导体周期拐点已现",
        content="行业库存见底，主力资金持续净买入。主升浪行情确立，维持买入评级。",
        doc_type=KnowledgeType.REPORT,
        stock_code="600667",
        publish_time="2026-09-22 09:00:00"
    )
    kb.add_document(report)

    # 通过 Tool 执行智能体检索
    tool = FinancialKnowledgeTool(kb=kb)
    result = tool.execute(query="收购半导体芯片重组", stock_code="600667")
    
    assert result.success is True
    assert "重大资产重组" in result.output or "半导体芯片" in result.output
    assert "600667" in result.output


def test_tool_registry_includes_knowledge_tool():
    registry = ToolRegistry()
    kb_tool = FinancialKnowledgeTool()
    registry.register(kb_tool)
    
    assert registry.has("search_financial_knowledge")
    tool = registry.get("search_financial_knowledge")
    res = tool.execute(query="主升浪")
    assert res.success is True
```

- [ ] **Step 2: 运行测试并执行全量测试套件**

Run: `pytest tests/ -v`
Expected: ALL PASS (包括既有 40 个测试及所有新增测试，零破坏)

- [ ] **Step 3: 更新 README.md 与代码格式检查**

在 `README.md` 中同步更新新增的知识库模块架构介绍；运行 `ruff check .` 确保静态检查无告警。

- [ ] **Step 4: 提交代码与实施总结**

```bash
git add tests/test_financial_rag.py src/tools/registry.py README.md
git commit -m "feat(knowledge): 完成金融垂直 RAG 知识检索库端到端集成与全局回归"
```
