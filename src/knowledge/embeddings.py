"""金融向量嵌入模型抽象与轻量确定性实现"""

import hashlib
import math
from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """
    向量嵌入模型抽象基类
    定义单文本及批量文本到稠密浮点向量的转换接口规范
    """

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """将单个查询或文本转换为稠密特征向量

        参数:
            text: 输入待编码文本

        返回:
            稠密浮点向量列表
        """
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量将文本列表转换为稠密特征向量列表

        参数:
            texts: 待编码文本列表

        返回:
            二维浮点向量列表
        """
        pass

    def embed_text(self, text: str) -> List[float]:
        """embed_query 的便捷别名方法"""
        return self.embed_query(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """embed_documents 的便捷别名方法"""
        return self.embed_documents(texts)


class DeterministicHashEmbedding(BaseEmbedding):
    """
    轻量确定性局部哈希向量生成器 (零第三方重量级模型依赖)
    基于 MD5 结合 n-gram 局部投影与 L2 范数归一化，
    用于单元测试、快速验证以及离线环境兜底，具有强确定性与词频相似性。
    """

    def __init__(self, dimension: int = 32):
        """初始化哈希嵌入器

        参数:
            dimension: 嵌入向量目标维度，默认为 32
        """
        self.dimension = dimension

    def _hash_token(self, token: str) -> int:
        """计算 token 的 MD5 散列值作为整型映射基数"""
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        return int(h, 16)

    def embed_query(self, text: str) -> List[float]:
        """将输入文本计算为具有 L2 归一化的固定维度向量

        参数:
            text: 输入待编码文本

        返回:
            归一化后的浮点向量
        """
        vec = [0.0] * self.dimension
        if not text:
            return vec

        # 按 2-gram / 字符局部滑动窗口投影至向量空间
        for i in range(len(text)):
            gram = text[i:min(i + 2, len(text))]
            idx = self._hash_token(gram) % self.dimension
            vec[idx] += 1.0

        # L2 范数归一化
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本集合

        参数:
            texts: 文本列表

        返回:
            向量列表
        """
        return [self.embed_query(t) for t in texts]
