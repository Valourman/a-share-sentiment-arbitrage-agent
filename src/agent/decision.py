"""Domain policy for comparing forum sentiment with a validated market snapshot.

The policy and its explanations live outside the Agent orchestrator so that
collection, assessment, and presentation can be tested independently.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Optional

from src.agent.state import AgentState, DivergenceType, ReflectionDecision, RiskLevel
from src.core.market_schema import MarketSnapshot

# 背离研判与样本有效性阈值常量
BULLISH_SENTIMENT_THRESHOLD: float = 0.20
BEARISH_SENTIMENT_THRESHOLD: float = -0.20
PRICE_DROP_THRESHOLD_PCT: float = -0.5
MIN_RELIABLE_SAMPLE_COUNT: int = 5


def has_valid_market_snapshot(market: Optional[MarketSnapshot]) -> bool:
    """A failed or zero-filled quote is not evidence of a flat trading day."""
    return bool(
        market is not None
        and market.is_trading
        and market.current_price > 0
        and market.pre_close > 0
        and isfinite(market.current_price)
        and isfinite(market.pre_close)
        and isfinite(market.change_percent)
    )


@dataclass(frozen=True)
class DivergenceAssessment:
    is_divergent: bool
    divergence_label: DivergenceType
    risk_level: RiskLevel
    sentiment: float
    chg_pct: float
    missing_sources: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Preserve the existing evaluate_critique dictionary contract."""
        return {
            "is_divergent": self.is_divergent,
            "divergence_label": self.divergence_label,
            "risk_level": self.risk_level,
            "sentiment": self.sentiment,
            "chg_pct": self.chg_pct,
            "missing_sources": list(self.missing_sources),
        }

    @classmethod
    def from_dict(cls, critique: Mapping[str, Any]) -> "DivergenceAssessment":
        """Reuse the critique in the reflection step instead of recomputing it."""
        return cls(
            is_divergent=critique["is_divergent"],
            divergence_label=DivergenceType(critique["divergence_label"]),
            risk_level=RiskLevel(critique["risk_level"]),
            sentiment=critique["sentiment"],
            chg_pct=critique["chg_pct"],
            missing_sources=tuple(critique.get("missing_sources", ())),
        )


def assess_divergence(state: AgentState) -> DivergenceAssessment:
    """Apply one conservative, deterministic rule to the available evidence."""
    market_valid = has_valid_market_snapshot(state.market_data)
    missing = []
    if not market_valid:
        missing.append("有效行情")
    # None means older callers supplied an aggregate score without sample data.
    if state.sentiment_sample_count == 0 or not isfinite(state.average_sentiment):
        missing.append("有效舆情样本")

    sentiment = state.average_sentiment if isfinite(state.average_sentiment) else 0.0
    change = state.market_data.change_percent if market_valid else 0.0
    if missing:
        return DivergenceAssessment(
            False, DivergenceType.INSUFFICIENT_DATA, RiskLevel.UNKNOWN,
            sentiment, change, tuple(missing),
        )
    if sentiment >= BULLISH_SENTIMENT_THRESHOLD and change < PRICE_DROP_THRESHOLD_PCT:
        return DivergenceAssessment(True, DivergenceType.BULL_TRAP, RiskLevel.HIGH, sentiment, change)
    if sentiment <= BEARISH_SENTIMENT_THRESHOLD and change >= 0.0:
        return DivergenceAssessment(True, DivergenceType.PANIC_BOTTOM, RiskLevel.MEDIUM, sentiment, change)
    return DivergenceAssessment(False, DivergenceType.CONSISTENT, RiskLevel.LOW, sentiment, change)


def build_reflection_decision(
    state: AgentState, assessment: DivergenceAssessment
) -> ReflectionDecision:
    """Explain only observed evidence; headlines alone do not establish causality."""
    source_note = (
        f"另收集新闻 {len(state.news_list)} 篇、公告 {len(state.announcements)} 份，"
        "其内容尚未参与方向判定。"
        if state.news_list or state.announcements else ""
    )
    sample_note = (
        "舆情样本较少，结果仅供参考。"
        if state.sentiment_sample_count is not None and state.sentiment_sample_count < MIN_RELIABLE_SAMPLE_COUNT
        else ""
    )

    if assessment.divergence_label == DivergenceType.INSUFFICIENT_DATA:
        reason = "、".join(assessment.missing_sources) or "必要数据"
        narrative = f"缺少{reason}，无法判断舆情与盘面是否背离。{source_note}"
        suggestion = "数据不足，不给出买卖结论；请核对行情和舆情样本后重试。"
    elif assessment.divergence_label == DivergenceType.BULL_TRAP:
        narrative = (
            f"散户情绪偏乐观({assessment.sentiment:+.2f})，而行情下跌"
            f"({assessment.chg_pct:+.2f}%)，存在多头诱多风险；"
            f"仅凭此背离无法证实主力出货。{sample_note}{source_note}"
        )
        suggestion = "警惕情绪与价格背离，等待更多有效量价与公告证据，不宜仅据此抄底。"
    elif assessment.divergence_label == DivergenceType.PANIC_BOTTOM:
        narrative = (
            f"散户情绪呈悲观绝望({assessment.sentiment:+.2f})，而行情未下跌"
            f"({assessment.chg_pct:+.2f}%)，可能出现恐慌磨底；"
            f"仅凭此背离无法证明机构吸筹或反弹将至。{sample_note}{source_note}"
        )
        suggestion = "恐慌盘与价格走势存在分歧，继续观察；不要仅凭情绪分值决定建仓。"
    else:
        narrative = (
            f"散户情绪指数({assessment.sentiment:+.2f})与盘面涨跌"
            f"({assessment.chg_pct:+.2f}%)未触发背离规则。"
            f"这不等同于已确认的市场趋势。{sample_note}{source_note}"
        )
        suggestion = "当前未检测到规则定义的背离，仍需结合基本面及其他风险因素判断。"

    return ReflectionDecision(
        is_divergent=assessment.is_divergent,
        divergence_type=assessment.divergence_label,
        risk_level=assessment.risk_level,
        reflection_narrative=narrative,
        action_suggestion=suggestion,
    )
