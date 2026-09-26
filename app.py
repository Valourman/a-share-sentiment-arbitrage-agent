import streamlit as st
import re
import textwrap
from src.agent.engine import SentimentArbitrageAgent
from src.agent.conversational import ConversationalArbitrageAgent
from src.agent.state import AgentState, DivergenceType
from src.agent.decision import has_valid_market_snapshot
from src.core.config import AgentConfig, global_config
from src.core.llm import HelloAgentsLLM

# ============================================================
# 1. 页面基础配置 (Gemini 沉浸式风格)
# ============================================================
st.set_page_config(
    page_title="A-Share Sentiment Agent · Google Gemini",
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
.status-indicator-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
    vertical-align: middle;
    margin-right: 6px;
}
.status-indicator-dot.alert {
    background-color: #DC2626;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.2);
}
.status-indicator-dot.normal {
    background-color: #059669;
    box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.2);
}
.info-label-tag {
    display: inline-block;
    background: #E5E7EB;
    color: #374151;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    margin-right: 0.3rem;
}

/* 多智能体多空辩论卡片 (对标 TradingAgents / FinRobot) */
.debate-box {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 1.25rem;
    padding: 1.25rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
}
.debate-col-bull {
    background: linear-gradient(180deg, rgba(254, 242, 242, 0.6) 0%, #FFFFFF 100%);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 1rem;
    padding: 1rem;
}
.debate-col-bear {
    background: linear-gradient(180deg, rgba(240, 253, 244, 0.6) 0%, #FFFFFF 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 1rem;
    padding: 1rem;
}
.catalyst-card {
    background: #FFFFFF;
    border: 1px solid rgba(0, 0, 0, 0.05);
    border-radius: 1rem;
    padding: 0.85rem 1rem;
    margin-bottom: 0.6rem;
}

/* 结构化消歧日志终端容器 (Log Terminal) */
.log-terminal {
    background-color: #0F172A;
    color: #E2E8F0;
    border-radius: 0.85rem;
    padding: 1.1rem 1.35rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem;
    line-height: 1.65;
    max-height: 480px;
    overflow-y: auto;
    border: 1px solid #1E293B;
    box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.35);
}
.log-terminal-line {
    margin-bottom: 0.45rem;
    word-break: break-all;
}
.log-tag-info {
    color: #38BDF8;
    font-weight: 600;
}
.log-tag-disambiguate {
    color: #C084FC;
    font-weight: 600;
}
.log-tag-fact {
    color: #34D399;
    font-weight: 600;
}
.log-tag-decision {
    color: #FBBF24;
    font-weight: 600;
}
.log-tag-reasoning {
    color: #94A3B8;
}

/* 卡片内嵌消歧日志折叠器 */
.disambiguation-details {
    margin-top: 0.4rem;
    border-top: 1px dashed #E5E7EB;
    padding-top: 0.35rem;
}
.disambiguation-details summary {
    cursor: pointer;
    font-size: 0.74rem;
    font-weight: 500;
    color: #6B7280;
    user-select: none;
    transition: color 0.15s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
}
.disambiguation-details summary:hover {
    color: #1A73E8;
}
.disambiguation-details[open] summary {
    color: #1A73E8;
    margin-bottom: 0.35rem;
}
.disambiguation-log-box {
    background: #F8FAFC;
    border-left: 3px solid #3B82F6;
    border-radius: 0 0.5rem 0.5rem 0;
    padding: 0.5rem 0.75rem;
    font-size: 0.74rem;
    color: #334155;
    line-height: 1.55;
    font-family: 'JetBrains Mono', monospace;
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

/* 侧边栏折叠面板与表单输入控件美化 */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid rgba(0, 0, 0, 0.08) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.5rem !important;
    overflow: hidden !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: #374151 !important;
    padding: 0.55rem 0.8rem !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0.5rem 0.8rem 0.8rem 0.8rem !important;
}
[data-testid="stSidebar"] .stTextInput input, [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
    border-radius: 8px !important;
    font-size: 0.8rem !important;
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
# 3. Session State 管理与全局辅助函数
# ============================================================
if "active_state" not in st.session_state:
    st.session_state.active_state = None
if "current_stock" not in st.session_state:
    st.session_state.current_stock = None
if "trace_summary" not in st.session_state:
    st.session_state.trace_summary = None
if "trace_spans" not in st.session_state:
    st.session_state.trace_spans = []
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "📊 标的研判"
if "chat_agent" not in st.session_state:
    st.session_state.chat_agent = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "settings" not in st.session_state:
    st.session_state.settings = {
        "api_key": global_config.openai_api_key or "",
        "base_url": global_config.openai_base_url or "",
        "model_name": global_config.default_model or "gpt-4o-mini",
        "temperature": float(global_config.temperature if global_config.temperature is not None else 0.1),
        "max_posts": 30,
        "use_llm": True,
        "workflow_mode": True,
        "timeout_seconds": float(global_config.timeout_seconds if global_config.timeout_seconds is not None else 30.0),
    }


def run_configured_agent(stock_code: str):
    """根据当前会话动态设置构造 LLM 与 Agent 并执行研判，附带实时动态进度条"""
    st.session_state.current_stock = stock_code
    settings = st.session_state.settings
    config = AgentConfig(
        openai_api_key=settings["api_key"].strip() if settings["api_key"].strip() else None,
        openai_base_url=settings["base_url"].strip() if settings["base_url"].strip() else None,
        default_model=settings["model_name"].strip() if settings["model_name"].strip() else "gpt-4o-mini",
        temperature=float(settings["temperature"]),
        timeout_seconds=float(settings["timeout_seconds"]),
    )
    llm = HelloAgentsLLM(config=config)
    agent = SentimentArbitrageAgent(llm=llm)

    # 动态进度条挂载
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0.05, text=f"Agent 启动中：准备多源全景研判 [{stock_code}]...")

    def on_progress(val: float, desc: str):
        try:
            progress_bar.progress(min(max(float(val), 0.0), 1.0), text=desc)
        except Exception:
            pass

    try:
        state = agent.run(
            stock_code=stock_code,
            max_posts=int(settings["max_posts"]),
            use_llm=bool(settings["use_llm"]),
            workflow_mode=bool(settings.get("workflow_mode", True)),
            progress_callback=on_progress,
        )
        st.session_state.active_state = state
        st.session_state.trace_summary = agent.tracer.get_summary()
        st.session_state.trace_spans = [
            {
                "环节": s.name,
                "类型": s.span_type,
                "耗时 (s)": s.duration,
                "状态": "✅ 成功" if s.status == "success" else f"❌ {s.error or '失败'}",
            }
            for s in agent.tracer.spans
        ]
        return state
    finally:
        progress_placeholder.empty()


# ============================================================
# 4. 左侧折叠侧边栏 (Gemini Rail 规范)
# ============================================================
with st.sidebar:
    sidebar_brand_html = """
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0.25rem 1rem 0.25rem;">
        <span style="font-weight: 700; font-size: 1.15rem; background: linear-gradient(135deg, #4285F4, #9B72CF); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Gemini</span>
        <span style="font-size: 0.7rem; padding: 0.15rem 0.5rem; background: #DBEAFE; color: #1D4ED8; border-radius: 9999px; font-weight: 600;">Pro</span>
    </div>
    """
    st.markdown(textwrap.dedent(sidebar_brand_html).strip(), unsafe_allow_html=True)

    st.session_state.app_mode = st.radio(
        "工作模式",
        options=["📊 标的研判", "💬 对话问答"],
        index=0 if st.session_state.app_mode == "📊 标的研判" else 1,
        horizontal=True,
        label_visibility="collapsed",
    )

    if st.button("发起新标的研判", use_container_width=True):
        st.session_state.active_state = None
        st.session_state.current_stock = None
        st.session_state.trace_summary = None
        st.session_state.trace_spans = []
        st.rerun()

    # 系统与模型设置折叠面板
    with st.expander("系统与模型设置", expanded=False):
        st.markdown("<div style='font-size: 0.72rem; color: #4B5563; font-weight: 600; margin-bottom: 0.25rem;'>大模型接入配置</div>", unsafe_allow_html=True)
        cur_s = st.session_state.settings

        new_api_key = st.text_input(
            "API Key",
            value=cur_s["api_key"],
            type="password",
            placeholder="留空则读取环境变量 OPENAI_API_KEY",
            help="OpenAI 或兼容服务商 API 密钥",
        )
        new_base_url = st.text_input(
            "Base URL",
            value=cur_s["base_url"],
            placeholder="如 https://api.openai.com/v1",
            help="模型服务端点 Base URL",
        )

        preset_models = ["gpt-4o-mini", "gpt-4o", "deepseek-chat", "qwen-plus", "自定义"]
        model_idx = 0
        if cur_s["model_name"] in preset_models[:-1]:
            model_idx = preset_models.index(cur_s["model_name"])
        elif cur_s["model_name"]:
            model_idx = len(preset_models) - 1

        selected_model = st.selectbox(
            "选择模型",
            options=preset_models,
            index=model_idx,
        )
        if selected_model == "自定义":
            model_name = st.text_input("自定义模型名", value=cur_s["model_name"])
        else:
            model_name = selected_model

        temperature = st.slider(
            "采样温度 (Temperature)",
            min_value=0.0,
            max_value=1.0,
            value=float(cur_s["temperature"]),
            step=0.05,
            help="较低值输出更收敛确定，较高值更发散",
        )

        st.markdown("<div style='font-size: 0.72rem; color: #4B5563; font-weight: 600; margin: 0.5rem 0 0.25rem 0;'>情报与策略配置</div>", unsafe_allow_html=True)
        max_posts = st.slider(
            "最大抓取帖数",
            min_value=10,
            max_value=60,
            value=int(cur_s["max_posts"]),
            step=5,
            help="单次从股吧抓取的最大帖子条数",
        )
        use_llm = st.toggle(
            "启用大模型反思消歧",
            value=bool(cur_s["use_llm"]),
            help="关闭后仅做规则匹配，开启后调用大模型进行反讽消歧与多步反思",
        )
        workflow_mode = st.toggle(
            "多智能体工作流流水线",
            value=bool(cur_s.get("workflow_mode", True)),
            help="启用对标 TradingAgents/FinRobot 的并发感知、基本面催化挖掘与多空多智能体辩论 (Bull vs Bear Debate)",
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("保存设置", key="btn_save_settings", use_container_width=True):
                st.session_state.settings.update({
                    "api_key": new_api_key.strip(),
                    "base_url": new_base_url.strip(),
                    "model_name": model_name.strip() if model_name else "gpt-4o-mini",
                    "temperature": temperature,
                    "max_posts": max_posts,
                    "use_llm": use_llm,
                    "workflow_mode": workflow_mode,
                })
                st.success("配置已更新生效")
                st.rerun()
        with c2:
            if st.button("恢复默认", key="btn_reset_settings", use_container_width=True):
                st.session_state.settings = {
                    "api_key": global_config.openai_api_key or "",
                    "base_url": global_config.openai_base_url or "",
                    "model_name": global_config.default_model or "gpt-4o-mini",
                    "temperature": float(global_config.temperature if global_config.temperature is not None else 0.1),
                    "max_posts": 30,
                    "use_llm": True,
                    "workflow_mode": True,
                    "timeout_seconds": float(global_config.timeout_seconds if global_config.timeout_seconds is not None else 30.0),
                }
                    "base_url": global_config.openai_base_url or "",
                    "model_name": global_config.default_model or "gpt-4o-mini",
                    "temperature": float(global_config.temperature if global_config.temperature is not None else 0.1),
                    "max_posts": 30,
                    "use_llm": True,
                    "timeout_seconds": float(global_config.timeout_seconds if global_config.timeout_seconds is not None else 30.0),
                }
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
        if st.button(label, key=f"btn_{code}", use_container_width=True):
            with st.spinner(f"Agent 正在多方位并发采集 [{code}] 全量股吧、主流新闻与盘面..."):
                run_configured_agent(code)
            st.rerun()

    cur_m = st.session_state.settings["model_name"]
    cur_p = st.session_state.settings["max_posts"]
    cur_llm = "开启" if st.session_state.settings["use_llm"] else "关闭"
    st.markdown("---")
    sidebar_info_html = f"""
    <div style="font-size: 0.75rem; color: #6B7280; line-height: 1.6; padding: 0.25rem;">
        <span class="info-label-tag">模型</span> <strong>当前模型</strong>：{cur_m}<br>
        <span class="info-label-tag">策略</span> <strong>分析深度</strong>：{cur_p} 条 (反思消歧: {cur_llm})<br>
        <span class="info-label-tag">信源</span> <strong>多源覆盖</strong>：股吧全量 + 专业财经新闻 + 官方披露公告 + 秒级 L1 盘面
    </div>
    """
    st.markdown(textwrap.dedent(sidebar_info_html).strip(), unsafe_allow_html=True)

# ============================================================
# 5. 顶栏极简 App Bar
# ============================================================
st.markdown("""
<div class="gemini-app-bar">
    <div class="gemini-app-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="vertical-align: -2px; margin-right: 6px;">
            <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="url(#titleGrad)"/>
            <defs>
                <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#4285F4"/>
                    <stop offset="50%" stop-color="#9B72CF"/>
                    <stop offset="100%" stop-color="#D96570"/>
                </linearGradient>
            </defs>
        </svg>
        A-Share Sentiment Agent
    </div>
    <div class="gemini-chip-badge">
        多源情报网：东财全量股吧 · 新浪财经资讯 · 官方权威公告 · 秒级 L1 盘面
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 6. 处理底部悬浮输入舱的指令提交 (Chat Input, 仅研判模式)
# ============================================================
if st.session_state.app_mode == "📊 标的研判":
    user_input = st.chat_input("输入 6 位 A 股股票代码 (如 600667, 600584) 启动多源全景智能研判...")

    if user_input:
        code_match = re.search(r"\b(\d{6})\b", user_input)
        target_code = code_match.group(1) if code_match else user_input.strip()

        with st.spinner(f"Agent 正在多方位全量采集 [{target_code}] 股吧、新闻与盘面，并启动大模型多步反思..."):
            try:
                run_configured_agent(target_code)
            except Exception as e:
                st.error(f"Agent 研判异常: {e}")
        st.rerun()

# ============================================================
# 7. 主视口内容区：空态欢迎 vs 多源研判结果排版
# ============================================================
state: AgentState = st.session_state.active_state

if st.session_state.app_mode == "💬 对话问答":
    # ---------------- 对话问答模式：ConversationalArbitrageAgent 多轮交互 ----------------
    st.markdown("""
    <div style="text-align: center; padding: 1.5rem 1rem 1rem 1rem;">
        <div style="font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; background: linear-gradient(135deg, #4285F4 0%, #9B72CF 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;">对话式研判助手</div>
        <div style="color: #5F6368; font-size: 0.85rem; max-width: 560px; margin: 0 auto; line-height: 1.6;">
            直接输入股票名称（如"太极实业"、"长电科技"）或 6 位代码触发全流程研判，支持多轮追问、买卖咨询、归因剖析与金融概念科普。
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.chat_agent is None:
        with st.spinner("正在初始化对话式智能体 (System 1 + System 2 双脑架构)..."):
            st.session_state.chat_agent = ConversationalArbitrageAgent()
    chat_agent = st.session_state.chat_agent

    # 历史消息回放
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 提问表单 (回车即提交)
    with st.form("chat_form", clear_on_submit=True):
        question = st.text_input(
            "提问",
            placeholder="例如：看看太极实业如何？/ 它现在能抄底吗？/ 什么是多头诱多陷阱？",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("发送", use_container_width=True)

    if submitted and question.strip():
        with st.spinner("Agent 正在思考并实时检索舆情与盘面..."):
            try:
                res = chat_agent.chat(question.strip())
                reply = res.reply_text
            except Exception as e:
                reply = f"对话引擎暂时异常：{e}"
        st.session_state.chat_history.append({"role": "user", "content": question.strip()})
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

    if st.session_state.chat_history:
        if st.button("🧹 清空对话与焦点记忆", use_container_width=False):
            chat_agent.clear_memory()
            st.session_state.chat_history = []
            st.rerun()

elif not state:
    # ---------------- 空态：Gemini 经典居中 Hero ----------------
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-sparkle-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
                <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z"/>
            </svg>
        </div>
        <div class="welcome-title">你好，投资研究员</div>
        <div class="welcome-desc">
            基于 Google Gemini 设计系统的金融多源研判智能体。不设散户分析深度限制，默认全量捕获股吧舆情，并并行汇聚主流专业资讯与官方披露，与秒级真实盘面交叉验证。
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("**长电科技 (600584)**\n\n半导体封测龙头：全量散户情绪与日内盘面多维背离分析", key="hero_600584", use_container_width=True):
            with st.spinner("正在多方位全量研判长电科技..."):
                run_configured_agent("600584")
            st.rerun()

        if st.button("**比亚迪 (002594)**\n\n新能源汽车龙头：多源验证散户全量情绪与专业机构资讯共振", key="hero_002594", use_container_width=True):
            with st.spinner("正在多方位全量研判比亚迪..."):
                run_configured_agent("002594")
            st.rerun()

    with col2:
        if st.button("**太极实业 (600667)**\n\n半导体工程龙头：全量散户黑话反讽消歧与盘面资金博弈特征", key="hero_600667", use_container_width=True):
            with st.spinner("正在多方位全量研判太极实业..."):
                run_configured_agent("600667")
            st.rerun()

        if st.button("**贵州茅台 (600519)**\n\n白酒消费核心资产：深度剖析全量股吧散户悲喜情绪与官方公告", key="hero_600519", use_container_width=True):
            with st.spinner("正在多方位全量研判贵州茅台..."):
                run_configured_agent("600519")
            st.rerun()

else:
    # ---------------- 研判结果态：Gemini 多源立体排版 ----------------
    user_bubble_html = f"""
    <div class="user-msg-bubble">
        <div class="user-msg-content">
            启动标的 <strong style="color: #2563EB;">[{state.stock_name} ({state.stock_code})]</strong> 的全量散户情绪消歧、主流资讯整合与多方位异动背离研判。
        </div>
    </div>
    """
    st.markdown(textwrap.dedent(user_bubble_html).strip(), unsafe_allow_html=True)

    market_available = has_valid_market_snapshot(state.market_data)
    price = state.market_data.current_price if state.market_data else 0.0
    chg = state.market_data.change_percent if state.market_data else 0.0
    turnover = state.market_data.turnover_amount_yi if state.market_data else 0.0
    sentiment = state.average_sentiment
    is_up = chg >= 0
    chg_color = "#6B7280" if not market_available else "#DC2626" if is_up else "#059669"
    sentiment_color = "#DC2626" if sentiment >= 0 else "#059669"
    price_display = f"{price:.2f} 元" if market_available else "暂无有效行情"
    change_display = f"{'▲ +' if is_up else '▼ '}{chg:.2f}%" if market_available else "—"
    turnover_display = f"{turnover:.2f} 亿" if market_available else "暂无有效数据"

    market_grid_html = f"""
    <div class="gemini-ai-container">
        <div class="gemini-sparkle-avatar">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="white">
                <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z"/>
            </svg>
        </div>
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
                    <div class="chip-value" style="color: {chg_color};">{price_display}</div>
                    <div class="chip-sub" style="color: {chg_color};">{change_display}</div>
                </div>
                <div class="market-chip-card">
                    <div class="chip-label">今日成交量能</div>
                    <div class="chip-value" style="color: #1F2937;">{turnover_display}</div>
                    <div style="font-size: 0.72rem; color: #6B7280;">行情接口成交额</div>
                </div>
                <div class="market-chip-card">
                    <div class="chip-label">全样本散户情绪分</div>
                    <div class="chip-value" style="color: {sentiment_color};">{'+' if sentiment > 0 else ''}{sentiment:.2f}</div>
                    <div style="font-size: 0.72rem; color: #6B7280;">有效样本: {len(state.sentiment_list)} 条</div>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(textwrap.dedent(market_grid_html).strip(), unsafe_allow_html=True)

    # 背离研判雷达警报卡片
    ref = state.reflection
    if ref:
        div_label = getattr(ref.divergence_type, "value", str(ref.divergence_type))
        risk_label = getattr(ref.risk_level, "value", str(ref.risk_level))
        is_div = ref.is_divergent
        is_unknown = ref.divergence_type == DivergenceType.INSUFFICIENT_DATA
        radar_class = "radar-banner divergent" if is_div else "radar-banner"
        badge_bg = "#E5E7EB" if is_unknown else "#FEE2E2" if is_div else "#D1FAE5"
        badge_text = "#4B5563" if is_unknown else "#B91C1C" if is_div else "#065F46"
        status_dot = ('<span class="status-indicator-dot" style="background: #9CA3AF;"></span>'
                      if is_unknown else '<span class="status-indicator-dot alert"></span>'
                      if is_div else '<span class="status-indicator-dot normal"></span>')

        radar_card_html = f"""
        <div class="{radar_class}">
            <div class="radar-header">
                <div class="radar-status">
                    {status_dot}
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
                <strong>交易策略与风控提示：</strong>{ref.action_suggestion}
            </div>
        </div>
        """
        st.markdown(textwrap.dedent(radar_card_html).strip(), unsafe_allow_html=True)

    market_summary = (
        f"现价 **{price:.2f} 元**，日内涨跌 **{chg:+.2f}%**，成交额 **{turnover:.2f} 亿元**。"
        if market_available else "未取得有效行情，不能据零值快照推断价格走势。"
    )
    sentiment_summary = (
        f"有效散户情绪指数 **{sentiment:+.2f}**，并与有效行情对照。"
        if state.sentiment_list else "没有有效股吧样本，不能计算有代表性的散户情绪。"
    )
    # Gemini 思维链展开抽屉
    with st.expander("Gemini 大模型多源思维链语义推理过程 (4 个步骤)"):
        chain_md = f"""
        - **第一步 [行情数据校验]**：{market_summary}
        - **第二步 [信息采集]**：获取股吧有效发帖 **{len(state.sentiment_list)} 条**、新闻 **{len(state.news_list)} 篇**、公告 **{len(state.announcements)} 份**；新闻与公告未参与方向判定。
        - **第三步 [语义消歧]**：{sentiment_summary}
        - **第四步 [规则背离研判]**：按情绪与涨跌幅规则生成结构化决策；必要数据缺失则标记数据不足。
        """
        st.markdown(textwrap.dedent(chain_md).strip())

    # 链路追踪耗时面板 (AgentTracer)
    if st.session_state.trace_summary:
        ts = st.session_state.trace_summary
        m1, m2, m3 = st.columns(3)
        m1.metric("链路追踪跨度", f"{ts['total_spans']} 个")
        m2.metric("全流程累计耗时", f"{ts['total_latency_seconds']} s")
        m3.metric("异常环节", ", ".join(ts["failed_spans"]) if ts["has_error"] else "无")
        with st.expander("⏱️ 全链路 Span 耗时明细 (AgentTracer)"):
            st.dataframe(st.session_state.trace_spans, use_container_width=True, hide_index=True)

    # ============================================================
    # 8. 多源情报与执行日志分区展示 Tabs (Gemini 沉浸式标签页)
    # ============================================================
    execution_logs = getattr(state, "execution_logs", [])
    catalysts = getattr(state, "catalysts", [])
    risks = getattr(state, "risks", [])
    debate_res = getattr(state, "debate_result", None)

    tab_debate, tab_catalysts, tab_guba, tab_news, tab_ann, tab_logs = st.tabs([
        "多空博弈辩论 (Debate)",
        f"基本面驱动与风险 ({len(catalysts) + len(risks)} 项)",
        f"股吧散户语料 ({len(state.sentiment_list)} 条样本)",
        f"主流专业资讯 ({len(state.news_list)} 篇)",
        f"上市公司官方披露 ({len(state.announcements)} 份)",
        f"全流程执行日志 ({len(execution_logs)} 条流水)"
    ])

    with tab_debate:
        if debate_res:
            dr = debate_res
            st.markdown(f"""
            <div class="debate-box">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.85rem;">
                    <div style="font-size: 0.95rem; font-weight: 700; color: #1F2937;">
                        多智能体多空对抗博弈 (对标 TradingAgents / FinRobot Debate Protocol)
                    </div>
                    <div style="font-size: 0.75rem; background: #EEF2FF; color: #4338CA; padding: 0.2rem 0.65rem; border-radius: 9999px; font-weight: 600;">
                        裁决态势: {dr.consensus_bias}
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 0.85rem;">
                    <div class="debate-col-bull">
                        <div style="font-weight: 700; color: #DC2626; font-size: 0.85rem; margin-bottom: 0.4rem;">
                            {dr.bull_opinion.agent_name} (置信度: {dr.bull_opinion.confidence:.2f})
                        </div>
                        <div style="font-size: 0.8rem; color: #374151; margin-bottom: 0.5rem; font-weight: 600;">
                            {dr.bull_opinion.core_thesis}
                        </div>
                        <ul style="font-size: 0.75rem; color: #4B5563; margin: 0; padding-left: 1.1rem; line-height: 1.5;">
                            {"".join(f"<li>{arg}</li>" for arg in dr.bull_opinion.arguments)}
                        </ul>
                    </div>
                    <div class="debate-col-bear">
                        <div style="font-weight: 700; color: #059669; font-size: 0.85rem; margin-bottom: 0.4rem;">
                            {dr.bear_opinion.agent_name} (置信度: {dr.bear_opinion.confidence:.2f})
                        </div>
                        <div style="font-size: 0.8rem; color: #374151; margin-bottom: 0.5rem; font-weight: 600;">
                            {dr.bear_opinion.core_thesis}
                        </div>
                        <ul style="font-size: 0.75rem; color: #4B5563; margin: 0; padding-left: 1.1rem; line-height: 1.5;">
                            {"".join(f"<li>{arg}</li>" for arg in dr.bear_opinion.arguments)}
                        </ul>
                    </div>
                </div>
                <div style="background: #F8FAFC; border-radius: 0.75rem; padding: 0.65rem 0.85rem; font-size: 0.78rem; color: #475569;">
                    <strong>多空分歧焦点：</strong>{dr.key_divergence_point}<br>
                    <strong>风控委员会仲裁结论：</strong>{dr.arbitration_summary}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("当前模式未生成多智能体对抗辩论，请在侧边栏开启'多智能体工作流流水线'以启用此功能。")

    with tab_catalysts:
        col_cat, col_risk = st.columns(2)
        with col_cat:
            st.markdown(f"<div style='font-size: 0.85rem; font-weight: 700; color: #DC2626; margin-bottom: 0.5rem;'>正向催化与支撑驱动 ({len(catalysts)} 项)</div>", unsafe_allow_html=True)
            if catalysts:
                for c in catalysts:
                    st.markdown(f"""
                    <div class="catalyst-card" style="border-left: 3px solid #DC2626;">
                        <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.2rem;">[{c.source_type.upper()}] 影响等级: {c.impact_level}</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1F2937; margin-bottom: 0.3rem;">{c.source_title}</div>
                        <div style="font-size: 0.75rem; color: #4B5563; line-height: 1.4;">{c.key_insight}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-size: 0.78rem; color: #9CA3AF;'>暂未提取到强正向利好催化。</div>", unsafe_allow_html=True)

        with col_risk:
            st.markdown(f"<div style='font-size: 0.85rem; font-weight: 700; color: #059669; margin-bottom: 0.5rem;'>负向警示与潜在风险 ({len(risks)} 项)</div>", unsafe_allow_html=True)
            if risks:
                for r in risks:
                    st.markdown(f"""
                    <div class="catalyst-card" style="border-left: 3px solid #059669;">
                        <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.2rem;">[{r.source_type.upper()}] 影响等级: {r.impact_level}</div>
                        <div style="font-size: 0.8rem; font-weight: 600; color: #1F2937; margin-bottom: 0.3rem;">{r.source_title}</div>
                        <div style="font-size: 0.75rem; color: #4B5563; line-height: 1.4;">{r.key_insight}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<div style='font-size: 0.78rem; color: #9CA3AF;'>暂未提取到极端负向预警公告或涉诉新闻。</div>", unsafe_allow_html=True)

    with tab_guba:
        st.markdown("<div style='font-size: 0.8rem; color: #6B7280; margin-bottom: 0.75rem;'>自动抓取该页全部真实散户发帖，已剔除 70%+ 水军广告并消除反讽语义翻转（大模型消歧依据已归档入日志）：</div>", unsafe_allow_html=True)
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
            sarcasm_html = '<span class="sarcasm-pill">识别到反讽语义翻转</span>' if item.is_sarcasm else ''

            post_content = getattr(item, "raw_title", None) or f"股吧散户讨论语料 #{idx + 1}"
            reason_text = item.reasoning or "表意明确，无特殊反向修辞。"

            guba_card_html = f"""
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
                <div style="font-size: 0.875rem; color: #1F2937; margin: 0.4rem 0 0.5rem 0; padding-left: 0.75rem; border-left: 3px solid #E5E7EB; font-style: italic;">
                    “{post_content}”
                </div>
                <details class="disambiguation-details">
                    <summary>📋 查看大模型消歧依据与日志</summary>
                    <div class="disambiguation-log-box">
                        <strong>大模型消歧依据：</strong>{reason_text}
                    </div>
                </details>
            </div>
            """
            st.markdown(textwrap.dedent(guba_card_html).strip(), unsafe_allow_html=True)

    with tab_news:
        if state.news_list:
            for n_idx, news in enumerate(state.news_list):
                link_html = f'<a href="{news.url}" target="_blank" style="color: #1A73E8; text-decoration: none; font-size: 0.8rem; margin-left: 0.5rem;">查看原文 ↗</a>' if news.url else ''
                news_card_html = f"""
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
                """
                st.markdown(textwrap.dedent(news_card_html).strip(), unsafe_allow_html=True)
        else:
            st.info("暂未获取到该标的日内专业新闻资讯。")

    with tab_ann:
        if state.announcements:
            for a_idx, ann in enumerate(state.announcements):
                link_html = f'<a href="{ann.url}" target="_blank" style="color: #1A73E8; text-decoration: none; font-size: 0.8rem; margin-left: 0.5rem;">官方查阅 ↗</a>' if ann.url else ''
                ann_card_html = f"""
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
                """
                st.markdown(textwrap.dedent(ann_card_html).strip(), unsafe_allow_html=True)
        else:
            st.info("暂未获取到该标的近期官方公告。")

    with tab_logs:
        st.markdown("<div style='font-size: 0.8rem; color: #6B7280; margin-bottom: 0.75rem;'>全流程执行日志与大模型语料消歧依据审计流水：</div>", unsafe_allow_html=True)
        if execution_logs:
            log_lines_html = []
            for line in execution_logs:
                safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if "[语料消歧" in safe_line:
                    safe_line = re.sub(
                        r'(\[语料消歧\s*#[0-9]+\])',
                        r'<span class="log-tag-disambiguate">\1</span>',
                        safe_line
                    )
                    safe_line = re.sub(
                        r'(大模型消歧依据:\s*.*)',
                        r'<span class="log-tag-reasoning">\1</span>',
                        safe_line
                    )
                elif "[情报采集]" in safe_line:
                    safe_line = safe_line.replace("[情报采集]", '<span class="log-tag-info">[情报采集]</span>')
                elif "[行情事实对照]" in safe_line or "[客观事实对照]" in safe_line:
                    safe_line = safe_line.replace("[行情事实对照]", '<span class="log-tag-fact">[行情事实对照]</span>')
                    safe_line = safe_line.replace("[客观事实对照]", '<span class="log-tag-fact">[客观事实对照]</span>')
                elif "[多维反思决策]" in safe_line or "[反思自愈决策]" in safe_line:
                    safe_line = safe_line.replace("[多维反思决策]", '<span class="log-tag-decision">[多维反思决策]</span>')
                    safe_line = safe_line.replace("[反思自愈决策]", '<span class="log-tag-decision">[反思自愈决策]</span>')
                elif "[情绪聚合]" in safe_line:
                    safe_line = safe_line.replace("[情绪聚合]", '<span class="log-tag-info">[情绪聚合]</span>')

                log_lines_html.append(f'<div class="log-terminal-line">{safe_line}</div>')

            terminal_html = f"""
            <div class="log-terminal">
                {''.join(log_lines_html)}
            </div>
            """
            st.markdown(textwrap.dedent(terminal_html).strip(), unsafe_allow_html=True)

            with st.expander("📄 复制纯文本审计日志", expanded=False):
                st.text_area("全量日志明细", value="\n".join(execution_logs), height=200, label_visibility="collapsed")
        else:
            st.info("当前会话暂无执行日志记录。")
