"""金融专有 BM25 稀疏关键词检索器模块"""

import math
import re
from typing import Dict, List, Optional, Tuple

from src.knowledge.schema import Chunk


class BM25Retriever:
    """
    轻量高效的中文金融 BM25 稀疏检索器
    对金融专有简称、股票代码、成语及黑话具备精确的关键词召回能力，
    支持金融专有符号（如 $AAPL、¥100 等）的完整解析与精确匹配。
    """

    FINANCIAL_PATTERN = re.compile(
        r"(?:"
        r"\$[a-z0-9_\.]+"
        r"|[¥￥$€£]\s*[0-9]+(?:\.[0-9]+)?(?:[万亿kmbt])?"
        r"|[0-9]+(?:\.[0-9]+)?%"
        r"|[a-z0-9_]+"
        r"|[一-龥]"
        r")"
    )

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """初始化 BM25 稀疏检索器

        参数:
            k1: 词频饱和度调节因子，默认 1.5
            b: 文档长度归一化调节因子，默认 0.75
        """
        self.k1 = k1
        self.b = b
        self._chunks: List[Chunk] = []
        self._doc_lens: List[int] = []
        self._avg_doc_len: float = 0.0
        self._doc_freqs: Dict[str, int] = {}
        self._term_freqs: List[Dict[str, int]] = []

    def _tokenize(self, text: str) -> List[str]:
        """中文字符、英文/数字序列与金融符号（如 $AAPL、¥100 等）结构化分词。

        将英文字母统一转为小写，优先提取完整的金融 Cashtag、货币金额及百分比实体，
        并保留核心脱符子词元以支持混合检索；汉字按单字切分。

        参数:
            text: 待分词的原始文本

        返回:
            词元字符串列表
        """
        text = text.lower()
        raw_matches = self.FINANCIAL_PATTERN.findall(text)
        tokens: List[str] = []
        for match in raw_matches:
            clean_token = match.strip()
            if not clean_token:
                continue
            tokens.append(clean_token)
            # 若属于金融带符号词元（如 $aapl 或 ¥100），派发脱符号词元，
            # 保证精确符号查询 ($AAPL) 与普通无符号查询 (AAPL) 均能高置信度召回
            if clean_token.startswith("$") and len(clean_token) > 1:
                sub = clean_token[1:]
                if sub and sub != clean_token:
                    tokens.append(sub)
            elif clean_token[0] in ("¥", "￥", "€", "£") and len(clean_token) > 1:
                sub = clean_token[1:].strip()
                if sub and sub != clean_token:
                    tokens.append(sub)
        return tokens

    def add_chunks(self, chunks: List[Chunk]) -> None:
        """批量追加切片并更新倒排索引与统计指标

        参数:
            chunks: 待添加的切片对象列表
        """
        for chunk in chunks:
            # 融合股票代码元数据以支持按股票代码直接精确检索
            index_content = f"{chunk.stock_code} {chunk.text}" if chunk.stock_code else chunk.text
            tokens = self._tokenize(index_content)
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
        stock_code: Optional[str] = None,
    ) -> List[Tuple[Chunk, float]]:
        """基于 BM25 算法计算相关度打分并执行关键词检索

        参数:
            query: 查询字符串
            top_k: 最大返回候选切片数
            stock_code: 可选的股票代码过滤条件

        返回:
            (Chunk, score) 二元组列表，按得分降序排列
        """
        query_tokens = self._tokenize(query)
        if not query_tokens or not self._chunks:
            return []

        num_docs = len(self._chunks)
        scores: List[Tuple[Chunk, float]] = []

        for idx, chunk in enumerate(self._chunks):
            # 精确匹配股票代码元数据过滤
            if stock_code is not None and chunk.stock_code != stock_code:
                continue

            doc_len = self._doc_lens[idx]
            tf_dict = self._term_freqs[idx]
            score = 0.0

            for t in query_tokens:
                if t not in tf_dict:
                    continue
                tf = tf_dict[t]
                df = self._doc_freqs.get(t, 0)

                # BM25 IDF 平滑公式
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                # BM25 TF 长度归一化调节
                denom = tf + self.k1 * (
                    1.0 - self.b + self.b * (doc_len / (self._avg_doc_len or 1.0))
                )
                term_score = idf * (tf * (self.k1 + 1.0)) / denom
                score += term_score

            if score > 0.0:
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def clear(self) -> None:
        """清空检索器存储的所有切片及其索引结构"""
        self._chunks.clear()
        self._doc_lens.clear()
        self._doc_freqs.clear()
        self._term_freqs.clear()
        self._avg_doc_len = 0.0

    @property
    def total_chunks(self) -> int:
        """获取当前索引库中的切片总量"""
        return len(self._chunks)
