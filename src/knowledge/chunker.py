"""金融文本结构化与滑动窗口分块器"""

import time
from typing import List, Optional
from src.knowledge.schema import Document, Chunk


class FinancialChunker:
    """
    金融文档智能切片分块器
    支持按双换行/段落切分、滑动窗口重叠（保持跨切片上下文连续性），并自动继承股票代码与时间戳元数据
    """

    def __init__(self, chunk_size: int = 250, chunk_overlap: int = 50):
        if chunk_size <= 0:
            raise ValueError(f"chunk_size 必须为正整数，收到: {chunk_size}")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap 必须满足 0 <= overlap < chunk_size，收到: overlap={chunk_overlap}, size={chunk_size}")
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

        # 超长单段落硬切兜底：无空行的长段落（中文网页文本极常见）若不切分
        # 会绕过 chunk_size 上限，稀释向量并失去检索粒度
        sized_paragraphs: List[str] = []
        for para in paragraphs:
            if len(para) <= self.chunk_size:
                sized_paragraphs.append(para)
                continue
            step = self.chunk_size - self.chunk_overlap
            start = 0
            while start < len(para):
                sized_paragraphs.append(para[start:start + self.chunk_size])
                if start + self.chunk_size >= len(para):
                    break
                start += step
        paragraphs = sized_paragraphs

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
