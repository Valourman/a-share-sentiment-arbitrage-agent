"""
单元测试: AgentState 与 DivergenceType 枚举测试套件
命名规范: test_<功能>_<场景>_<期望结果>
"""
import pytest
from src.agent.state import DivergenceType, RiskLevel, ReflectionDecision, AgentState
from src.core.market_schema import MarketSnapshot

def test_divergence_type_enum_backward_compatibility_resolves_old_strings():
    """测试通过旧字符串代码或名称能够成功映射为 DivergenceType 枚举"""
    assert DivergenceType("BULL_TRAP") == DivergenceType.BULL_TRAP
    assert DivergenceType("PANIC_BOTTOM") == DivergenceType.PANIC_BOTTOM
    assert DivergenceType("CONSISTENT") == DivergenceType.CONSISTENT

def test_reflection_decision_instantiation_with_enum_and_value_access():
    """测试 ReflectionDecision 实例可以通过 .value 获取人类可读中文标签"""
    decision = ReflectionDecision(
        is_divergent=True,
        divergence_type=DivergenceType.BULL_TRAP,
        risk_level=RiskLevel.HIGH,
        reflection_narrative="情绪过热但盘面下挫",
        action_suggestion="严控仓位"
    )
    assert decision.is_divergent is True
    assert "多头诱多" in decision.divergence_type.value
    assert decision.risk_level == RiskLevel.HIGH

def test_agent_state_defaults_and_lifecycle():
    """测试 AgentState 初始化默认值与状态迭代生命周期"""
    state = AgentState(stock_code="600584")
    assert state.stock_code == "600584"
    assert state.average_sentiment == 0.0
    assert state.iteration_count == 0
    assert len(state.sentiment_list) == 0
    assert state.market_data is None

    # 更新市场数据快照
    state.market_data = MarketSnapshot(
        stock_code="600584",
        stock_name="长电科技",
        current_price=30.5,
        pre_close=30.0,
        change_percent=1.67,
        turnover_amount_yi=12.5,
        is_trading=True
    )
    assert state.market_data.stock_name == "长电科技"
    assert state.market_data.change_percent == 1.67
