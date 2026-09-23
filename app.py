import json
import streamlit as st
import streamlit.components.v1 as components
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState

# ============================================================
# 1. Streamlit 页面配置：沉浸式全屏，隐藏原生边框
# ============================================================
st.set_page_config(
    page_title="A-Share Sentiment Agent · Google Gemini",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 隐藏 Streamlit 自带的所有冗余结构，将整个视口完全交由 Gemini 设计系统接管
st.markdown(
    """
<style>
    #MainMenu, header, footer, [data-testid="stSidebar"], [data-testid="stToolbar"] {
        display: none !important;
    }
    .stApp {
        background-color: #F8FAFD;
        margin: 0 !important;
        padding: 0 !important;
    }
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    iframe {
        border: none !important;
        width: 100% !important;
        height: 100vh !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# 2. 状态与参数管理 (双向联动)
# ============================================================
query_params = st.query_params
target_code = query_params.get("code", "")
should_run = query_params.get("run", "0") == "1"
max_posts = int(query_params.get("depth", "5"))
use_llm = query_params.get("llm", "1") == "1"

agent_result_data = None

if should_run and target_code:
    try:
        agent = SentimentArbitrageAgent()
        state: AgentState = agent.run(stock_code=target_code, max_posts=max_posts, use_llm=use_llm)

        sentiment_items = []
        for idx, item in enumerate(state.sentiment_list):
            raw_val = str(getattr(item.stance, "value", item.stance)).lower()
            stance_display = "看多 (Bullish)" if ("bull" in raw_val or "多" in raw_val) else ("看空 (Bearish)" if ("bear" in raw_val or "空" in raw_val) else "中性 (Neutral)")
            sentiment_items.append({
                "id": f"p_{idx+1}",
                "original_post": getattr(item, "raw_title", None) or f"股吧散户讨论语料 #{idx + 1}",
                "stance": stance_display,
                "sentiment_score": float(item.sentiment_score),
                "is_sarcasm": bool(item.is_sarcasm),
                "slang_detected": list(item.slang_detected) if item.slang_detected else [],
                "reasoning": item.reasoning
            })

        ref = state.reflection
        div_label = getattr(ref.divergence_type, "value", str(ref.divergence_type)) if ref else "状态一致"
        risk_label = getattr(ref.risk_level, "value", str(ref.risk_level)) if ref else "LOW"

        agent_result_data = {
            "stock_code": state.stock_code,
            "stock_name": state.stock_name or f"标的 {state.stock_code}",
            "timestamp": "刚刚 (实时已更新)",
            "market_data": {
                "current_price": float(state.market_data.current_price) if state.market_data else 0.0,
                "change_percent": float(state.market_data.change_percent) if state.market_data else 0.0,
                "turnover_amount_yi": float(state.market_data.turnover_amount_yi) if state.market_data else 0.0,
            },
            "average_sentiment": float(state.average_sentiment),
            "reflection": {
                "is_divergent": bool(ref.is_divergent) if ref else False,
                "divergence_type": div_label,
                "risk_level": risk_label,
                "reflection_narrative": ref.reflection_narrative if ref else "",
                "action_suggestion": ref.action_suggestion if ref else "",
                "thinking_steps": [
                    f"第一步 [新浪 L1 行情基准交叉]：实时提取现价 {state.market_data.current_price if state.market_data else 0.0} 元，日内涨跌 {state.market_data.change_percent if state.market_data else 0.0}%，成交额 {state.market_data.turnover_amount_yi if state.market_data else 0.0} 亿元。",
                    f"第二步 [东方财富股吧语义消歧]：清洗并解析 {len(state.sentiment_list)} 条真实散户发帖，大模型消除反讽与倒装黑话。",
                    f"第三步 [博弈因果反思研判]：对比主观情绪指数 ({state.average_sentiment}) 与客观盘面走势，判定背离状态为【{div_label}】。",
                    "第四步 [Pydantic V2 契约决策自愈]：完成风险级别定级，输出防御性操作与仓位风控建议。"
                ]
            },
            "sentiment_list": sentiment_items
        }
    except Exception as e:
        st.error(f"Agent 运行异常: {e}")

backend_payload_json = json.dumps(agent_result_data, ensure_ascii=False) if agent_result_data else "null"

# ============================================================
# 3. Google Gemini 官方设计系统单页模板
# ============================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A-Share Sentiment Agent · Gemini Redesign</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            gemini: {
              blue: '#4285F4',
              purple: '#9B72CF',
              pink: '#D96570',
              bgLight: '#F8FAFD',
              surfaceLight: '#FFFFFF',
              sidebarLight: '#F0F4F9',
              bgDark: '#131314',
              surfaceDark: '#1E1F20',
              cardDark: '#282A2C',
            }
          }
        }
      }
    }
  </script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style>
    body {
      margin: 0;
      padding: 0;
      overflow: hidden;
      height: 100vh;
      width: 100vw;
    }
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: transparent;
    }
    ::-webkit-scrollbar-thumb {
      background: rgba(150, 150, 150, 0.25);
      border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: rgba(150, 150, 150, 0.45);
    }
  </style>
</head>
<body class="bg-gemini-bgLight dark:bg-gemini-bgDark text-neutral-900 dark:text-neutral-100 transition-colors duration-300 font-sans selection:bg-blue-500/20 selection:text-blue-600">
  <div id="root"></div>

  <script type="text/babel">
    const { useState, useEffect } = React;
    const initialBackendData = __BACKEND_PAYLOAD__;
    const defaultTargetCode = "__DEFAULT_CODE__";

    function App() {
      const [isDark, setIsDark] = useState(false);
      const [isSidebarOpen, setIsSidebarOpen] = useState(true);
      const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
      const [isParamDrawerOpen, setIsParamDrawerOpen] = useState(false);

      const [stockCode, setStockCode] = useState(defaultTargetCode || "600584");
      const [maxPosts, setMaxPosts] = useState(__MAX_POSTS__);
      const [useLLM, setUseLLM] = useState(__USE_LLM__);
      const [naturalPrompt, setNaturalPrompt] = useState("");

      const [isLoading, setIsLoading] = useState(false);
      const [activeSession, setActiveSession] = useState(initialBackendData);
      const [copied, setCopied] = useState(false);
      const [isThinkingExpanded, setIsThinkingExpanded] = useState(true);

      const historyList = [
        { id: "1", code: "600584", title: "长电科技 · 散户恐慌割肉背离", time: "最新" },
        { id: "2", code: "600519", title: "贵州茅台 · 散户反讽消歧研判", time: "核心" },
        { id: "3", code: "002594", title: "比亚迪 · 盘面情绪量价共振", time: "热门" },
        { id: "4", code: "601127", title: "赛力斯 · 智选车诱多识别", time: "高波" },
      ];

      useEffect(() => {
        if (isDark) {
          document.documentElement.classList.add("dark");
        } else {
          document.documentElement.classList.remove("dark");
        }
      }, [isDark]);

      useEffect(() => {
        if (window.lucide) {
          window.lucide.createIcons();
        }
      });

      const triggerRealAgent = (code) => {
        const target = code || stockCode || "600584";
        setIsLoading(true);
        const search = `?code=${encodeURIComponent(target)}&run=1&depth=${maxPosts}&llm=${useLLM ? '1' : '0'}`;
        if (window.parent && window.parent.location) {
          window.parent.location.search = search;
        } else {
          window.location.search = search;
        }
      };

      const copyReport = () => {
        if (activeSession && activeSession.reflection) {
          navigator.clipboard.writeText(activeSession.reflection.reflection_narrative);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }
      };

      return (
        <div className="flex h-screen w-screen overflow-hidden">
          {/* 左侧可折叠导航轨 (Collapsible Rail) */}
          <aside className={`hidden md:flex flex-col justify-between transition-all duration-300 border-r z-20 ${
            isSidebarOpen ? "w-64" : "w-16"
          } ${isDark ? "bg-gemini-surfaceDark border-white/5" : "bg-gemini-sidebarLight border-black/5"}`}>
            <div className="p-3 flex flex-col gap-3">
              <div className="flex items-center justify-between px-2 h-10">
                <button
                  onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                  className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-transform active:scale-95 text-neutral-600 dark:text-neutral-300"
                  title={isSidebarOpen ? "收起导航" : "展开导航"}
                >
                  <i data-lucide="menu" className="w-5 h-5"></i>
                </button>
                {isSidebarOpen && (
                  <div className="flex items-center gap-1.5 font-medium tracking-tight text-sm">
                    <span className="bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 bg-clip-text text-transparent font-semibold">
                      Gemini
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-mono">
                      Pro
                    </span>
                  </div>
                )}
              </div>

              {/* 发起新研判按钮 */}
              <button
                onClick={() => {
                  if (window.parent && window.parent.location) {
                    window.parent.location.search = "?run=0";
                  } else {
                    window.location.search = "?run=0";
                  }
                }}
                className={`flex items-center gap-3 w-full py-2.5 px-3 rounded-full text-sm font-medium transition-all shadow-sm active:scale-95 ${
                  isSidebarOpen
                    ? "bg-white dark:bg-gemini-cardDark text-neutral-800 dark:text-neutral-100 hover:shadow-md"
                    : "justify-center bg-white dark:bg-gemini-cardDark"
                }`}
              >
                <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white shrink-0">
                  <i data-lucide="sparkles" className="w-3.5 h-3.5"></i>
                </div>
                {isSidebarOpen && <span>发起新标的研判</span>}
              </button>
            </div>

            {/* 研判历史抽屉 */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
              {isSidebarOpen && (
                <div className="text-[11px] font-semibold px-2 py-1.5 text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
                  快速切换标的
                </div>
              )}
              {historyList.map((item) => (
                <button
                  key={item.id}
                  onClick={() => triggerRealAgent(item.code)}
                  className={`w-full text-left py-2 px-3 rounded-xl text-xs flex items-center gap-2.5 transition-colors group ${
                    isSidebarOpen ? "justify-start" : "justify-center"
                  } hover:bg-black/5 dark:hover:bg-white/5 text-neutral-600 dark:text-neutral-300`}
                  title={item.title}
                >
                  <i data-lucide="history" className="w-4 h-4 shrink-0 text-neutral-400 group-hover:text-blue-500"></i>
                  {isSidebarOpen && (
                    <div className="truncate flex-1">
                      <div className="truncate font-medium">{item.title}</div>
                      <div className="text-[10px] text-neutral-400">代码: {item.code}</div>
                    </div>
                  )}
                </button>
              ))}
            </div>

            {/* 底部功能偏好 */}
            <div className="p-3 border-t border-black/5 dark:border-white/5 flex flex-col gap-1">
              <button
                onClick={() => setIsDark(!isDark)}
                className="flex items-center gap-3 w-full py-2 px-3 rounded-xl text-xs text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <i data-lucide={isDark ? "sun" : "moon"} className={`w-4 h-4 shrink-0 ${isDark ? "text-amber-400" : ""}`}></i>
                {isSidebarOpen && <span>{isDark ? "明亮外观 (Light)" : "深邃外观 (Dark)"}</span>}
              </button>
              <button
                onClick={() => setIsParamDrawerOpen(true)}
                className="flex items-center gap-3 w-full py-2 px-3 rounded-xl text-xs text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <i data-lucide="sliders-horizontal" className="w-4 h-4 shrink-0"></i>
                {isSidebarOpen && <span>Agent 引擎参数</span>}
              </button>
            </div>
          </aside>

          {/* 移动端遮罩侧边栏 */}
          {isMobileDrawerOpen && (
            <div className="fixed inset-0 z-50 flex md:hidden">
              <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setIsMobileDrawerOpen(false)}></div>
              <div className={`relative w-72 max-w-[80vw] h-full p-4 flex flex-col justify-between shadow-2xl z-10 ${
                isDark ? "bg-gemini-surfaceDark" : "bg-gemini-sidebarLight"
              }`}>
                <div className="flex items-center justify-between pb-3 border-b border-black/5 dark:border-white/5">
                  <span className="font-semibold text-sm bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">
                    Gemini Agent
                  </span>
                  <button onClick={() => setIsMobileDrawerOpen(false)} className="p-1 rounded-full">
                    <i data-lucide="x" className="w-5 h-5"></i>
                  </button>
                </div>
                <div className="flex-1 py-4 overflow-y-auto space-y-2">
                  <div className="text-xs font-semibold text-neutral-400">快速标的研判</div>
                  {historyList.map(h => (
                    <div
                      key={h.id}
                      onClick={() => { triggerRealAgent(h.code); setIsMobileDrawerOpen(false); }}
                      className="p-2.5 rounded-lg text-xs hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer"
                    >
                      <div className="font-medium truncate">{h.title}</div>
                      <div className="text-[10px] text-neutral-400">{h.code}</div>
                    </div>
                  ))}
                </div>
                <button onClick={() => setIsDark(!isDark)} className="flex items-center gap-2 p-2 text-xs">
                  <i data-lucide={isDark ? "sun" : "moon"} className="w-4 h-4"></i>
                  <span>切换外观主题</span>
                </button>
              </div>
            </div>
          )}

          {/* 主视口工作区 */}
          <main className="flex-1 flex flex-col h-full relative overflow-hidden">
            {/* 顶栏 */}
            <header className="h-14 flex items-center justify-between px-4 sm:px-8 border-b border-black/5 dark:border-white/5 z-10 shrink-0">
              <div className="flex items-center gap-3">
                <button onClick={() => setIsMobileDrawerOpen(true)} className="md:hidden p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5">
                  <i data-lucide="menu" className="w-5 h-5"></i>
                </button>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-base sm:text-lg tracking-tight bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                    A-Share Sentiment Agent
                  </span>
                  <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400">
                    <i data-lucide="zap" className="w-3 h-3 mr-1 text-amber-500"></i>
                    东方财富真实股吧 + 秒级盘面
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsParamDrawerOpen(!isParamDrawerOpen)}
                  className={`p-2 rounded-full transition-all active:scale-95 ${
                    isParamDrawerOpen ? "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300" : "hover:bg-black/5 dark:hover:bg-white/5"
                  }`}
                  title="引擎配置"
                >
                  <i data-lucide="sliders-horizontal" className="w-4 h-4"></i>
                </button>
                <button
                  onClick={() => setIsDark(!isDark)}
                  className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-all active:scale-95"
                  title="外观模式"
                >
                  <i data-lucide={isDark ? "sun" : "moon"} className={`w-4 h-4 ${isDark ? "text-amber-400" : ""}`}></i>
                </button>
              </div>
            </header>

            {/* 参数调节弹窗 */}
            {isParamDrawerOpen && (
              <div className="absolute top-14 right-4 sm:right-8 w-80 p-4 rounded-3xl shadow-2xl border backdrop-blur-2xl z-30 bg-white/95 dark:bg-gemini-surfaceDark/95 border-black/5 dark:border-white/10">
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-black/5 dark:border-white/5">
                  <span className="text-xs font-semibold flex items-center gap-1.5">
                    <i data-lucide="sliders-horizontal" className="w-3.5 h-3.5 text-blue-500"></i>
                    研判参数与大模型消歧
                  </span>
                  <button onClick={() => setIsParamDrawerOpen(false)} className="p-1 rounded-full">
                    <i data-lucide="x" className="w-3.5 h-3.5"></i>
                  </button>
                </div>
                <div className="space-y-4 text-xs">
                  <div>
                    <label className="block text-neutral-500 dark:text-neutral-400 mb-1 font-medium">股票代码 (A股 6位代码)</label>
                    <input
                      type="text"
                      value={stockCode}
                      onChange={(e) => setStockCode(e.target.value)}
                      placeholder="如 600584, 600519"
                      className="w-full px-3 py-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 border-none outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between text-neutral-500 dark:text-neutral-400 mb-1 font-medium">
                      <span>散户发帖分析深度</span>
                      <span className="font-mono text-blue-600 dark:text-blue-400">{maxPosts} 条</span>
                    </div>
                    <input
                      type="range"
                      min="3"
                      max="15"
                      value={maxPosts}
                      onChange={(e) => setMaxPosts(Number(e.target.value))}
                      className="w-full accent-blue-600 cursor-pointer"
                    />
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <div>
                      <div className="font-medium">启用真实大模型思维链</div>
                      <div className="text-[10px] text-neutral-400">调用 LLM 识别反讽隐喻</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={useLLM}
                      onChange={(e) => setUseLLM(e.target.checked)}
                      className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                    />
                  </div>
                  <button
                    onClick={() => { setIsParamDrawerOpen(false); triggerRealAgent(); }}
                    className="w-full py-2.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium text-xs shadow-md active:scale-95 transition-all flex items-center justify-center gap-1.5"
                  >
                    <i data-lucide="sparkles" className="w-3.5 h-3.5"></i>
                    保存并立即执行研判
                  </button>
                </div>
              </div>
            )}

            {/* 居中视口消息流 (Max-width Constrained Chat Flow) */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 pb-36 pt-4">
              <div className="max-w-4xl mx-auto space-y-8">
                {/* 空状态欢迎卡片 (Gemini 经典居中 Hero) */}
                {!activeSession && !isLoading && (
                  <div className="py-12 sm:py-20 flex flex-col items-center text-center">
                    <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-blue-500 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-blue-500/20 mb-6">
                      <i data-lucide="sparkles" className="w-8 h-8"></i>
                    </div>

                    <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight mb-3">
                      <span className="bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                        你好，投资研究员
                      </span>
                    </h1>
                    <p className="text-sm sm:text-base text-neutral-500 dark:text-neutral-400 max-w-lg mb-8 leading-relaxed">
                      基于 Google Gemini 设计系统的金融舆情决策智能体。穿透散户黑话与反语隐喻，与秒级 L1 盘面深度交叉印证。
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl text-left">
                      {[
                        { code: "600584", name: "长电科技", desc: "半导体封测龙头：检测日内盘面与散户恐慌割肉背离", tag: "高位背离预警" },
                        { code: "600519", name: "贵州茅台", desc: "白酒消费核心资产：分析震荡整理期散户黑话反讽程度", tag: "反讽消歧" },
                        { code: "002594", name: "比亚迪", desc: "新能源汽车龙头：验证股吧真实情绪与量价指标共振", tag: "量价共振" },
                        { code: "601127", name: "赛力斯", desc: "智选车核心标的：穿透『赢麻了』出货风险与洗盘特征", tag: "诱多甄别" },
                      ].map(c => (
                        <button
                          key={c.code}
                          onClick={() => triggerRealAgent(c.code)}
                          className={`p-4 rounded-2xl border transition-all text-left flex flex-col justify-between group active:scale-[0.98] ${
                            isDark ? "bg-gemini-surfaceDark/70 hover:bg-gemini-cardDark border-white/5" : "bg-white/80 hover:bg-white border-black/5 hover:shadow-md"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-semibold text-sm group-hover:text-blue-500 transition-colors">
                              {c.name} ({c.code})
                            </span>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 font-medium">
                              {c.tag}
                            </span>
                          </div>
                          <p className="text-xs text-neutral-500 dark:text-neutral-400 line-clamp-2 leading-relaxed">
                            {c.desc}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* 骨架加载中 */}
                {isLoading && (
                  <div className="py-10 space-y-6 animate-pulse">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white">
                        <i data-lucide="sparkles" className="w-4 h-4"></i>
                      </div>
                      <div className="h-4 w-48 bg-neutral-200 dark:bg-neutral-800 rounded-full"></div>
                    </div>
                    <div className="space-y-3 pl-11">
                      <div className="h-28 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full"></div>
                      <div className="h-24 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full"></div>
                      <div className="h-40 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full"></div>
                    </div>
                  </div>
                )}

                {/* 会话与 Gemini 响应 */}
                {activeSession && !isLoading && (
                  <div className="space-y-8 animate-in fade-in duration-300">
                    {/* 用户提问气泡 */}
                    <div className="flex justify-end">
                      <div className="max-w-xl rounded-3xl px-5 py-3.5 text-sm leading-relaxed shadow-sm bg-gemini-sidebarLight dark:bg-gemini-cardDark text-neutral-800 dark:text-neutral-100">
                        启动标的 <span className="font-semibold text-blue-600 dark:text-blue-400">[{activeSession.stock_name} ({activeSession.stock_code})]</span> 的东方财富真实舆情消歧与异动背离研判。
                      </div>
                    </div>

                    {/* Gemini 开放式排版 */}
                    <div className="flex gap-4 items-start">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-blue-500 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 shrink-0 mt-1">
                        <i data-lucide="sparkles" className="w-4 h-4"></i>
                      </div>

                      <div className="flex-1 space-y-6 overflow-hidden">
                        {/* 1. L1 盘面四宫格芯片 */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <div className={`p-4 rounded-3xl border transition-all ${isDark ? "bg-gemini-surfaceDark/70 border-white/5" : "bg-white border-black/5 shadow-sm"}`}>
                            <div className="text-[11px] text-neutral-400 mb-1">标的名称</div>
                            <div className="text-base font-semibold truncate">{activeSession.stock_name}</div>
                            <div className="text-[10px] text-neutral-500 font-mono">{activeSession.stock_code}</div>
                          </div>

                          <div className={`p-4 rounded-3xl border transition-all ${isDark ? "bg-gemini-surfaceDark/70 border-white/5" : "bg-white border-black/5 shadow-sm"}`}>
                            <div className="text-[11px] text-neutral-400 mb-1">实时成交价</div>
                            <div className={`text-base font-semibold font-mono ${activeSession.market_data.change_percent >= 0 ? "text-red-500" : "text-emerald-500"}`}>
                              {activeSession.market_data.current_price.toFixed(2)} 元
                            </div>
                            <div className={`text-[10px] font-semibold ${activeSession.market_data.change_percent >= 0 ? "text-red-500" : "text-emerald-500"}`}>
                              {activeSession.market_data.change_percent >= 0 ? `+${activeSession.market_data.change_percent}%` : `${activeSession.market_data.change_percent}%`}
                            </div>
                          </div>

                          <div className={`p-4 rounded-3xl border transition-all ${isDark ? "bg-gemini-surfaceDark/70 border-white/5" : "bg-white border-black/5 shadow-sm"}`}>
                            <div className="text-[11px] text-neutral-400 mb-1">今日成交量能</div>
                            <div className="text-base font-semibold font-mono">{activeSession.market_data.turnover_amount_yi.toFixed(2)} 亿</div>
                            <div className="text-[10px] text-neutral-400">主力资金博弈</div>
                          </div>

                          <div className={`p-4 rounded-3xl border transition-all ${isDark ? "bg-gemini-surfaceDark/70 border-white/5" : "bg-white border-black/5 shadow-sm"}`}>
                            <div className="text-[11px] text-neutral-400 mb-1">散户综合情绪分</div>
                            <div className={`text-base font-semibold font-mono ${activeSession.average_sentiment >= 0 ? "text-red-500" : "text-emerald-500"}`}>
                              {activeSession.average_sentiment > 0 ? `+${activeSession.average_sentiment.toFixed(2)}` : activeSession.average_sentiment.toFixed(2)}
                            </div>
                            <div className="text-[10px] text-neutral-400">区间: [-1.0, +1.0]</div>
                          </div>
                        </div>

                        {/* 2. 背离研判雷达警报卡 */}
                        <div className={`p-5 rounded-3xl border relative overflow-hidden transition-all ${
                          activeSession.reflection.is_divergent
                            ? isDark
                              ? "bg-gradient-to-r from-red-950/20 via-gemini-surfaceDark to-gemini-surfaceDark border-red-500/30"
                              : "bg-gradient-to-r from-red-50 via-white to-white border-red-200"
                            : isDark ? "bg-gemini-surfaceDark border-emerald-500/30" : "bg-emerald-50/60 border-emerald-200"
                        }`}>
                          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                            <div className="flex items-center gap-2">
                              <span className="relative flex h-3 w-3">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                              </span>
                              <span className="font-semibold text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
                                <i data-lucide="shield-alert" className="w-4 h-4"></i>
                                {activeSession.reflection.divergence_type}
                              </span>
                            </div>

                            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">
                              风险等级: {activeSession.reflection.risk_level}
                            </span>
                          </div>

                          <div className="text-xs sm:text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed mb-4">
                            <strong className="text-neutral-900 dark:text-white font-medium">研判推导逻辑：</strong>
                            {activeSession.reflection.reflection_narrative}
                          </div>

                          <div className="p-3 rounded-2xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 flex items-start gap-2.5 text-xs leading-relaxed">
                            <i data-lucide="info" className="w-4 h-4 text-blue-500 shrink-0 mt-0.5"></i>
                            <div>
                              <span className="font-medium text-neutral-900 dark:text-neutral-100">交易决策风控参考：</span>
                              <span className="text-neutral-600 dark:text-neutral-300">{activeSession.reflection.action_suggestion}</span>
                            </div>
                          </div>
                        </div>

                        {/* 3. Gemini 思考链折叠 */}
                        <div className="rounded-3xl border border-black/5 dark:border-white/5 overflow-hidden bg-black/[0.02] dark:bg-white/[0.02]">
                          <button
                            onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                            className="w-full px-5 py-3 flex items-center justify-between text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100"
                          >
                            <div className="flex items-center gap-2">
                              <i data-lucide="bot" className="w-4 h-4 text-indigo-500"></i>
                              <span>Gemini 大模型思维链语义推理过程 ({activeSession.reflection.thinking_steps.length} 个步骤)</span>
                            </div>
                            <i data-lucide={isThinkingExpanded ? "chevron-down" : "chevron-right"} className="w-4 h-4"></i>
                          </button>

                          {isThinkingExpanded && (
                            <div className="px-5 pb-4 pt-1 space-y-2 border-t border-black/5 dark:border-white/5 text-xs text-neutral-600 dark:text-neutral-400">
                              {activeSession.reflection.thinking_steps.map((step, idx) => (
                                <div key={idx} className="flex items-start gap-2 pl-2 border-l-2 border-indigo-500/50">
                                  <span className="leading-relaxed">{step}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* 4. 散户发帖语料与消歧明细 */}
                        <div className="space-y-3">
                          <div className="flex items-center justify-between px-1">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-neutral-500 flex items-center gap-1.5">
                              <i data-lucide="bar-chart-3" className="w-3.5 h-3.5"></i>
                              东方财富股吧实时抓取样本与消歧详情 ({activeSession.sentiment_list.length} 条样本)
                            </h3>
                            <span className="text-[11px] text-neutral-400">已消除反话倒装与黑话歧义</span>
                          </div>

                          <div className="space-y-3">
                            {activeSession.sentiment_list.map((item) => (
                              <div
                                key={item.id}
                                className={`p-4 rounded-3xl border transition-all ${
                                  isDark ? "bg-gemini-surfaceDark/50 hover:bg-gemini-surfaceDark border-white/5" : "bg-white hover:bg-neutral-50/80 border-black/5 shadow-sm"
                                }`}
                              >
                                <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
                                  <div className="flex items-center gap-2">
                                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                                      item.stance.includes("看多")
                                        ? "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
                                        : item.stance.includes("看空")
                                        ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300"
                                        : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300"
                                    }`}>
                                      {item.stance}
                                    </span>

                                    {item.is_sarcasm && (
                                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
                                        <i data-lucide="flame" className="w-3 h-3 text-amber-500"></i>
                                        反讽语义翻转
                                      </span>
                                    )}

                                    {item.slang_detected.map((slang, sIdx) => (
                                      <span key={sIdx} className="px-2 py-0.5 rounded-md text-[10px] bg-neutral-100 dark:bg-neutral-800 text-neutral-500 font-mono">
                                        #{slang}
                                      </span>
                                    ))}
                                  </div>

                                  <div className="font-mono text-xs font-semibold text-neutral-500">
                                    情绪评分: <span className={item.sentiment_score >= 0 ? "text-red-500" : "text-emerald-500"}>{item.sentiment_score > 0 ? `+${item.sentiment_score.toFixed(2)}` : item.sentiment_score.toFixed(2)}</span>
                                  </div>
                                </div>

                                <div className="text-xs sm:text-sm text-neutral-800 dark:text-neutral-200 mb-2 pl-3 border-l-2 border-neutral-300 dark:border-neutral-700 italic">
                                  “{item.original_post}”
                                </div>

                                <div className="text-[11px] text-neutral-500 dark:text-neutral-400 flex items-start gap-1.5 pt-1">
                                  <i data-lucide="sparkles" className="w-3.5 h-3.5 text-blue-500 shrink-0 mt-0.5"></i>
                                  <span>大模型反思依据: {item.reasoning}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* 5. 底部工具栏 */}
                        <div className="flex items-center gap-1 text-neutral-400 pt-2 border-t border-black/5 dark:border-white/5">
                          <button onClick={copyReport} className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5" title="复制研判结论">
                            <i data-lucide={copied ? "check" : "copy"} className={`w-4 h-4 ${copied ? "text-emerald-500" : ""}`}></i>
                          </button>
                          <button onClick={() => triggerRealAgent()} className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5" title="重新研判">
                            <i data-lucide="rotate-ccw" className="w-4 h-4"></i>
                          </button>
                          <div className="ml-auto text-[10px] text-neutral-400">
                            已接入实时 L1 盘面与股吧爬虫 · {activeSession.timestamp}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 视口中下方悬浮复合胶囊输入舱 (Floating Input Pill) */}
            <div className="absolute bottom-0 left-0 right-0 p-4 sm:p-6 pointer-events-none z-20 flex justify-center">
              <div className="w-full max-w-3xl pointer-events-auto">
                <div className={`p-2 sm:p-2.5 rounded-3xl sm:rounded-full shadow-2xl border backdrop-blur-2xl transition-all ${
                  isDark
                    ? "bg-gemini-surfaceDark/85 border-white/10 shadow-black/60"
                    : "bg-white/85 border-black/10 shadow-slate-200/80"
                }`}>
                  <div className="flex items-center gap-2">
                    {/* 代码选择胶囊 */}
                    <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/5 dark:bg-white/5 text-xs text-neutral-600 dark:text-neutral-300 font-mono">
                      <i data-lucide="search" className="w-3.5 h-3.5 text-neutral-400"></i>
                      <input
                        type="text"
                        value={stockCode}
                        onChange={(e) => setStockCode(e.target.value)}
                        placeholder="代码 (如 600584)"
                        className="bg-transparent border-none outline-none w-24 text-xs font-mono"
                      />
                    </div>

                    <input
                      type="text"
                      value={naturalPrompt}
                      onChange={(e) => setNaturalPrompt(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") triggerRealAgent(); }}
                      placeholder={stockCode ? `研判 [${stockCode}] 的主力意图与散户反讽背离...` : "输入 6 位 A 股股票代码或研判指令..."}
                      className="flex-1 bg-transparent px-3 py-2 text-xs sm:text-sm placeholder:text-neutral-400 outline-none border-none"
                    />

                    <button
                      onClick={() => setIsParamDrawerOpen(!isParamDrawerOpen)}
                      className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
                      title="研判参数"
                    >
                      <i data-lucide="sliders-horizontal" className="w-4 h-4"></i>
                    </button>

                    <button
                      onClick={() => triggerRealAgent()}
                      disabled={isLoading}
                      className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white flex items-center justify-center shadow-md active:scale-95 transition-all disabled:opacity-50 shrink-0"
                      title="启动智能研判"
                    >
                      <i data-lucide={isLoading ? "rotate-ccw" : "send"} className={`w-4 h-4 ${isLoading ? "animate-spin" : "ml-0.5"}`}></i>
                    </button>
                  </div>
                </div>
                <div className="text-center text-[10px] text-neutral-400 dark:text-neutral-500 mt-2">
                  Gemini Agent 研判结论基于大模型语义推理与 L1 实时盘面基准，不构成直接投资买卖依据。
                </div>
              </div>
            </div>
          </main>
        </div>
      );
    }

    ReactDOM.createRoot(document.getElementById("root")).render(<App />);
  </script>
</body>
</html>
"""

gemini_html = (
    HTML_TEMPLATE
    .replace("__BACKEND_PAYLOAD__", backend_payload_json)
    .replace("__DEFAULT_CODE__", target_code or "600584")
    .replace("__MAX_POSTS__", str(max_posts))
    .replace("__USE_LLM__", str(use_llm).lower())
)

# ============================================================
# 4. 全屏注入 Gemini 页面 (完美替代原生粗糙 UI)
# ============================================================
components.html(gemini_html, height=1000, scrolling=True)
