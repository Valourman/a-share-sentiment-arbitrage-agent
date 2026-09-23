import streamlit as st
import re
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState

# ============================================================
# 1. 页面基础配置 (Gemini 沉浸式风格)
# ============================================================
st.set_page_config(
    page_title="A-Share Sentiment Agent · Google Gemini",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 2. Google Gemini 顶级高定全局 CSS 注入
# ============================================================
GEMINI_NATIVE_CSS = """
<style>
/* 引入 Google 现代设计系统字体 */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    background-color: #F8FAFD !important;
    color: #1F1F1F !important;
}

/* 隐藏 Streamlit 自带的顶栏白条与页脚 */
header[data-testid="stHeader"] {
    background-color: rgba(248, 250, 253, 0.8) !important;
    backdrop-filter: blur(12px) !important;
}
footer { visibility: hidden !important; }

/* 居中视口约束 (Max-width 920px)，消除超宽屏阅读疲劳 */
.main .block-container {
    max-width: 920px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 7rem !important;
}

/* 左侧折叠侧边栏 (Gemini Collapsible Rail) */
[data-testid="stSidebar"] {
    background-color: #F0F4F9 !important;
    border-right: 1px solid rgba(0, 0, 0, 0.05) !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.5rem !important;
}

/* Gemini 顶栏标题样式 */
.gemini-app-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.gemini-app-title {
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #4285F4 0%, #9B72CF 50%, #D96570 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.gemini-chip-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.65rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    background: rgba(0, 0, 0, 0.04);
    color: #5F6368;
}

/* 欢迎 Hero 卡片 */
.welcome-container {
    text-align: center;
    padding: 3rem 1rem 2rem 1rem;
}
.welcome-sparkle-icon {
    width: 3.5rem;
    height: 3.5rem;
    margin: 0 auto 1.25rem auto;
    border-radius: 1.25rem;
    background: linear-gradient(135deg, #4285F4 0%, #9B72CF 50%, #D96570 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.75rem;
    box-shadow: 0 10px 25px rgba(66, 133, 244, 0.25);
}
.welcome-title {
    font-size: 2.25rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #4285F4 0%, #6366F1 50%, #9B72CF 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.75rem;
}
.welcome-desc {
    color: #5F6368;
    font-size: 0.95rem;
    max-width: 580px;
    margin: 0 auto 2rem auto;
    line-height: 1.6;
}

/* 用户提问气泡 */
.user-msg-bubble {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1.75rem;
}
.user-msg-content {
    background-color: #F0F4F9;
    color: #1F1F1F;
    padding: 0.85rem 1.35rem;
    border-radius: 1.5rem;
    max-width: 80%;
    font-size: 0.9rem;
    line-height: 1.6;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

/* Gemini AI 回复容器 */
.gemini-ai-container {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    margin-bottom: 1.5rem;
}
.gemini-sparkle-avatar {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 9999px;
    background: linear-gradient(135deg, #4285F4 0%, #9B72CF 50%, #D96570 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.1rem;
    box-shadow: 0 4px 12px rgba(66, 133, 244, 0.2);
    flex-shrink: 0;
    margin-top: 0.25rem;
}

/* 四宫格盘面行情卡片 (Surface Elevation) */
.market-chips-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.25rem;
}
@media (max-width: 640px) {
    .market-chips-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
.market-chip-card {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.05);
    border-radius: 1.25rem;
    padding: 0.9rem 1rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.market-chip-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
}
.chip-label {
    font-size: 0.72rem;
    color: #70757A;
    margin-bottom: 0.25rem;
}
.chip-value {
    font-size: 1.25rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.chip-sub {
    font-size: 0.72rem;
    font-weight: 600;
    margin-top: 0.15rem;
}

/* 背离研判雷达警报卡片 */
.radar-banner {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 1.5rem;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    position: relative;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}
.radar-banner.divergent {
    border-color: rgba(239, 68, 68, 0.25);
    background: linear-gradient(135deg, rgba(254, 242, 242, 0.5) 0%, #FFFFFF 100%);
}
.radar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}
.radar-status {
    font-size: 0.95rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.radar-badge {
    padding: 0.2rem 0.65rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

/* 资讯卡片与散户发帖独立卡片 */
.info-card {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.05);
    border-radius: 1.25rem;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    transition: all 0.2s ease;
}
.info-card:hover {
    background: #FAFCFE;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.03);
}
.slang-pill {
    display: inline-block;
    background: #F1F3F4;
    color: #4B5563;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    padding: 0.15rem 0.45rem;
    border-radius: 6px;
    margin-right: 0.35rem;
}
.sarcasm-pill {
    display: inline-flex;
    align-items: center;
    background: #FEF3C7;
    color: #92400E;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 9999px;
    margin-right: 0.35rem;
}

/* 底部悬浮复合输入舱 (Chat Input) */
[data-testid="stChatInput"] {
    border-radius: 9999px !important;
    border: 1px solid rgba(0, 0, 0, 0.1) !important;
    background: rgba(255, 255, 255, 0.9) !important;
    backdrop-filter: blur(20px) !important;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.06) !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 0.9rem !important;
}
[data-testid="stChatInput"] button {
    background: linear-gradient(135deg, #4285F4 0%, #6366F1 100%) !important;
    color: white !important;
    border-radius: 9999px !important;
    border: none !important;
}

/* 侧边栏按钮样式 */
[data-testid="stSidebar"] .stButton button {
    border-radius: 9999px !important;
    border: 1px solid rgba(0, 0, 0, 0.06) !important;
    background: #FFFFFF !important;
    color: #374151 !important;
    font-size: 0.825rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.5rem 1rem !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    transition: all 0.2s ease !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #F8FAFD !important;
    border-color: #4285F4 !important;
    color: #4285F4 !important;
    transform: translateY(-1px) !important;
}

/* Streamlit Tabs 切换美化 */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9999px !important;
    padding: 0.4rem 1rem !important;
    font-size: 0.825rem !important;
    font-weight: 500 !important;
    background-color: transparent !important;
}
.stTabs [aria-selected="true"] {
    background-color: #E8F0FE !important;
    color: #1A73E8 !important;
    font-weight: 600 !important;
}
</style>
"""
st.markdown(GEMINI_NATIVE_CSS, unsafe_allow_html=True)

# ============================================================
# 3. Session State 管理
# ============================================================
if "active_state" not in st.session_state:
    st.session_state.active_state = None
if "current_stock" not in st.session_state:
    st.session_state.current_stock = None

# ============================================================
# 4. 左侧折叠侧边栏 (Gemini Rail 规范)
# ============================================================
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0.25rem 1rem 0.25rem;">
        <span style="font-weight: 700; font-size: 1.15rem; background: linear-gradient(135deg, #4285F4, #9B72CF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Gemini</span>
        <span style="font-size: 0.7rem; padding: 0.15rem 0.5rem; background: #DBEAFE; color: #1D4ED8; border-radius: 9999px; font-weight: 600;">Pro</span>
    </div>
    """, unsafe_allow_html=True)

    if st.button("✨ 发起新标的研判", use_container_width=True):
        st.session_state.active_state = None
        st.session_state.current_stock = None
        st.rerun()

    st.markdown("<div style='font-size: 0.72rem; color: #9CA3AF; font-weight: 600; text-transform: uppercase; margin: 1rem 0 0.5rem 0.25rem;'>快速切换标的</div>", unsafe_allow_html=True)

    preset_stocks = [
        ("600584", "长电科技 · 散户恐慌割肉背离"),
        ("600667", "太极实业 · 半导体概念异动"),
        ("600519", "贵州茅台 · 散户反讽消歧研判"),
        ("002594", "比亚迪 · 盘面情绪量价共振"),
        ("601127", "赛力斯 · 智选车诱多识别"),
    ]

    for code, label in preset_stocks:
        if st.button(f"🕒 {label}", key=f"btn_{code}", use_container_width=True):
            st.session_state.current_stock = code
            with st.spinner(f"Agent 正在多方位并发采集 [{code}] 全量股吧、主流新闻与盘面..."):
                agent = SentimentArbitrageAgent()
                # 默认全量最大深度 (max_posts=30)，并聚合多源资讯
                state = agent.run(stock_code=code, max_posts=30, use_llm=True)
                st.session_state.active_state = state
            st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="font-size: 0.75rem; color: #6B7280; line-height: 1.5; padding: 0.25rem;">
        ⚡ <strong>分析策略</strong>：全量最大化深度（自动抓取该页全部真实散户发帖）<br>
        🌐 <strong>多源情报</strong>：股吧全量 + 专业财经新闻 + 官方披露公告 + 秒级 L1 盘面
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# 5. 顶栏极简 App Bar
# ============================================================
st.markdown("""
<div class="gemini-app-bar">
    <div class="gemini-app-title">
        ✨ A-Share Sentiment Agent
    </div>
    <div class="gemini-chip-badge">
        🌐 多源情报网：东财全量股吧 + 新浪财经资讯 + 官方权威公告 + 秒级 L1 盘面
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 6. 处理底部悬浮输入舱的指令提交 (Chat Input)
# ============================================================
user_input = st.chat_input("输入 6 位 A 股股票代码 (如 600667, 600584) 启动多源全景智能研判...")

if user_input:
    code_match = re.search(r"\b(\d{6})\b", user_input)
    target_code = code_match.group(1) if code_match else user_input.strip()

    st.session_state.current_stock = target_code
    with st.spinner(f"Agent 正在多方位全量采集 [{target_code}] 股吧、新闻与盘面，并启动大模型多步反思..."):
        try:
            agent = SentimentArbitrageAgent()
            # 默认全量最大深度 (max_posts=30)
            state = agent.run(stock_code=target_code, max_posts=30, use_llm=True)
            st.session_state.active_state = state
        except Exception as e:
            st.error(f"Agent 研判异常: {e}")
    st.rerun()

# ============================================================
# 7. 主视口内容区：空态欢迎 vs 多源研判结果排版
# ============================================================
state: AgentState = st.session_state.active_state

if not state:
    # ---------------- 空态：Gemini 经典居中 Hero ----------------
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-sparkle-icon">✨</div>
        <div class="welcome-title">你好，投资研究员</div>
        <div class="welcome-desc">
            基于 Google Gemini 设计系统的金融多源研判智能体。不设散户分析深度限制，默认全量捕获股吧舆情，并并行汇聚主流专业资讯与官方披露，与秒级真实盘面交叉验证。
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📈 **长电科技 (600584)**\n\n半导体封测龙头：全量散户情绪与日内盘面多维背离分析", key="hero_600584", use_container_width=True):
            st.session_state.current_stock = "600584"
            with st.spinner("正在多方位全量研判长电科技..."):
                st.session_state.active_state = SentimentArbitrageAgent().run("600584", max_posts=30, use_llm=True)
            st.rerun()

        if st.button("🚗 **比亚迪 (002594)**\n\n新能源汽车龙头：多源验证散户全量情绪与专业机构资讯共振", key="hero_002594", use_container_width=True):
            st.session_state.current_stock = "002594"
            with st.spinner("正在多方位全量研判比亚迪..."):
                st.session_state.active_state = SentimentArbitrageAgent().run("002594", max_posts=30, use_llm=True)
            st.rerun()

    with col2:
        if st.button("🏢 **太极实业 (600667)**\n\n半导体工程龙头：全量散户黑话反讽消歧与盘面资金博弈特征", key="hero_600667", use_container_width=True):
            st.session_state.current_stock = "600667"
            with st.spinner("正在多方位全量研判太极实业..."):
                st.session_state.active_state = SentimentArbitrageAgent().run("600667", max_posts=30, use_llm=True)
            st.rerun()

        if st.button("🍶 **贵州茅台 (600519)**\n\n白酒消费核心资产：深度剖析全量股吧散户悲喜情绪与官方公告", key="hero_600519", use_container_width=True):
            st.session_state.current_stock = "600519"
            with st.spinner("正在多方位全量研判贵州茅台..."):
                st.session_state.active_state = SentimentArbitrageAgent().run("600519", max_posts=30, use_llm=True)
            st.rerun()

else:
    # ---------------- 研判结果态：Gemini 多源立体排版 ----------------
    st.markdown(f"""
    <div class="user-msg-bubble">
        <div class="user-msg-content">
            启动标的 <strong style="color: #2563EB;">[{state.stock_name} ({state.stock_code})]</strong> 的全量散户情绪消歧、主流资讯整合与多方位异动背离研判。
        </div>
    </div>
    """, unsafe_allow_html=True)

    price = state.market_data.current_price if state.market_data else 0.0
    chg = state.market_data.change_percent if state.market_data else 0.0
    turnover = state.market_data.turnover_amount_yi if state.market_data else 0.0
    sentiment = state.average_sentiment
    is_up = chg >= 0
    chg_color = "#DC2626" if is_up else "#059669"
    sentiment_color = "#DC2626" if sentiment >= 0 else "#059669"

    st.markdown(f"""
    <div class="gemini-ai-container">
        <div class="gemini-sparkle-avatar">✨</div>
        <div style="flex: 1; overflow: hidden;">
            <!-- 四宫格盘面行情芯片 -->
            <div class="market-chips-grid">
                <div class="market-chip-card">
                    <div class="chip-label">分析标的</div>
                    <div class="chip-value" style="font-size: 1.1rem; color: #1F2937;">{state.stock_name}</div>
                    <div style="font-size: 0.72rem; color: #6B7280; font-family: monospace;">{state.stock_code}</div>
                </div>
                <div class="market-chip-card">
                    <div class="chip-label">实时成交价</div>
                    <div class="chip-value" style="color: {chg_color};">{price:.2f} 元</div>
                    <div class="chip-sub" style="color: {chg_color};">{'▲ +' if is_up else '▼ '}{chg:.2f}%</div>
                </div>
                <div class="market-chip-card">
                    <div class="chip-label">今日成交量能</div>
                    <div class="chip-value" style="color: #1F2937;">{turnover:.2f} 亿</div>
                    <div style="font-size: 0.72rem; color: #6B7280;">主力资金博弈</div>
                </div>
                <div class="market-chip-card">
                    <div class="chip-label">全样本散户情绪分</div>
                    <div class="chip-value" style="color: {sentiment_color};">{'+' if sentiment > 0 else ''}{sentiment:.2f}</div>
                    <div style="font-size: 0.72rem; color: #6B7280;">全量样本: {len(state.sentiment_list)} 条</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 背离研判雷达警报卡片
    ref = state.reflection
    if ref:
        div_label = getattr(ref.divergence_type, "value", str(ref.divergence_type))
        risk_label = getattr(ref.risk_level, "value", str(ref.risk_level))
        is_div = ref.is_divergent
        radar_class = "radar-banner divergent" if is_div else "radar-banner"
        badge_bg = "#FEE2E2" if is_div else "#D1FAE5"
        badge_text = "#B91C1C" if is_div else "#065F46"
        icon = "🚨" if is_div else "✅"

        st.markdown(f"""
        <div class="{radar_class}">
            <div class="radar-header">
                <div class="radar-status">
                    <span>{icon}</span>
                    <span>多源异动背离研判: {div_label}</span>
                </div>
                <span class="radar-badge" style="background: {badge_bg}; color: {badge_text};">
                    风险等级: {risk_label}
                </span>
            </div>
            <div style="font-size: 0.875rem; color: #374151; line-height: 1.6; margin-bottom: 0.75rem;">
                <strong>多维因果推导逻辑：</strong>{ref.reflection_narrative}
            </div>
            <div style="padding: 0.65rem 0.85rem; background: rgba(0,0,0,0.03); border-radius: 0.75rem; font-size: 0.8rem; color: #4B5563;">
                💡 <strong>交易策略与风控提示：</strong>{ref.action_suggestion}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Gemini 思维链展开抽屉
    with st.expander("🤖 Gemini 大模型多源思维链语义推理过程 (4 个步骤)"):
        st.markdown(f"""
        - **第一步 [客观行情事实]**：提取实时现价 **{price:.2f} 元**，日内变动 **{chg:+.2f}%**，成交量能 **{turnover:.2f} 亿元**。
        - **第二步 [多方位信息聚合]**：无限制抓取东方财富股吧全部 **{len(state.sentiment_list)} 条有效原帖**，并同步比对新浪主流新闻与官方公告。
        - **第三步 [深度反讽消歧与博弈反思]**：大模型消除『赢麻了』『抬轿子』等网络倒装反语，综合情绪值定格在 **{sentiment:+.2f}**，对比盘面判定背离类型。
        - **第四步 [Pydantic V2 契约决策自愈]**：通过严格模式结构校验，生成交易防御建议。
        """)

    # ============================================================
    # 8. 多源情报分区展示 Tabs (Gemini 沉浸式标签页)
    # ============================================================
    tab_guba, tab_news, tab_ann = st.tabs([
        f"💬 股吧全量散户语料消歧 ({len(state.sentiment_list)} 条样本)",
        f"📰 主流专业财经资讯与主力动向 ({len(state.news_list)} 篇)",
        f"📢 上市公司官方披露公告 ({len(state.announcements)} 份)"
    ])

    with tab_guba:
        st.markdown("<div style='font-size: 0.8rem; color: #6B7280; margin-bottom: 0.75rem;'>自动抓取该页全部真实散户发帖，已剔除 70%+ 水军广告并消除反讽语义翻转：</div>", unsafe_allow_html=True)
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

            slang_html = "".join([f'<span class="slang-pill">#{s}</span>' for s in item.slang_detected]) if item.slang_detected else '<span style="color: #9CA3AF; font-size: 0.7rem;">无特殊黑话</span>'
            sarcasm_html = '<span class="sarcasm-pill">🔥 识别到反讽语义翻转</span>' if item.is_sarcasm else ''

            post_content = getattr(item, "raw_title", None) or f"股吧散户讨论语料 #{idx + 1}"

            st.markdown(f"""
            <div class="info-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                    <div>
                        <span style="background: {stance_bg}; color: {stance_color}; font-size: 0.72rem; font-weight: 600; padding: 0.15rem 0.55rem; border-radius: 9999px; margin-right: 0.5rem;">
                            {display_stance}
                        </span>
                        {sarcasm_html}
                        {slang_html}
                    </div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; font-weight: 600; color: #6B7280;">
                        情绪分值: <span style="color: {'#DC2626' if item.sentiment_score >= 0 else '#059669'};">{item.sentiment_score:+.2f}</span>
                    </div>
                </div>
                <div style="font-size: 0.875rem; color: #1F2937; margin: 0.4rem 0; padding-left: 0.75rem; border-left: 3px solid #E5E7EB; font-style: italic;">
                    “{post_content}”
                </div>
                <div style="font-size: 0.75rem; color: #6B7280;">
                    🧠 <strong>大模型消歧依据：</strong>{item.reasoning}
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab_news:
        if state.news_list:
            for n_idx, news in enumerate(state.news_list):
                link_html = f'<a href="{news.url}" target="_blank" style="color: #1A73E8; text-decoration: none; font-size: 0.8rem; margin-left: 0.5rem;">查看原文 ↗</a>' if news.url else ''
                st.markdown(f"""
                <div class="info-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                        <span style="font-size: 0.72rem; padding: 0.15rem 0.5rem; background: #E0F2FE; color: #0369A1; border-radius: 9999px; font-weight: 600;">
                            {news.source}
                        </span>
                        <span style="font-size: 0.75rem; color: #9CA3AF;">#{n_idx + 1} 实时财经资讯</span>
                    </div>
                    <div style="font-size: 0.9rem; font-weight: 600; color: #1F2937; line-height: 1.5;">
                        {news.title} {link_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暂未获取到该标的日内专业新闻资讯。")

    with tab_ann:
        if state.announcements:
            for a_idx, ann in enumerate(state.announcements):
                link_html = f'<a href="{ann.url}" target="_blank" style="color: #1A73E8; text-decoration: none; font-size: 0.8rem; margin-left: 0.5rem;">官方查阅 ↗</a>' if ann.url else ''
                st.markdown(f"""
                <div class="info-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                        <span style="font-size: 0.72rem; padding: 0.15rem 0.5rem; background: #FEF3C7; color: #92400E; border-radius: 9999px; font-weight: 600;">
                            上市公司法定披露
                        </span>
                        <span style="font-size: 0.75rem; color: #9CA3AF;">权威公告</span>
                    </div>
                    <div style="font-size: 0.9rem; font-weight: 600; color: #1F2937; line-height: 1.5;">
                        {ann.title} {link_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暂未获取到该标的近期官方公告。")
