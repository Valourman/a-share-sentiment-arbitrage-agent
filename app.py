import streamlit as st
import pandas as pd
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import DivergenceType, AgentState

st.set_page_config(
    page_title="A-Share Sentiment Agent · Gemini Aesthetic",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 注入 Google Gemini 设计系统全局定制样式
# ==========================================
GEMINI_CSS = """
<style>
/* 引入现代化无衬线字体 */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 页面背景与呼吸留白 */
.stApp {
    background-color: #F8FAFD;
    color: #1F1F1F;
}

/* 限制中央视口最大阅读宽度，营造 Gemini 单栏聚焦体验 */
.main .block-container {
    max-width: 960px;
    padding-top: 2rem;
    padding-bottom: 5rem;
}

/* 顶栏与标题美化：Gemini 极光色彩渐变 */
.gemini-title {
    font-size: 1.85rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #4285F4 0%, #9B72CF 50%, #D96570 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
}

.gemini-caption {
    color: #5F6368;
    font-size: 0.875rem;
    line-height: 1.5;
    margin-bottom: 1.5rem;
}

/* 左侧折叠侧边栏：浅灰中性底色与大圆角容器 */
[data-testid="stSidebar"] {
    background-color: #F0F4F9 !important;
    border-right: 1px solid rgba(0, 0, 0, 0.05);
}

/* 按钮组件：Gemini 悬浮复合胶囊风格 */
.stButton > button {
    background: linear-gradient(135deg, #4285F4 0%, #6366F1 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 9999px !important;
    padding: 0.55rem 1.25rem !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    box-shadow: 0 4px 14px rgba(66, 133, 244, 0.25) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.stButton > button:hover {
    box-shadow: 0 6px 20px rgba(66, 133, 244, 0.35) !important;
    transform: translateY(-1px);
}
.stButton > button:active {
    transform: scale(0.98);
}

/* 行情指标 Metric 卡片：悬浮微光与柔和阴影 */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 20px;
    padding: 1rem 1.25rem;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.05);
}
[data-testid="stMetricLabel"] {
    color: #70757A !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #1F1F1F !important;
}

/* 背离研判雷达卡 */
.radar-alert-card {
    background: #FFFFFF;
    border: 1px solid #FECACA;
    border-left: 5px solid #EF4444;
    border-radius: 20px;
    padding: 1.25rem 1.5rem;
    margin: 1.5rem 0;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.08);
}
.radar-alert-card.safe {
    border-color: #A7F3D0;
    border-left-color: #10B981;
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.08);
}

.radar-title {
    font-size: 1rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.radar-badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    background: #FEE2E2;
    color: #B91C1C;
}

/* 散户发帖卡片式排版 (开放式消息流) */
.post-bubble {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 18px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
}
.post-bubble:hover {
    background: #FAFCFE;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}
.slang-chip {
    display: inline-block;
    background: #F1F3F4;
    color: #4B5563;
    font-family: monospace;
    font-size: 0.72rem;
    padding: 0.15rem 0.5rem;
    border-radius: 6px;
    margin-right: 0.35rem;
}
.sarcasm-tag {
    display: inline-flex;
    align-items: center;
    background: #FEF3C7;
    color: #92400E;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    margin-right: 0.35rem;
}
</style>
"""
st.markdown(GEMINI_CSS, unsafe_allow_html=True)

# 顶栏标题
st.markdown('<div class="gemini-title">✨ A股舆情反讽研判与异动背离预警 Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="gemini-caption">参考 Google Gemini 交互哲学构建 · 大模型思维链消歧 + 秒级盘面基准验证 + 决策自愈</div>', unsafe_allow_html=True)

# 初始化 Session State
if "agent_state" not in st.session_state:
    st.session_state.agent_state = None

with st.sidebar:
    st.markdown("### ⚙️ 研判参数配置")
    stock_code = st.text_input("股票代码 (6位 A 股代码)", value="600584", help="如 600519(贵州茅台), 600584(长电科技), 002594(比亚迪)")
    max_posts = st.slider("散户发帖分析深度 (条数)", min_value=3, max_value=15, value=5)
    use_llm = st.checkbox("启用真实大模型推理 (Gemini / DeepSeek)", value=True)

    st.markdown("---")
    st.markdown("<small style='color: #70757A;'>💡 提示：本系统结合了大模型反思消除网络『反讽』黑话与实时行情 L1 基准。</small>", unsafe_allow_html=True)
    run_btn = st.button("🚀 启动智能反思研判", use_container_width=True)

if run_btn:
    with st.spinner(f"Agent 正在采集 [{stock_code}] 散户舆情并启动多步思维链研判..."):
        try:
            agent = SentimentArbitrageAgent()
            state = agent.run(stock_code=stock_code, max_posts=max_posts, use_llm=use_llm)
            st.session_state.agent_state = state
        except Exception as err:
            st.error(f"Agent 执行异常: {err}")

# 如果 session_state 中有研判结果，则持续渲染
if st.session_state.agent_state is not None:
    state: AgentState = st.session_state.agent_state

    # 1. 行情与情绪四宫格 Metric 芯片
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("标的名称", f"{state.stock_name}", f"代码: {state.stock_code}")
    curr_price = state.market_data.current_price if state.market_data else 0.0
    chg_pct = state.market_data.change_percent if state.market_data else 0.0
    turnover = state.market_data.turnover_amount_yi if state.market_data else 0.0
    m2.metric("最新价格", f"{curr_price:.2f} 元", f"{chg_pct:+.2f}%")
    m3.metric("今日成交额", f"{turnover:.2f} 亿元", "主力博弈")
    m4.metric("散户综合情绪分", f"{state.average_sentiment:+.2f}", "区间: [-1, +1]")

    # 2. 背离研判雷达警报卡
    ref = state.reflection
    if ref:
        div_label = getattr(ref.divergence_type, "value", str(ref.divergence_type))
        risk_label = getattr(ref.risk_level, "value", str(ref.risk_level))
        is_alert = ref.is_divergent
        card_class = "radar-alert-card" if is_alert else "radar-alert-card safe"
        badge_style = "background: #FEE2E2; color: #B91C1C;" if is_alert else "background: #D1FAE5; color: #065F46;"
        icon = "🚨" if is_alert else "✅"

        st.markdown(f"""
        <div class="{card_class}">
            <div class="radar-title">
                <span>{icon} 异动背离研判: <strong>{div_label}</strong></span>
                <span class="radar-badge" style="{badge_style}">风险等级: {risk_label}</span>
            </div>
            <div style="font-size: 0.875rem; color: #374151; margin-top: 0.5rem; line-height: 1.6;">
                <strong>研判推导依据：</strong>{ref.reflection_narrative}
            </div>
            <div style="margin-top: 0.75rem; padding: 0.6rem 0.8rem; background: rgba(0,0,0,0.03); border-radius: 12px; font-size: 0.825rem; color: #4B5563;">
                💡 <strong>操作风控提示：</strong>{ref.action_suggestion}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 3. 散户语料样本与大模型消歧明细
    st.markdown("### 🔍 散户语料明细与大模型反思消歧")
    for idx, item in enumerate(state.sentiment_list):
        raw_val = str(getattr(item.stance, "value", item.stance)).lower()
        if "bull" in raw_val or "多" in raw_val:
            display_stance = "看多 (Bullish)"
            stance_color = "#DC2626"
            stance_bg = "#FEE2E2"
        elif "bear" in raw_val or "空" in raw_val:
            display_stance = "看空 (Bearish)"
            stance_color = "#059669"
            stance_bg = "#D1FAE5"
        else:
            display_stance = "中性 (Neutral)"
            stance_color = "#4B5563"
            stance_bg = "#F3F4F6"

        slang_html = "".join([f'<span class="slang-chip">#{s}</span>' for s in item.slang_detected]) if item.slang_detected else '<span style="color: #9CA3AF; font-size: 0.75rem;">无黑话</span>'
        sarcasm_html = '<span class="sarcasm-tag">🔥 识别到反讽语义翻转</span>' if item.is_sarcasm else ''

        post_content = getattr(item, "raw_title", None) or getattr(item, "original_post", None) or f"股吧散户讨论语料 #{idx + 1}"

        st.markdown(f"""
        <div class="post-bubble">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <div>
                    <span style="background: {stance_bg}; color: {stance_color}; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 9999px; margin-right: 0.5rem;">
                        {display_stance}
                    </span>
                    {sarcasm_html}
                    {slang_html}
                </div>
                <div style="font-family: monospace; font-size: 0.8rem; font-weight: 600; color: #4B5563;">
                    情绪分值: <span style="color: {'#DC2626' if item.sentiment_score >= 0 else '#059669'}">{item.sentiment_score:+.2f}</span>
                </div>
            </div>
            <div style="font-size: 0.875rem; color: #1F2937; margin: 0.5rem 0; padding-left: 0.75rem; border-left: 3px solid #E5E7EB; font-style: italic;">
                “{post_content}”
            </div>
            <div style="font-size: 0.775rem; color: #6B7280; margin-top: 0.4rem;">
                🧠 <strong>思维链判定依据：</strong>{item.reasoning}
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("👈 请在左侧侧边栏配置股票代码与参数，点击「启动智能反思研判」，或者直接双击打开 `frontend/index.html` 体验纯正的 Gemini 原生交互界面。")
