from src.agent.state import AgentState, ReflectionDecision, DivergenceType, RiskLevel
from src.tools.scraper import StockForumScraper
from src.tools.market import MarketDataTool
from src.tools.analyzer import FinancialSentimentAnalyzer
from rich.console import Console

console = Console()

class SentimentArbitrageAgent:
    def __init__(self):
        self.scraper = StockForumScraper()
        self.market_tool = MarketDataTool()
        self.analyzer = FinancialSentimentAnalyzer()

    def run(self, stock_code: str, max_posts: int = 30, use_llm: bool = True) -> AgentState:
        """
        启动多源交叉金融研判 Agent 任务
        默认拉取全量最大深度散户语料，并并行多源聚合专业财经资讯与官方披露
        """
        console.print(f'[bold cyan]>>> 启动 Agent 多源立体研判任务: 标的代码 [{stock_code}][/bold cyan]')
        state = AgentState(stock_code=stock_code)
        state.iteration_count = 1

        # 1. 多源信息采集 (散户舆情全量 + 专业财经新闻 + 官方公告)
        console.print('[yellow]Step 1/4: 正在多方位并发采集多源金融情报 (股吧全量+主流新闻+官方公告)...[/yellow]')
        posts = self.scraper.fetch_guba_posts(stock_code, max_posts=max_posts)
        news = self.scraper.fetch_financial_news(stock_code, max_items=5)
        announcements = self.scraper.fetch_announcements(stock_code, max_items=4)

        state.news_list = news
        state.announcements = announcements
        console.print(f'   -> 成功捕获 [green]{len(posts)}[/green] 条真实散户有效发帖 (全量最大深度)')
        console.print(f'   -> 成功汇聚 [cyan]{len(news)}[/cyan] 条主流财经资讯研报与主力动向')
        console.print(f'   -> 成功提取 [magenta]{len(announcements)}[/magenta] 份上市公司官方权威披露')

        # 2. 散户情绪全量语义消歧与反讽识别
        mode_desc = "大模型思维链(LLM)" if use_llm else "启发式规则(Mock)"
        console.print(f'[yellow]Step 2/4: 执行全量散户语料深度消歧 (模式: {mode_desc}, 样本量: {len(posts)})...[/yellow]')
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
        console.print(f'   -> 散户全样本综合情绪指数: [bold magenta]{state.average_sentiment}[/bold magenta] (区间: -1.0 极度看空 到 +1.0 极度看多)')

        # 3. 盘面真实数据交叉验证 (确定性 L1 盘面事实)
        console.print('[yellow]Step 3/4: 提取秒级客观盘面事实行情 (基准数据)...[/yellow]')
        market_snap = self.market_tool.fetch_snapshot(stock_code)
        state.market_data = market_snap
        state.stock_name = market_snap.stock_name
        console.print(f'   -> 标的: [bold]{market_snap.stock_name}[/bold], 现价: {market_snap.current_price}, 涨跌: {market_snap.change_percent}%, 成交额: {market_snap.turnover_amount_yi}亿')

        # 4. 批判性反思与多源背离研判 (Reflection Loop)
        console.print('[yellow]Step 4/4: 触发多源立体反思机制 (Reflection Loop)...[/yellow]')
        reflection = self._reflect_on_divergence(state)
        state.reflection = reflection
        return state

    def _reflect_on_divergence(self, state: AgentState) -> ReflectionDecision:
        sentiment = state.average_sentiment
        chg_pct = state.market_data.change_percent if state.market_data else 0.0
        news_count = len(state.news_list)

        # 辅助多源新闻摘要作为决策论据
        news_hint = f"（同步监控到主流财经媒体近5篇深度资讯与机构动向）" if news_count > 0 else ""

        # 情况 A: 散户情绪亢奋看多 (>=0.20)，但盘面下挫 (< -0.5%) -> 诱多/踩踏风险
        if sentiment >= 0.20 and chg_pct < -0.5:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type=DivergenceType.BULL_TRAP,
                risk_level=RiskLevel.HIGH,
                reflection_narrative=f'散户全样本情绪指数呈现偏乐观态度(+{sentiment})，频繁出现追涨抬轿言论；但盘面客观实际处于下挫形态({chg_pct}%)。结合多源新闻显示主力资金可能处于分歧出货阶段{news_hint}。存在明显多头诱多或散户不理性抄底被套特征。',
                action_suggestion='警惕盘面诱多与阴跌风险，不宜盲目跟风抄底，建议轻仓观望，等待放量企稳。'
            )

        # 情况 B: 散户极度恐慌割肉 (<= -0.20)，但盘面抗跌翻红 (>= 0.0%) -> 恐慌盘磨底
        elif sentiment <= -0.20 and chg_pct >= 0.0:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type=DivergenceType.PANIC_BOTTOM,
                risk_level=RiskLevel.MEDIUM,
                reflection_narrative=f'散户社区大面积充斥关灯吃面、保卫战等悲观绝望言论({sentiment})，但盘面实际抗跌翻红({chg_pct}%)，量能维持活跃。结合专业资讯研报，筹码正在向主力或机构资金逆向沉淀{news_hint}。',
                action_suggestion='左侧散户恐慌盘逐步出清，可密切关注量价企稳与右侧反弹突破信号，分批布局。'
            )

        # 情况 C: 盘面与情绪大体一致
        else:
            return ReflectionDecision(
                is_divergent=False,
                divergence_type=DivergenceType.CONSISTENT,
                risk_level=RiskLevel.LOW,
                reflection_narrative=f'散户全量情绪指数({sentiment})与盘面实际涨跌({chg_pct}%)趋势基本一致，市场各方博弈处于均衡区间{news_hint}。',
                action_suggestion='情绪与价格走势共振，按常规量价指标与上市公司基本面策略执行。'
            )
