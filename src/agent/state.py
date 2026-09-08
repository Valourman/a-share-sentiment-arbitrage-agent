from pydantic import BaseModel, Field
from typing import List, Optional
from src.core.market_schema import MarketSnapshot
from src.core.schema import SentimentAnalysisResult

class ReflectionDecision(BaseModel):
    is_divergent: bool = Field(description='情绪与盘面客观事实是否存在背离')
    divergence_type: str = Field(description='背离类型: BULL_TRAP(多头诱多), PANIC_BOTTOM(恐慌磨底), CONSISTENT(情绪与盘面一致)')
    risk_level: str = Field(description='风险级别: HIGH, MEDIUM, LOW')
    reflection_narrative: str = Field(description='反思研判推导链')
    action_suggestion: str = Field(description='最终建议')

class AgentState(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    market_data: Optional[MarketSnapshot] = None
    sentiment_list: List[SentimentAnalysisResult] = Field(default_factory=list)
    average_sentiment: float = 0.0
    reflection: Optional[ReflectionDecision] = None
    iteration_count: int = 0
