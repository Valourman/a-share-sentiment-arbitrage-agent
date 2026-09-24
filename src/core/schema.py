from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SentimentStance(str, Enum):
    BULLISH = "bullish"    # 看多 / 乐观
    BEARISH = "bearish"    # 看空 / 悲观
    NEUTRAL = "neutral"    # 中性 / 客观公告


class RawPost(BaseModel):
    """东方财富等股吧抓取的原始帖子数据模型"""
    title: str = Field(description="帖子标题")
    author: Optional[str] = Field(default=None, description="作者昵称")
    publish_time: Optional[str] = Field(default=None, description="发帖时间")
    read_count: int = Field(default=0, description="阅读量")
    comment_count: int = Field(default=0, description="评论量")
    url: Optional[str] = Field(default=None, description="帖子链接")


class NewsArticle(BaseModel):
    """新浪/财联社等主流专业财经新闻资讯模型"""
    title: str = Field(description="资讯标题")
    source: str = Field(default="新浪财经", description="新闻来源媒体")
    publish_time: Optional[str] = Field(default=None, description="发布时间")
    url: Optional[str] = Field(default=None, description="资讯链接")


class AnnouncementItem(BaseModel):
    """上市公司官方披露公告模型"""
    title: str = Field(description="公告标题")
    publish_time: Optional[str] = Field(default=None, description="披露时间")
    url: Optional[str] = Field(default=None, description="公告链接")


class SentimentAnalysisResult(BaseModel):
    """大模型/分析引擎产出的结构化情绪判定契约"""
    raw_title: Optional[str] = Field(default=None, description="原始发帖标题/语料")
    stance: SentimentStance = Field(description="核心立场: 看多/看空/中性")
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="情绪强度，-1.0为极度恐慌/看空，+1.0为极度亢奋/看多")
    is_sarcasm: bool = Field(default=False, description="是否包含反讽/正话反说 (如: 好耶主力又送钱了)")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8, description="判定置信度")
    slang_detected: List[str] = Field(default_factory=list, description="命中的股市隐喻/黑话")
    reasoning: str = Field(description="严谨的研判逻辑链 (COT推导过程)")
    engine_used: Optional[str] = Field(default=None, description="实际执行研判的引擎: jev / llm / mock")
    probabilities: Dict[str, Any] = Field(default_factory=dict, description="多空立场概率分布 (Jev Choice 输出)")
    sarcasm_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="反讽概率 (Jev Noul 输出)")
    latency_ms: Optional[float] = Field(default=None, description="单次研判耗时 (毫秒)")
