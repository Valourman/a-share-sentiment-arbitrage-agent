from typing import Any, Dict, Optional
from rich.console import Console

from src.core.agent import BaseAgent
from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.agent.base_reflection import ReflectionAgent
from src.agent.state import AgentState, ReflectionDecision, DivergenceType, RiskLevel
from src.tools.scraper import StockForumScraper
from src.tools.market import MarketDataTool
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.registry import ToolRegistry, global_tool_registry

console = Console()


class SentimentArbitrageAgent(ReflectionAgent):
    """
    面向 A 股市场的多源舆情反讽研判与盘面背离预警 Agent
    派生自 Hello Agents 标准 ReflectionAgent 范式
    具备：
    1. 多源感知采集 (execute_initial)
    2. 客观盘面基准对照与批判审查 (evaluate_critique)
    3. 背离反思与决策自愈闭环 (reflect_and_refine)
    """
    def __init__(
        self,
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        super().__init__(
            name="SentimentArbitrageAgent",
            llm=llm or HelloAgentsLLM(),
            tools=tools or global_tool_registry,
        )
        # 获取或注册具象工具
        self.scraper: StockForumScraper = self.tools.get("stock_scraper") or StockForumScraper()
        self.market_tool: MarketDataTool = self.tools.get("market_data") or MarketDataTool()
        self.analyzer: FinancialSentimentAnalyzer = (
            self.tools.get("sentiment_analyzer") or FinancialSentimentAnalyzer(llm=self.llm)
        )

    def execute_initial(self, stock_code: str, **kwargs: Any) -> AgentState:
        """步骤一：多源情报并行采集与散户语义深度消歧"""
        max_posts = kwargs.get("max_posts", 30)
        use_llm = kwargs.get("use_llm", True)

        console.print(f"[bold cyan]>>> 启动 Agent 多源立体研判任务: 标的代码 [{stock_code}][/bold cyan]")
        state = AgentState(stock_code=stock_code)
        state.iteration_count = 1

        # 1. 多源信息采集
        console.print("[yellow]Step 1/4: 正在多方位并发采集多源金融情报 (股吧全量+主流新闻+官方公告)...[/yellow]")
        posts = self.scraper.fetch_guba_posts(stock_code, max_posts=max_posts)
        news = self.scraper.fetch_financial_news(stock_code, max_items=5)
        announcements = self.scraper.fetch_announcements(stock_code, max_items=4)

        state.news_list = news
        state.announcements = announcements
        console.print(f"   -> 成功捕获 [green]{len(posts)}[/green] 条真实散户有效发帖 (全量最大深度)")
        console.print(f"   -> 成功汇聚 [cyan]{len(news)}[/cyan] 条主流财经资讯研报与主力动向")
        console.print(f"   -> 成功提取 [magenta]{len(announcements)}[/magenta] 份上市公司官方权威披露")

        # 2. 散户情绪全量消歧与反讽识别
        mode_desc = "大模型思维链(LLM)" if use_llm else "启发式规则(Mock)"
        console.print(f"[yellow]Step 2/4: 执行全量散户语料深度消歧 (模式: {mode_desc}, 样本量: {len(posts)})...[/yellow]")
        total_score = 0.0
        for p in posts:
            if use_llm:
                res = self.analyzer.analyze_with_llm(p)
            else:
                res = self.analyzer.analyze_mock(p)
            state.sentiment_list.append(res)
            total_score += res.sentiment_score

        if state.sentiment_list:
            state.average_sentiment = round(total_score / len(state.sentiment_list), 2)
        console.print(f"   -> 散户全样本综合情绪指数: [bold magenta]{state.average_sentiment}[/bold magenta] (区间: -1.0 极度看空 到 +1.0 极度看多)")

        return state

    def evaluate_critique(self, initial_result: AgentState, **kwargs: Any) -> Dict[str, Any]:
        """步骤二：调用确定性行情事实源提取客观盘面数据，进行交叉对照"""
        state = initial_result
        stock_code = state.stock_code

        console.print("[yellow]Step 3/4: 提取秒级客观盘面事实行情 (基准数据)...[/yellow]")
        market_snap = self.market_tool.fetch_snapshot(stock_code)
        state.market_data = market_snap
        state.stock_name = market_snap.stock_name
        console.print(f"   -> 标的: [bold]{market_snap.stock_name}[/bold], 现价: {market_snap.current_price}, 涨跌: {market_snap.change_percent}%, 成交额: {market_snap.turnover_amount_yi}亿")

        sentiment = state.average_sentiment
        chg_pct = market_snap.change_percent if market_snap else 0.0

        # 判断客观盘面与主观情绪是否存在背离冲突
        is_divergent = False
        divergence_label = DivergenceType.CONSISTENT
        risk_level = RiskLevel.LOW

        if sentiment >= 0.20 and chg_pct < -0.5:
            is_divergent = True
            divergence_label = DivergenceType.BULL_TRAP
            risk_level = RiskLevel.HIGH
        elif sentiment <= -0.20 and chg_pct >= 0.0:
            is_divergent = True
            divergence_label = DivergenceType.PANIC_BOTTOM
            risk_level = RiskLevel.MEDIUM

        return {
            "is_divergent": is_divergent,
            "divergence_label": divergence_label,
            "risk_level": risk_level,
            "sentiment": sentiment,
            "chg_pct": chg_pct,
        }

    def _reflect_on_divergence(self, state: AgentState) -> ReflectionDecision:
        """核心反思逻辑：对照主观情绪与客观盘面背离"""
        sentiment = state.average_sentiment
        chg_pct = state.market_data.change_percent if state.market_data else 0.0
        news_count = len(state.news_list)
        news_hint = f"（同步监控到主流财经媒体近{news_count}篇深度资讯与机构动向）" if news_count > 0 else ""

        if sentiment >= 0.20 and chg_pct < -0.5:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type=DivergenceType.BULL_TRAP,
                risk_level=RiskLevel.HIGH,
                reflection_narrative=f"散户全样本情绪指数呈现偏乐观态度(+{sentiment})，频繁出现追涨抬轿言论；但盘面客观实际处于下挫形态({chg_pct}%)。结合多源新闻显示主力资金可能处于分歧出货阶段{news_hint}。存在明显多头诱多或散户不理性抄底被套特征。",
                action_suggestion="警惕盘面诱多与阴跌风险，不宜盲目跟风抄底，建议轻仓观望，等待放量企稳。",
            )
        elif sentiment <= -0.20 and chg_pct >= 0.0:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type=DivergenceType.PANIC_BOTTOM,
                risk_level=RiskLevel.MEDIUM,
                reflection_narrative=f"散户社区大面积充斥关灯吃面、保卫战等悲观绝望言论({sentiment})，但盘面实际抗跌翻红({chg_pct}%)，量能维持活跃。结合专业资讯研报，筹码正在向主力或机构资金逆向沉淀{news_hint}。",
                action_suggestion="左侧散户恐慌盘逐步出清，可密切关注量价企稳与右侧反弹突破信号，分批布局。",
            )
        else:
            return ReflectionDecision(
                is_divergent=False,
                divergence_type=DivergenceType.CONSISTENT,
                risk_level=RiskLevel.LOW,
                reflection_narrative=f"散户全量情绪指数({sentiment})与盘面实际涨跌({chg_pct}%)趋势基本一致，市场各方博弈处于均衡区间{news_hint}。",
                action_suggestion="情绪与价格走势共振，按常规量价指标与上市公司基本面策略执行。",
            )

    def reflect_and_refine(
        self,
        initial_result: AgentState,
        critique: Dict[str, Any],
        **kwargs: Any,
    ) -> AgentState:
        """步骤三：反思背离根源，生成可解释性因果推导建议"""
        console.print("[yellow]Step 4/4: 触发多源立体反思机制 (Reflection Loop)...[/yellow]")
        state = initial_result
        state.reflection = self._reflect_on_divergence(state)
        return state

    def run(self, stock_code: str, max_posts: int = 30, use_llm: bool = True, **kwargs: Any) -> AgentState:
        """
        启动多源交叉金融研判 Agent 任务
        完全保持原有的调用签名与返回数据类型兼容性
        """
        self.add_message(Message.user(f"研判标的股票代码: {stock_code}"))
        state = self.execute_initial(stock_code, max_posts=max_posts, use_llm=use_llm, **kwargs)
        critique = self.evaluate_critique(state, **kwargs)
        final_state = self.reflect_and_refine(state, critique, **kwargs)
        self.add_message(Message.assistant(f"完成标的 [{stock_code}] 研判报告"))
        return final_state
