import streamlit as st
import pandas as pd
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import DivergenceType, AgentState

st.set_page_config(page_title="A-Share Sentiment Agent", page_icon="📈", layout="wide")
st.title("📈 A股舆情反讽研判与异动背离预警 Agent")
st.caption("双向闭环架构：大模型思维链语义消歧 + 秒级L1盘面基准交叉验证 + Pydantic自愈决策")

# 初始化 Session State
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None

with st.sidebar:
    st.header("⚙️ 研判参数配置")
    stock_code = st.text_input("股票代码 (6位 A 股代码)", value="600584", help="如 600519(贵州茅台), 600584(长电科技), 002594(比亚迪)")
    max_posts = st.slider("散户发帖分析深度 (条数)", min_value=3, max_value=15, value=5)
    use_llm = st.checkbox("启用真实大模型推理 (Gemini / OpenAI)", value=True)
    run_btn = st.button("🚀 启动智能反思研判", type="primary", use_container_width=True)

if run_btn:
    with st.spinner(f"Agent 正在采集 [{stock_code}] 舆情并启动多步反思研判..."):
        try:
            agent = SentimentArbitrageAgent()
            state = agent.run(stock_code=stock_code, max_posts=max_posts, use_llm=use_llm)
            st.session_state.agent_state = state
        except Exception as err:
            st.error(f"Agent 执行异常: {err}")

# 如果 session_state 中有研判结果，则持续渲染
if st.session_state.agent_state is not None:
    state: AgentState = st.session_state.agent_state

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("标的名称", f"{state.stock_name} ({state.stock_code})")
    curr_price = state.market_data.current_price if state.market_data else 0.0
    chg_pct = state.market_data.change_percent if state.market_data else 0.0
    turnover = state.market_data.turnover_amount_yi if state.market_data else 0.0
    m2.metric("最新价格", f"{curr_price:.2f} 元", f"{chg_pct:+.2f}%")
    m3.metric("今日成交额", f"{turnover:.2f} 亿元")
    m4.metric("散户综合情绪分", f"{state.average_sentiment:+.2f}", "区间: [-1, +1]")

    st.divider()
    st.subheader("🎯 Agent 背离研判与风险预警")
    ref = state.reflection

    if ref:
        div_label = getattr(ref.divergence_type, "value", str(ref.divergence_type))
        risk_label = getattr(ref.risk_level, "value", str(ref.risk_level))
        if ref.is_divergent:
            st.error(f"🚨 触发背离警报: 【{div_label}】 (风险等级: {risk_label})")
        else:
            st.success(f"✅ 状态平稳: 【{div_label}】 (风险等级: {risk_label})")

        st.write(f"**研判推导依据**: {ref.reflection_narrative}")
        st.info(f"**💡 操作建议提示**: {ref.action_suggestion}")

    st.divider()
    st.subheader("🔍 散户语料明细与大模型思维链消歧")
    table_rows = []
    for item in state.sentiment_list:
        stance_val = getattr(item.stance, "value", str(item.stance))
        table_rows.append({
            "多空立场": stance_val,
            "情绪评分": f"{item.sentiment_score:+.2f}",
            "是否反讽": "🔥 是 (反语)" if item.is_sarcasm else "否",
            "识别黑话": ", ".join(item.slang_detected) if item.slang_detected else "-",
            "模型思考依据": item.reasoning
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)
else:
    st.info("👈 请在左侧侧边栏输入股票代码，点击「启动智能反思研判」体验完整的 Agent 决策链路。")