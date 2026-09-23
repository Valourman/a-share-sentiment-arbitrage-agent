"""金融知识库核心数据契约与数据模型定义"""

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
