from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional
from src.core.market_schema import MarketSnapshot
from src.core.schema import SentimentAnalysisResult, NewsArticle, AnnouncementItem
from src.workflow.state import MultiAgentDebateResult, CatalystItem

class DivergenceType(str, Enum):
    BULL_TRAP = "多头诱多 (BULL_TRAP)"
    PANIC_BOTTOM = "恐慌磨底 (PANIC_BOTTOM)"
    CONSISTENT = "情绪与盘面一致 (CONSISTENT)"
    INSUFFICIENT_DATA = "数据不足 (INSUFFICIENT_DATA)"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_upper = value.strip().upper()
            for member in cls:
                if member.name == val_upper or val_upper in member.value.upper():
                    return member
        return super()._missing_(value)

class RiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class ReflectionDecision(BaseModel):
    is_divergent: bool = Field(description='情绪与盘面客观事实是否存在背离')
    divergence_type: DivergenceType = Field(description='背离类型')
    risk_level: RiskLevel = Field(description='风险级别: HIGH, MEDIUM, LOW, UNKNOWN')
    reflection_narrative: str = Field(description='反思研判推导链')
    action_suggestion: str = Field(description='最终建议')

class AgentState(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    market_data: Optional[MarketSnapshot] = None
    sentiment_list: List[SentimentAnalysisResult] = Field(default_factory=list)
    news_list: List[NewsArticle] = Field(default_factory=list, description="主流专业财经资讯")
    announcements: List[AnnouncementItem] = Field(default_factory=list, description="官方披露公告")
    average_sentiment: float = 0.0
    sentiment_sample_count: Optional[int] = Field(default=None, ge=0, description="实际取得的有效舆情样本数；None 代表旧调用方未提供")
    reflection: Optional[ReflectionDecision] = None
    iteration_count: int = 0
    catalysts: List[CatalystItem] = Field(default_factory=list, description="基本面正向催化与驱动事实")
    risks: List[CatalystItem] = Field(default_factory=list, description="基本面负向警示与潜在风险事实")
    debate_result: Optional[MultiAgentDebateResult] = Field(default=None, description="多智能体多空博弈辩论与仲裁决议")
    execution_logs: List[str] = Field(default_factory=list, description="Agent 全流程可审计执行日志与消歧链路")
