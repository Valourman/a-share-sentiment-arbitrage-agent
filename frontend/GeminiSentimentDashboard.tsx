import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Send,
  SlidersHorizontal,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  Share2,
  Menu,
  X,
  History,
  Settings,
  Flame,
  Search,
  Zap,
  Info,
  ExternalLink,
  Sun,
  Moon,
  ShieldAlert,
  BarChart3,
  Bot
} from "lucide-react";

// ==========================================
// 领域实体与类型定义 (Domain Types)
// ==========================================
export interface MarketData {
  stock_code: string;
  stock_name: string;
  current_price: number;
  change_percent: number;
  turnover_amount_yi: number;
}

export interface SentimentItem {
  id: string;
  original_post: string;
  stance: "看多 (Bullish)" | "看空 (Bearish)" | "中性 (Neutral)";
  sentiment_score: number;
  is_sarcasm: boolean;
  slang_detected: string[];
  reasoning: string;
}

export interface ReflectionData {
  is_divergent: boolean;
  divergence_type: string;
  risk_level: "高 (High)" | "中 (Medium)" | "低 (Low)" | "无 (None)";
  reflection_narrative: string;
  action_suggestion: string;
  thinking_steps: string[];
}

export interface AgentRunState {
  stock_code: string;
  stock_name: string;
  market_data: MarketData;
  sentiment_list: SentimentItem[];
  average_sentiment: number;
  reflection: ReflectionData;
  timestamp: string;
}

