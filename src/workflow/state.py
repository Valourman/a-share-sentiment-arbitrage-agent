from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class CatalystType(str, Enum):
    """基本面/新闻催化类型"""
    POSITIVE = "利好催化 (POSITIVE)"
    NEGATIVE = "风险警示 (NEGATIVE)"
    NEUTRAL = "中性观察 (NEUTRAL)"


class CatalystItem(BaseModel):
    """催化剂或风险事实项"""
    source_title: str = Field(description="来源新闻或公告标题")
    source_type: str = Field(description="来源类别: news / announcement / report")
    catalyst_type: CatalystType = Field(description="催化性质")
    key_insight: str = Field(description="核心提炼要点与传导逻辑")
    impact_level: str = Field(default="MEDIUM", description="影响强度: HIGH, MEDIUM, LOW")


class DebateStance(str, Enum):
    """辩论立场"""
    BULLISH = "多头逻辑 (BULL)"
    BEARISH = "空头逻辑 (BEAR)"
    NEUTRAL = "中立观望 (NEUTRAL)"


class DebateOpinion(BaseModel):
    """单一智能体研究员的辩论论点（对标 TradingAgents 的 Bull/Bear Researcher）"""
    agent_name: str = Field(description="研究员智能体代号，如 BullAnalyst, BearAnalyst")
    stance: DebateStance = Field(description="论点核心倾向")
    core_thesis: str = Field(description="核心观点概述")
    arguments: List[str] = Field(default_factory=list, description="论据支撑列表（基本面、散户心理、盘面量价等）")
    evidence_citations: List[str] = Field(default_factory=list, description="溯源证据（引用具体的新闻、公告或股吧讨论）")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="置信度评分 (0.0 - 1.0)")


class MultiAgentDebateResult(BaseModel):
    """多智能体多空辩论最终对抗决议（对标 TradingAgents / FinRobot Debate Protocol）"""
    bull_opinion: DebateOpinion = Field(description="多头研究员陈述与论据")
    bear_opinion: DebateOpinion = Field(description="空头研究员陈述与论据")
    key_divergence_point: str = Field(description="多空双方的核心分歧焦点")
    arbitration_summary: str = Field(description="风控仲裁员对双方博弈的综合裁决摘要")
    consensus_bias: str = Field(description="博弈后的倾向定性: 多方占优 / 空方占优 / 僵持背离 / 存疑中立")
