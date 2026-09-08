from src.agent.state import AgentState, ReflectionDecision
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

    def run(self, stock_code: str, max_posts: int = 10, use_llm: bool = True) -> AgentState:
        console.print(f'[bold cyan]>>> 启动 Agent 研判任务: 标的代码 [{stock_code}][/bold cyan]')
        state = AgentState(stock_code=stock_code)

        # 1. 采集舆情发帖
        console.print('[yellow]Step 1/4: 正在检索股吧舆情并进行水军过滤...[/yellow]')
        posts = self.scraper.fetch_guba_posts(stock_code, max_posts=max_posts)
        console.print(f'   -> 成功提取 [green]{len(posts)}[/green] 条高价值散户发帖')

        # 2. 情绪分析与黑话/反讽识别
        console.print('[yellow]Step 2/4: 执行深度语义消歧 (识别散户黑话与反讽)...[/yellow]')
        total_score = 0.0
        for p in posts:
            res = self.analyzer.analyze_mock(p)
            state.sentiment_list.append(res)
            total_score += res.sentiment_score
        
        if state.sentiment_list:
            state.average_sentiment = round(total_score / len(state.sentiment_list), 2)
        console.print(f'   -> 散户综合情绪指数: [bold magenta]{state.average_sentiment}[/bold magenta] (区间: -1.0 极度看空 到 +1.0 极度看多)')

        # 3. 盘面真实数据交叉验证
        console.print('[yellow]Step 3/4: 提取盘面客观事实行情 (确定性基准数据)...[/yellow]')
        market_snap = self.market_tool.fetch_snapshot(stock_code)
        state.market_data = market_snap
        state.stock_name = market_snap.stock_name
        console.print(f'   -> 标的: [bold]{market_snap.stock_name}[/bold], 现价: {market_snap.current_price}, 今日涨跌: {market_snap.change_percent}%, 成交额: {market_snap.turnover_amount_yi}亿')

        # 4. 批判性反思与背离研判 (Reflection Loop)
        console.print('[yellow]Step 4/4: 触发交叉反思机制 (Reflection Loop)...[/yellow]')
        reflection = self._reflect_on_divergence(state)
        state.reflection = reflection
        return state

    def _reflect_on_divergence(self, state: AgentState) -> ReflectionDecision:
        sentiment = state.average_sentiment
        chg_pct = state.market_data.change_percent if state.market_data else 0.0

        # 情况 A: 散户情绪亢奋看多 (>=0.25)，但盘面下挫 (< -0.5%) -> 诱多/踩踏风险
        if sentiment >= 0.25 and chg_pct < -0.5:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type='BULL_TRAP',
                risk_level='HIGH',
                reflection_narrative=f'散户情绪指数呈现偏乐观态度(+{sentiment})，频繁出现主升浪等期待；但盘面客观实际处于下挫形态({chg_pct}%)。存在明显多头诱多或散户不理性抄底被套特征。',
                action_suggestion='警惕盘面诱多与阴跌风险，不宜盲目跟风抄底，建议轻仓观望。'
            )

        # 情况 B: 散户极度恐慌割肉 (<= -0.25)，但盘面抗跌翻红 (>= 0.0%) -> 恐慌盘磨底
        elif sentiment <= -0.25 and chg_pct >= 0.0:
            return ReflectionDecision(
                is_divergent=True,
                divergence_type='PANIC_BOTTOM',
                risk_level='MEDIUM',
                reflection_narrative=f'散户社区充斥关灯吃面、保卫战等悲观绝望言论({sentiment})，但盘面实际抗跌翻红({chg_pct}%)，筹码可能正在向主力资金集中。',
                action_suggestion='左侧恐慌盘逐步出清，可密切关注量价企稳与右侧反弹信号。'
            )

        # 情况 C: 盘面与情绪高度一致
        else:
            return ReflectionDecision(
                is_divergent=False,
                divergence_type='CONSISTENT',
                risk_level='LOW',
                reflection_narrative=f'散户情绪指数({sentiment})与盘面实际涨跌({chg_pct}%)趋势基本一致，市场处于理性定价区间。',
                action_suggestion='情绪与价格走势共振，按常规技术指标和基本面策略执行。'
            )