// ==========================================
// 主组件: GeminiSentimentDashboard
// ==========================================
export const GeminiSentimentDashboard: React.FC = () => {
  // 主题与导航状态
  const [isDark, setIsDark] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState<boolean>(false);
  const [isParamDrawerOpen, setIsParamDrawerOpen] = useState<boolean>(false);

  // 参数配置状态
  const [stockCode, setStockCode] = useState<string>("600584");
  const [maxPosts, setMaxPosts] = useState<number>(5);
  const [useLLM, setUseLLM] = useState<boolean>(true);
  const [naturalPrompt, setNaturalPrompt] = useState<string>("");

  // 运行与结果状态
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeSession, setActiveSession] = useState<AgentRunState | null>(null);
  const [historyList, setHistoryList] = useState<Array<{ id: string; title: string; time: string }>>([
    { id: "1", title: "长电科技 (600584) · 诱多背离预警", time: "10分钟前" },
    { id: "2", title: "贵州茅台 (600519) · 散户恐慌盘研判", time: "昨天" },
    { id: "3", title: "比亚迪 (002594) · 情绪共振验证", time: "3天前" },
  ]);

  // 思考过程抽屉展开状态
  const [isThinkingExpanded, setIsThinkingExpanded] = useState<boolean>(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // 监听主题切换同步至 document
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  // 模拟触发 Agent 反思研判流程
  const handleTriggerAnalysis = (codeToRun?: string) => {
    const targetCode = codeToRun || stockCode || "600584";
    setIsLoading(true);
    setStockCode(targetCode);

    setTimeout(() => {
      const mockResult: AgentRunState = {
        stock_code: targetCode,
        stock_name: targetCode === "600519" ? "贵州茅台" : targetCode === "002594" ? "比亚迪" : "长电科技",
        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        market_data: {
          stock_code: targetCode,
          stock_name: targetCode === "600519" ? "贵州茅台" : targetCode === "002594" ? "比亚迪" : "长电科技",
          current_price: targetCode === "600519" ? 1720.5 : targetCode === "002594" ? 286.3 : 32.45,
          change_percent: targetCode === "600519" ? -1.85 : 4.12,
          turnover_amount_yi: targetCode === "600519" ? 54.2 : 28.6,
        },
        average_sentiment: -0.68,
        reflection: {
          is_divergent: true,
          divergence_type: "价格虚拉 / 散户恐慌割肉 (洗盘背离)",
          risk_level: "高 (High)",
          reflection_narrative:
            "标的盘面日内放量大涨 +4.12%，但股吧散户论坛情绪深度承压 (-0.68)，出现大面积『主力快跑』、『再买剁手』等黑话反讽。大模型多步思维链消歧确认散户处于极端交出筹码状态，呈现经典盘面主力对倒拉升与散户非理性恐慌背离。",
          action_suggestion:
            "短期注意主力诱多出货脉冲或高位震荡，散户情绪未现逆向修复前不宜重仓盲目追高，等待缩量二次确认。",
          thinking_steps: [
            "第一步 [盘面基准交叉]：提取实时行情 L1 数据，价格突破 32.40 元，成交额 28.6 亿，技术面呈现超买走势。",
            "第二步 [大模型语义消歧]：检索并解析 5 条高频热帖，识别到『赢麻了』实际带有反讽修辞，真实态度修正为强看空。",
            "第三步 [黑话提取与反思]：触发关键词『发套』、『收割』，反思引擎比对历史情绪周期，判定当前为筹码置换期。",
            "第四步 [自愈决策生成]：通过 Pydantic 校验背离类型，输出背离告警与二级风控策略建议。",
          ],
        },
        sentiment_list: [
          {
            id: "p1",
            original_post: "今天又是赢麻了的一天，家人们赶紧买入给主力抬轿子送温暖啊！",
            stance: "看空 (Bearish)",
            sentiment_score: -0.85,
            is_sarcasm: true,
            slang_detected: ["赢麻了", "抬轿子", "送温暖"],
            reasoning: "字面表达看似看多，但后半句具有强烈嘲讽与自嘲特征，大模型判定为反讽看空。",
          },
          {
            id: "p2",
            original_post: "主力真是大善人，这么高的位置还拉红，怕我们亏不够是吧？",
            stance: "看空 (Bearish)",
            sentiment_score: -0.75,
            is_sarcasm: true,
            slang_detected: ["大善人", "拉红"],
            reasoning: "反语修辞表达对拉高出货的质疑，判定为负面恐慌看空。",
          },
          {
            id: "p3",
            original_post: "明天一开盘估计又是准时发套，早盘冲高我已坚决清仓保命了。",
            stance: "看空 (Bearish)",
            sentiment_score: -0.9,
            is_sarcasm: false,
            slang_detected: ["发套", "保命"],
            reasoning: "直白陈述看空预期并透露卖出行为，情绪极其悲观。",
          },
          {
            id: "p4",
            original_post: "量能确实放出来了，半导体板块情绪在修复，这波能看前高。",
            stance: "看多 (Bullish)",
            sentiment_score: 0.65,
            is_sarcasm: false,
            slang_detected: ["前高"],
            reasoning: "理性基于量价与板块轮动的看多观点，无明显反语反讽。",
          },
          {
            id: "p5",
            original_post: "机构在这个位置格局真大，天天做T把散户耍得团团转。",
            stance: "中性 (Neutral)",
            sentiment_score: -0.2,
            is_sarcasm: true,
            slang_detected: ["格局", "做T"],
            reasoning: "反讽机构操作手法，但兼具观望与博弈心理，判定为偏空弱中性。",
          },
        ],
      };

      setActiveSession(mockResult);
      setIsLoading(false);
      setHistoryList((prev) => [
        { id: Date.now().toString(), title: `${mockResult.stock_name} (${mockResult.stock_code}) · 背离研判`, time: "刚刚" },
        ...prev,
      ]);
    }, 1200);
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  return (
    <div className={`min-h-screen font-sans transition-colors duration-300 ${isDark ? "bg-[#131314] text-[#E3E3E3]" : "bg-[#F8FAFD] text-[#1F1F1F]"}`}>
      {/* ============================================================ */}
      {/* 布局主网格 (Layout: Left Rail + Center Stream Viewport)      */}
      {/* ============================================================ */}
      <div className="flex h-screen overflow-hidden">
        {/* ---------------- 1. 桌面端左侧折叠导航轨 (Collapsible Rail) ---------------- */}
        <aside
          className={`hidden md:flex flex-col justify-between transition-all duration-300 border-r z-20 ${
            isSidebarOpen ? "w-64" : "w-16"
          } ${
            isDark ? "bg-[#1E1F20] border-white/5" : "bg-[#F0F4F9] border-black/5"
          }`}
        >
          {/* 顶部 Brand 区域 */}
          <div className="p-3 flex flex-col gap-3">
            <div className="flex items-center justify-between px-2 h-10">
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className={`p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-transform active:scale-95 text-neutral-600 dark:text-neutral-300`}
                title={isSidebarOpen ? "折叠侧边栏" : "展开侧边栏"}
              >
                <Menu size={18} />
              </button>

              {isSidebarOpen && (
                <div className="flex items-center gap-1.5 font-medium tracking-tight text-sm">
                  <span className="bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 bg-clip-text text-transparent font-semibold">
                    Gemini
                  </span>
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-mono scale-90">
                    Pro
                  </span>
                </div>
              )}
            </div>

            {/* 发起新研判按钮 (Gemini 经典悬浮大圆角 Pill) */}
            <button
              onClick={() => {
                setActiveSession(null);
                setStockCode("");
              }}
              className={`flex items-center gap-3 w-full py-2.5 px-3 rounded-full text-sm font-medium transition-all shadow-sm active:scale-95 ${
                isSidebarOpen
                  ? "bg-white dark:bg-[#282A2C] text-neutral-800 dark:text-neutral-100 hover:shadow-md"
                  : "justify-center bg-white dark:bg-[#282A2C]"
              }`}
            >
              <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white shrink-0">
                <Sparkles size={13} />
              </div>
              {isSidebarOpen && <span>发起新标的研判</span>}
            </button>
          </div>

          {/* 研判历史抽屉列表 */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            {isSidebarOpen && (
              <div className="text-xs font-semibold px-2 py-1.5 text-neutral-400 dark:text-neutral-500 uppercase tracking-wider">
                最近研判任务
              </div>
            )}
            {historyList.map((item) => (
              <button
                key={item.id}
                onClick={() => handleTriggerAnalysis("600584")}
                className={`w-full text-left py-2 px-3 rounded-xl text-xs flex items-center gap-2.5 transition-colors group ${
                  isSidebarOpen ? "justify-start" : "justify-center"
                } hover:bg-black/5 dark:hover:bg-white/5 text-neutral-600 dark:text-neutral-300`}
                title={item.title}
              >
                <History size={15} className="shrink-0 text-neutral-400 group-hover:text-blue-500 transition-colors" />
                {isSidebarOpen && (
                  <div className="truncate flex-1">
                    <div className="truncate font-medium">{item.title}</div>
                    <div className="text-[10px] text-neutral-400">{item.time}</div>
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* 底部系统状态与偏好 */}
          <div className="p-3 border-t border-black/5 dark:border-white/5 flex flex-col gap-1">
            <button
              onClick={() => setIsDark(!isDark)}
              className="flex items-center gap-3 w-full py-2 px-3 rounded-xl text-xs text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              {isDark ? <Sun size={16} className="text-amber-400 shrink-0" /> : <Moon size={16} className="shrink-0" />}
              {isSidebarOpen && <span>{isDark ? "明亮外观 (Light)" : "深邃模式 (Dark)"}</span>}
            </button>

            <button
              onClick={() => setIsParamDrawerOpen(true)}
              className="flex items-center gap-3 w-full py-2 px-3 rounded-xl text-xs text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <Settings size={16} className="shrink-0" />
              {isSidebarOpen && <span>Agent 引擎参数</span>}
            </button>
          </div>
        </aside>

        {/* ---------------- 2. 移动端抽屉遮罩 (Mobile Drawer) ---------------- */}
        {isMobileDrawerOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden">
            <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setIsMobileDrawerOpen(false)} />
            <div className={`relative w-72 max-w-[80vw] h-full p-4 flex flex-col justify-between shadow-2xl z-10 ${
              isDark ? "bg-[#1E1F20]" : "bg-[#F0F4F9]"
            }`}>
              <div className="flex items-center justify-between pb-3 border-b border-black/5 dark:border-white/5">
                <span className="font-semibold text-sm bg-gradient-to-r from-blue-500 to-purple-600 bg-clip-text text-transparent">
                  Gemini Agent
                </span>
                <button onClick={() => setIsMobileDrawerOpen(false)} className="p-1 rounded-full hover:bg-black/5 dark:hover:bg-white/5">
                  <X size={18} />
                </button>
              </div>

              <div className="flex-1 py-4 overflow-y-auto space-y-2">
                <div className="text-xs font-semibold text-neutral-400">研判历史</div>
                {historyList.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => {
                      handleTriggerAnalysis("600584");
                      setIsMobileDrawerOpen(false);
                    }}
                    className="p-2.5 rounded-lg text-xs hover:bg-black/5 dark:hover:bg-white/5 cursor-pointer"
                  >
                    <div className="font-medium truncate">{item.title}</div>
                    <div className="text-[10px] text-neutral-400">{item.time}</div>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-black/5 dark:border-white/5 flex justify-between items-center text-xs">
                <button onClick={() => setIsDark(!isDark)} className="flex items-center gap-2 p-2">
                  {isDark ? <Sun size={15} /> : <Moon size={15} />}
                  <span>切换外观</span>
                </button>
                <span className="text-[10px] text-neutral-400">Gemini 1.5 Pro</span>
              </div>
            </div>
          </div>
        )}

        {/* ---------------- 3. 主交互视口 (Main Viewport Flow) ---------------- */}
        <main className="flex-1 flex flex-col h-full relative overflow-hidden">
          {/* 顶栏 (Top Minimal App Bar) */}
          <header className="h-14 flex items-center justify-between px-4 sm:px-8 border-b border-transparent z-10 shrink-0">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsMobileDrawerOpen(true)}
                className="md:hidden p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
              >
                <Menu size={18} />
              </button>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-base sm:text-lg tracking-tight bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                  A-Share Sentiment Agent
                </span>
                <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400">
                  <Zap size={11} className="mr-1 text-amber-500" />
                  双向闭环反思
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsParamDrawerOpen(!isParamDrawerOpen)}
                className={`p-2 rounded-full transition-all active:scale-95 ${
                  isParamDrawerOpen
                    ? "bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300"
                    : "hover:bg-black/5 dark:hover:bg-white/5 text-neutral-600 dark:text-neutral-300"
                }`}
                title="调整研判深度与引擎"
              >
                <SlidersHorizontal size={18} />
              </button>
              <button
                onClick={() => setIsDark(!isDark)}
                className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-all active:scale-95 text-neutral-600 dark:text-neutral-300"
                title="切换主题"
              >
                {isDark ? <Sun size={18} className="text-amber-400" /> : <Moon size={18} />}
              </button>
            </div>
          </header>

          {/* 参数抽屉 (Popover Drawer) */}
          {isParamDrawerOpen && (
            <div className="absolute top-14 right-4 sm:right-8 w-80 p-4 rounded-3xl shadow-2xl border backdrop-blur-xl z-30 transition-all animate-in fade-in zoom-in-95 bg-white/90 dark:bg-[#1E1F20]/95 border-black/5 dark:border-white/10">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-black/5 dark:border-white/5">
                <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200 flex items-center gap-1.5">
                  <SlidersHorizontal size={14} className="text-blue-500" />
                  引擎参数与消歧配置
                </span>
                <button
                  onClick={() => setIsParamDrawerOpen(false)}
                  className="p-1 rounded-full hover:bg-black/5 dark:hover:bg-white/5"
                >
                  <X size={14} />
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
                    className="w-full px-3 py-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 border-none outline-none focus:ring-2 focus:ring-blue-500 text-neutral-800 dark:text-neutral-100 font-mono text-xs"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-neutral-500 dark:text-neutral-400 mb-1 font-medium">
                    <span>散户发帖分析深度</span>
                    <span className="font-mono text-blue-600 dark:text-blue-400">{maxPosts} 条</span>
                  </div>
                  <input
                    type="range"
                    min={3}
                    max={15}
                    value={maxPosts}
                    onChange={(e) => setMaxPosts(Number(e.target.value))}
                    className="w-full accent-blue-600 cursor-pointer"
                  />
                  <div className="flex justify-between text-[10px] text-neutral-400 mt-0.5">
                    <span>3条(极速)</span>
                    <span>15条(深度)</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div>
                    <div className="font-medium text-neutral-800 dark:text-neutral-200">启用真实大模型思维链</div>
                    <div className="text-[10px] text-neutral-400">调用 Gemini / DeepSeek 识别反讽隐喻</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={useLLM}
                    onChange={(e) => setUseLLM(e.target.checked)}
                    className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                  />
                </div>

                <button
                  onClick={() => {
                    setIsParamDrawerOpen(false);
                    handleTriggerAnalysis();
                  }}
                  className="w-full py-2.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium text-xs shadow-md active:scale-95 transition-all flex items-center justify-center gap-1.5"
                >
                  <Sparkles size={13} />
                  保存并立即执行研判
                </button>
              </div>
            </div>
          )}

          {/* 消息滚动流 (Max-width Constrained Chat Stream) */}
          <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 pb-36 pt-4">
            <div className="max-w-4xl mx-auto space-y-8">
              {/* 空状态欢迎卡片 (Gemini 经典居中 Hero) */}
              {!activeSession && !isLoading && (
                <div className="py-12 sm:py-20 flex flex-col items-center text-center animate-in fade-in duration-500">
                  <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-blue-500 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-blue-500/20 mb-6">
                    <Sparkles size={32} />
                  </div>

                  <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight mb-3">
                    <span className="bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">
                      你好，投资研究员
                    </span>
                  </h1>
                  <p className="text-sm sm:text-base text-neutral-500 dark:text-neutral-400 max-w-lg mb-8 leading-relaxed">
                    基于 Gemini 大模型思维链消歧与实时行情基准，穿透散户黑话与反语，研判资金博弈背离。
                  </p>

                  {/* 快捷推荐卡片网格 (Prompt Recommendation Chips) */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl text-left">
                    {[
                      {
                        code: "600584",
                        name: "长电科技",
                        desc: "检测半导体封测龙头放量大涨下的散户恐慌割肉背离",
                        tag: "高位背离预警",
                      },
                      {
                        code: "600519",
                        name: "贵州茅台",
                        desc: "分析白酒消费核心资产震荡整理期的散户黑话反讽程度",
                        tag: "反讽消歧",
                      },
                      {
                        code: "002594",
                        name: "比亚迪",
                        desc: "新能源车出海催化下，验证股吧舆情与技术盘面共振性",
                        tag: "量价共振",
                      },
                      {
                        code: "601127",
                        name: "赛力斯",
                        desc: "智选车概念狂欢期，穿透『赢麻了』情绪陷阱与出货风险",
                        tag: "诱多甄别",
                      },
                    ].map((card) => (
                      <button
                        key={card.code}
                        onClick={() => handleTriggerAnalysis(card.code)}
                        className={`p-4 rounded-2xl border transition-all text-left flex flex-col justify-between group active:scale-[0.98] ${
                          isDark
                            ? "bg-[#1E1F20]/70 hover:bg-[#282A2C] border-white/5"
                            : "bg-white/80 hover:bg-white border-black/5 hover:shadow-md"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold text-sm text-neutral-900 dark:text-neutral-100 group-hover:text-blue-500 transition-colors">
                            {card.name} ({card.code})
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 font-medium">
                            {card.tag}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400 line-clamp-2 leading-relaxed">
                          {card.desc}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* 加载中状态 (Gemini 极光呼吸流光骨架) */}
              {isLoading && (
                <div className="py-10 space-y-6 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center text-white">
                      <Sparkles size={16} />
                    </div>
                    <div className="h-4 w-48 bg-neutral-200 dark:bg-neutral-800 rounded-full" />
                  </div>
                  <div className="space-y-3 pl-11">
                    <div className="h-28 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full" />
                    <div className="h-20 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full" />
                    <div className="h-40 bg-neutral-100 dark:bg-neutral-800/60 rounded-3xl w-full" />
                  </div>
                </div>
              )}

              {/* 渲染完整会话与结果 */}
              {activeSession && !isLoading && (
                <div className="space-y-8 animate-in fade-in duration-300">
                  {/* 用户提问胶囊气泡 (User Bubble) */}
                  <div className="flex justify-end">
                    <div className="max-w-xl rounded-3xl px-5 py-3.5 text-sm leading-relaxed shadow-sm bg-[#F0F4F9] dark:bg-[#282A2C] text-neutral-800 dark:text-neutral-100">
                      启动标的 <span className="font-semibold text-blue-600 dark:text-blue-400">[{activeSession.stock_name} ({activeSession.stock_code})]</span> 的舆情反讽消除与异动背离研判，抓取深度 {maxPosts} 条，{useLLM ? "启用" : "未启用"}真实大模型。
                    </div>
                  </div>

                  {/* Gemini 开放式排版 AI 响应区 */}
                  <div className="flex gap-4 items-start">
                    {/* Gemini 专属渐变 Sparkle 徽章 */}
                    <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-blue-500 via-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 shrink-0 mt-1">
                      <Sparkles size={18} />
                    </div>

                    <div className="flex-1 space-y-6 overflow-hidden">
                      {/* 1. L1 盘面四宫格行情芯片 (Surface Elevation Metric Chips) */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className={`p-4 rounded-3xl border transition-all ${
                          isDark ? "bg-[#1E1F20]/70 border-white/5" : "bg-white border-black/5 shadow-sm"
                        }`}>
                          <div className="text-[11px] text-neutral-400 mb-1">分析标的</div>
                          <div className="text-base font-semibold truncate">{activeSession.stock_name}</div>
                          <div className="text-[10px] text-neutral-500 font-mono">{activeSession.stock_code}</div>
                        </div>

                        <div className={`p-4 rounded-3xl border transition-all ${
                          isDark ? "bg-[#1E1F20]/70 border-white/5" : "bg-white border-black/5 shadow-sm"
                        }`}>
                          <div className="text-[11px] text-neutral-400 mb-1">最新成交价</div>
                          <div className={`text-base font-semibold font-mono ${
                            activeSession.market_data.change_percent >= 0 ? "text-red-500" : "text-emerald-500"
                          }`}>
                            {activeSession.market_data.current_price.toFixed(2)} 元
                          </div>
                          <div className="flex items-center text-[10px] font-semibold">
                            {activeSession.market_data.change_percent >= 0 ? (
                              <span className="text-red-500 flex items-center"><TrendingUp size={11} className="mr-0.5" />+{activeSession.market_data.change_percent}%</span>
                            ) : (
                              <span className="text-emerald-500 flex items-center"><TrendingDown size={11} className="mr-0.5" />{activeSession.market_data.change_percent}%</span>
                            )}
                          </div>
                        </div>

                        <div className={`p-4 rounded-3xl border transition-all ${
                          isDark ? "bg-[#1E1F20]/70 border-white/5" : "bg-white border-black/5 shadow-sm"
                        }`}>
                          <div className="text-[11px] text-neutral-400 mb-1">今日成交量能</div>
                          <div className="text-base font-semibold font-mono">{activeSession.market_data.turnover_amount_yi.toFixed(2)} 亿</div>
                          <div className="text-[10px] text-neutral-400">资金博弈活跃</div>
                        </div>

                        <div className={`p-4 rounded-3xl border transition-all ${
                          isDark ? "bg-[#1E1F20]/70 border-white/5" : "bg-white border-black/5 shadow-sm"
                        }`}>
                          <div className="text-[11px] text-neutral-400 mb-1">散户综合情绪分</div>
                          <div className={`text-base font-semibold font-mono ${
                            activeSession.average_sentiment < -0.3 ? "text-emerald-500" : activeSession.average_sentiment > 0.3 ? "text-red-500" : "text-amber-500"
                          }`}>
                            {activeSession.average_sentiment > 0 ? `+${activeSession.average_sentiment.toFixed(2)}` : activeSession.average_sentiment.toFixed(2)}
                          </div>
                          <div className="text-[10px] text-neutral-400">区间: [-1.0, +1.0]</div>
                        </div>
                      </div>

                      {/* 2. 背离研判雷达警报卡 (Divergence Radar Banner) */}
                      <div className={`p-5 rounded-3xl border relative overflow-hidden transition-all ${
                        activeSession.reflection.is_divergent
                          ? isDark
                            ? "bg-gradient-to-r from-red-950/20 via-[#1E1F20] to-[#1E1F20] border-red-500/30"
                            : "bg-gradient-to-r from-red-50 via-white to-white border-red-200"
                          : isDark
                          ? "bg-[#1E1F20] border-emerald-500/30"
                          : "bg-emerald-50/60 border-emerald-200"
                      }`}>
                        {/* 状态徽标与风险级别 */}
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                          <div className="flex items-center gap-2">
                            <span className="relative flex h-3 w-3">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                            </span>
                            <span className="font-semibold text-sm text-red-600 dark:text-red-400 flex items-center gap-1.5">
                              <ShieldAlert size={16} />
                              {activeSession.reflection.divergence_type}
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5">
                            <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">
                              风险等级: {activeSession.reflection.risk_level}
                            </span>
                          </div>
                        </div>

                        {/* 叙事论证 */}
                        <div className="text-xs sm:text-sm text-neutral-700 dark:text-neutral-300 leading-relaxed mb-4">
                          <strong className="text-neutral-900 dark:text-white font-medium">研判推导逻辑：</strong>
                          {activeSession.reflection.reflection_narrative}
                        </div>

                        {/* 操作策略胶囊 */}
                        <div className="p-3 rounded-2xl bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5 flex items-start gap-2.5 text-xs leading-relaxed">
                          <Info size={16} className="text-blue-500 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-medium text-neutral-900 dark:text-neutral-100">交易决策风控参考：</span>
                            <span className="text-neutral-600 dark:text-neutral-300">{activeSession.reflection.action_suggestion}</span>
                          </div>
                        </div>
                      </div>

                      {/* 3. Gemini 经典思维链折叠面板 (Thinking Process Accordion) */}
                      <div className="rounded-3xl border border-black/5 dark:border-white/5 overflow-hidden bg-black/[0.02] dark:bg-white/[0.02]">
                        <button
                          onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                          className="w-full px-5 py-3 flex items-center justify-between text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <Bot size={15} className="text-indigo-500" />
                            <span>Gemini 大模型思维链语义推理过程 ({activeSession.reflection.thinking_steps.length} 个步骤)</span>
                          </div>
                          {isThinkingExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
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

                      {/* 4. 散户发帖语料与反讽消歧明细瀑布 (Sarcasm & Slang Analysis Cards) */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between px-1">
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-neutral-500 flex items-center gap-1.5">
                            <BarChart3 size={14} />
                            散户语料样本与消歧详情 ({activeSession.sentiment_list.length} 条样本)
                          </h3>
                          <span className="text-[11px] text-neutral-400">已消除反话倒装与黑话歧义</span>
                        </div>

                        <div className="space-y-3">
                          {activeSession.sentiment_list.map((item) => (
                            <div
                              key={item.id}
                              className={`p-4 rounded-3xl border transition-all ${
                                isDark
                                  ? "bg-[#1E1F20]/50 hover:bg-[#1E1F20] border-white/5"
                                  : "bg-white hover:bg-neutral-50/80 border-black/5 shadow-sm"
                              }`}
                            >
                              {/* 头部标签与评分 */}
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
                                      <Flame size={11} className="text-amber-500 animate-bounce" />
                                      反讽语义翻转
                                    </span>
                                  )}

                                  {item.slang_detected.map((slang, sIdx) => (
                                    <span
                                      key={sIdx}
                                      className="px-2 py-0.5 rounded-md text-[10px] bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 font-mono"
                                    >
                                      #{slang}
                                    </span>
                                  ))}
                                </div>

                                <div className="font-mono text-xs font-semibold text-neutral-500">
                                  情绪评分:{" "}
                                  <span className={item.sentiment_score >= 0 ? "text-red-500" : "text-emerald-500"}>
                                    {item.sentiment_score > 0 ? `+${item.sentiment_score.toFixed(2)}` : item.sentiment_score.toFixed(2)}
                                  </span>
                                </div>
                              </div>

                              {/* 原始发帖 */}
                              <div className="text-xs sm:text-sm text-neutral-800 dark:text-neutral-200 mb-2 pl-3 border-l-2 border-neutral-300 dark:border-neutral-700 italic">
                                “{item.original_post}”
                              </div>

                              {/* 模型思考依据 */}
                              <div className="text-[11px] text-neutral-500 dark:text-neutral-400 flex items-start gap-1.5 pt-1">
                                <Sparkles size={12} className="text-blue-500 shrink-0 mt-0.5" />
                                <span>大模型反思依据: {item.reasoning}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* 5. 消息底部 Hover 渐入工具条 (Gemini Message Actions) */}
                      <div className="flex items-center gap-1 text-neutral-400 pt-2 border-t border-black/5 dark:border-white/5">
                        <button
                          onClick={() => handleCopy(activeSession.reflection.reflection_narrative, "report")}
                          className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200"
                          title="复制研判结论"
                        >
                          {copiedId === "report" ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                        </button>
                        <button
                          onClick={() => handleTriggerAnalysis(activeSession.stock_code)}
                          className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200"
                          title="重新研判"
                        >
                          <RotateCcw size={14} />
                        </button>
                        <button className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200" title="结论准确">
                          <ThumbsUp size={14} />
                        </button>
                        <button className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200" title="结论偏差">
                          <ThumbsDown size={14} />
                        </button>
                        <button className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200" title="导出简报">
                          <Share2 size={14} />
                        </button>
                        <div className="ml-auto text-[10px] text-neutral-400">
                          Gemini 1.5 Flash · 耗时 1.2s · {activeSession.timestamp}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ---------------- 4. 视口中下方悬浮复合胶囊输入舱 (Floating Input Pill) ---------------- */}
          <div className="absolute bottom-0 left-0 right-0 p-4 sm:p-6 pointer-events-none z-20 flex justify-center">
            <div className="w-full max-w-3xl pointer-events-auto">
              <div className={`p-2 sm:p-2.5 rounded-3xl sm:rounded-full shadow-2xl border backdrop-blur-2xl transition-all ${
                isDark
                  ? "bg-[#1E1F20]/85 border-white/10 shadow-black/60"
                  : "bg-white/85 border-black/10 shadow-slate-200/80"
              }`}>
                <div className="flex items-center gap-2">
                  {/* 股票代码快捷胶囊 */}
                  <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/5 dark:bg-white/5 text-xs text-neutral-600 dark:text-neutral-300 font-mono">
                    <Search size={13} className="text-neutral-400" />
                    <input
                      type="text"
                      value={stockCode}
                      onChange={(e) => setStockCode(e.target.value)}
                      placeholder="代码 (如 600584)"
                      className="bg-transparent border-none outline-none w-24 text-xs font-mono"
                    />
                  </div>

                  {/* 自然语言指令输入框 */}
                  <input
                    type="text"
                    value={naturalPrompt}
                    onChange={(e) => setNaturalPrompt(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        handleTriggerAnalysis();
                      }
                    }}
                    placeholder={stockCode ? `研判 [${stockCode}] 的主力意图与散户反讽背离...` : "输入 6 位 A 股股票代码或研判指令..."}
                    className="flex-1 bg-transparent px-3 py-2 text-xs sm:text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 outline-none border-none"
                  />

                  {/* 快捷参数设置触发按钮 */}
                  <button
                    onClick={() => setIsParamDrawerOpen(!isParamDrawerOpen)}
                    className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-colors"
                    title="配置样本深度"
                  >
                    <SlidersHorizontal size={17} />
                  </button>

                  {/* 极具 Gemini 灵魂的渐变发送/执行按钮 */}
                  <button
                    onClick={() => handleTriggerAnalysis()}
                    disabled={isLoading}
                    className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white flex items-center justify-center shadow-md active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                    title="启动智能研判"
                  >
                    {isLoading ? <RotateCcw size={17} className="animate-spin" /> : <Send size={16} className="ml-0.5" />}
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
    </div>
  );
};

export default GeminiSentimentDashboard;
