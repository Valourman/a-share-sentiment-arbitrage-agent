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
        if not isinstance(value, str):
            return super()._missing_(value)

        val = value.strip()
        if not val:
            # 空串/纯空白不得匹配任何成员，避免脏数据被静默判为 BULL_TRAP
            # 污染下游风控结论（空串 in 任意字符串恒为 True）
            return super()._missing_(value)

        val_upper = val.upper()

        # 1. 显式中文常用简写与业务别名精准映射
        chinese_aliases = {
            # 多头诱多
            "多头诱多": cls.BULL_TRAP,
            "诱多": cls.BULL_TRAP,
            "多头": cls.BULL_TRAP,
            "诱多背离": cls.BULL_TRAP,
            # 恐慌磨底
            "恐慌磨底": cls.PANIC_BOTTOM,
            "磨底": cls.PANIC_BOTTOM,
            "恐慌": cls.PANIC_BOTTOM,
            "磨底背离": cls.PANIC_BOTTOM,
            # 情绪与盘面一致
            "情绪与盘面一致": cls.CONSISTENT,
            "盘面一致": cls.CONSISTENT,
            "情绪一致": cls.CONSISTENT,
            "一致": cls.CONSISTENT,
            # 数据不足
            "数据不足": cls.INSUFFICIENT_DATA,
            "不足": cls.INSUFFICIENT_DATA,
        }
        if val in chinese_aliases:
            return chinese_aliases[val]

        # 2. 精确枚举名或完整值匹配 (如 "BULL_TRAP" 或 "多头诱多 (BULL_TRAP)")
        for member in cls:
            if member.name == val_upper or member.value.upper() == val_upper:
                return member

        # 3. 中文子串唯一匹配（输入包含汉字且长度 >= 2）
        has_chinese = any("一" <= ch <= "鿿" for ch in val)
        if has_chinese and len(val) >= 2:
            matched = [m for m in cls if val in m.value]
            if len(matched) == 1:
                return matched[0]

        # 4. 英文子串唯一匹配（要求长度 >= 3，防止如 "IN" 等无意义短串误吞）
        if len(val_upper) >= 3:
            matched = [m for m in cls if val_upper in m.value.upper() or val_upper in m.name]
            if len(matched) == 1:
                return matched[0]

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
