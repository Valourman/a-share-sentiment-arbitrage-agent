from typing import Any, Callable, Dict, Optional
from datetime import datetime
from rich.console import Console

from src.core.llm import HelloAgentsLLM
from src.core.message import Message
from src.agent.base_reflection import ReflectionAgent
from src.agent.decision import (
    DivergenceAssessment,
    assess_divergence,
    build_reflection_decision,
    has_valid_market_snapshot,
)
from src.agent.state import AgentState, ReflectionDecision
from src.core.tracer import AgentTracer
from src.tools.scraper import StockForumScraper
from src.tools.market import MarketDataTool
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.registry import ToolRegistry, global_tool_registry
from src.workflow.pipeline import FinancialWorkflowPipeline
from src.workflow.nodes import FundamentalCatalystNode, MultiAgentDebateNode

console = Console()


class SentimentArbitrageAgent(ReflectionAgent):
    """
    面向 A 股市场的多源舆情反讽研判与盘面背离预警 Agent
    融合 Hello Agents 标准架构与 GitHub 热门金融多智能体 (FinRobot / TradingAgents) 范式：
    具备：
    1. 并发感知流与散户反讽穿透消歧
    2. 基本面催化剂与风险归因提炼
    3. 多智能体多空对抗辩论 (Bull vs Bear Debate Protocol)
    4. 秒级客观事实盘面交叉对照与背离终审决策
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

        configured_analyzer = tools.get("sentiment_analyzer") if tools is not None else None
        self.analyzer: FinancialSentimentAnalyzer = configured_analyzer or FinancialSentimentAnalyzer(llm=self.llm)

        # 现代化金融工作流流水线编排器
        self.pipeline: FinancialWorkflowPipeline = FinancialWorkflowPipeline(
            llm=self.llm,
            tools=self.tools,
        )
        # 执行链路追踪器 (每次 run 自动重置，可通过 get_summary() 获取汇总指标)
        self.tracer: AgentTracer = AgentTracer()

    def execute_initial(self, stock_code: str, **kwargs: Any) -> AgentState:
        """步骤一：多源情报并行采集与散户语义深度消歧"""
        max_posts = kwargs.get("max_posts", 30)
        use_llm = kwargs.get("use_llm", True)
        engine_mode: Optional[str] = kwargs.get("engine_mode")
        progress_callback: Optional[Callable[[float, str], None]] = kwargs.get("progress_callback")

        console.print(f"[bold cyan]>>> 启动 Agent 多源立体研判任务: 标的代码 [{stock_code}][/bold cyan]")
        state = AgentState(stock_code=stock_code)
        state.iteration_count = 1

        # 1. 多源信息采集
        if progress_callback:
            progress_callback(0.15, f"Step 1/4: 正在多方位并发采集 [{stock_code}] 股吧、新闻与官方披露...")
        console.print("[yellow]Step 1/4: 正在多方位并发采集多源金融情报 (股吧全量+主流新闻+官方公告)...[/yellow]")
        with self.tracer.span("intel_collection", "tool", inputs={"stock_code": stock_code, "max_posts": max_posts}) as span:
            posts = self.scraper.fetch_guba_posts(stock_code, max_posts=max_posts)
            news = self.scraper.fetch_financial_news(stock_code, max_items=5)
            announcements = self.scraper.fetch_announcements(stock_code, max_items=4)
            span.outputs = {"posts": len(posts), "news": len(news), "announcements": len(announcements)}

        state.news_list = news
        state.announcements = announcements
        state.sentiment_sample_count = len(posts)

        # 提取基本面催化与风险项
        cat_node = FundamentalCatalystNode(llm=self.llm)
        catalysts, risks = cat_node.run(news, announcements, stock_name=state.stock_name)
        state.catalysts = catalysts
        state.risks = risks

        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(
            f"[{now_str}] [情报采集] 启动标的 [{stock_code}] 多方位全景研判，捕获股吧发帖 {len(posts)} 条，主流资讯 {len(news)} 篇，权威公告 {len(announcements)} 份"
        )
        console.print(f"   -> 成功捕获 [green]{len(posts)}[/green] 条真实散户有效发帖 (全量最大深度)")
        console.print(f"   -> 成功汇聚 [cyan]{len(news)}[/cyan] 条主流财经资讯研报与主力动向")
        console.print(f"   -> 成功提取 [magenta]{len(announcements)}[/magenta] 份上市公司官方权威披露")

        # 2. 散户情绪全量消歧与反讽识别
        if engine_mode:
            mode_desc = f"引擎分发模式({engine_mode.upper()})"
        else:
            mode_desc = "大模型思维链(LLM)" if use_llm else "启发式规则(Mock)"
        if progress_callback:
            progress_callback(0.45, f"Step 2/4: 执行全量散户语料反讽消歧 (样本量: {len(posts)})...")
        console.print(f"[yellow]Step 2/4: 执行全量散户语料深度消歧 (模式: {mode_desc}, 样本量: {len(posts)})...[/yellow]")
        total_score = 0.0
        with self.tracer.span("sentiment_disambiguation", "llm", inputs={"samples": len(posts), "engine_mode": engine_mode or ("llm" if use_llm else "mock")}) as span:
            for idx, p in enumerate(posts):
                if engine_mode:
                    res = self.analyzer.analyze(p, engine_mode=engine_mode)
                elif use_llm:
                    res = self.analyzer.analyze_with_llm(p)
                else:
                    res = self.analyzer.analyze_mock(p)
                state.sentiment_list.append(res)
                total_score += res.sentiment_score

                # 结构化记录单条语料消歧日志
                t_str = datetime.now().strftime("%H:%M:%S")
                raw_stance = getattr(res.stance, "value", str(res.stance))
                slang_str = f"#{', #'.join(res.slang_detected)}" if res.slang_detected else "无特殊黑话"
                sarcasm_str = "【识别到反讽语义翻转】" if res.is_sarcasm else "无反讽"
                post_brief = (p.title[:45] + "...") if len(p.title) > 48 else p.title
                state.execution_logs.append(
                    f"[{t_str}] [语料消歧 #{idx+1:02d}] 语料: “{post_brief}” | "
                    f"立场: {raw_stance} | 情绪分值: {res.sentiment_score:+.2f} | "
                    f"黑话: {slang_str} | 反讽: {sarcasm_str} | "
                    f"大模型消歧依据: {res.reasoning}"
                )
            span.outputs = {"analyzed": len(state.sentiment_list)}

        if state.sentiment_list:
            state.average_sentiment = round(total_score / len(state.sentiment_list), 2)
        state.execution_logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] [情绪聚合] 完成 {len(state.sentiment_list)} 条散户语料消歧，全样本情绪指数定格为: {state.average_sentiment:+.2f} (区间: -1.0 极度看空 到 +1.0 极度看多)"
        )
        console.print(f"   -> 散户全样本综合情绪指数: [bold magenta]{state.average_sentiment}[/bold magenta] (区间: -1.0 极度看空 到 +1.0 极度看多)")

        return state

    def evaluate_critique(self, initial_result: AgentState, **kwargs: Any) -> Dict[str, Any]:
        """步骤二：调用确定性行情事实源提取客观盘面数据，进行交叉对照"""
        state = initial_result
        stock_code = state.stock_code
        progress_callback: Optional[Callable[[float, str], None]] = kwargs.get("progress_callback")

        if progress_callback:
            progress_callback(0.75, f"Step 3/4: 提取 [{stock_code}] 秒级客观盘面事实量价基准...")
        console.print("[yellow]Step 3/4: 提取秒级客观盘面事实行情 (基准数据)...[/yellow]")
        with self.tracer.span("market_snapshot", "tool", inputs={"stock_code": stock_code}) as span:
            market_snap = self.market_tool.fetch_snapshot(stock_code)
            span.outputs = {
                "stock_name": market_snap.stock_name,
                "change_percent": market_snap.change_percent,
                "valid": has_valid_market_snapshot(market_snap),
            }
        state.market_data = market_snap
        state.stock_name = market_snap.stock_name
        if has_valid_market_snapshot(market_snap):
            console.print(f"   -> 标的: [bold]{market_snap.stock_name}[/bold], 现价: {market_snap.current_price}, 涨跌: {market_snap.change_percent}%, 成交额: {market_snap.turnover_amount_yi}亿")
            state.execution_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] [行情事实对照] 提取标的 [{market_snap.stock_name}] 盘面事实基准: "
                f"现价 {market_snap.current_price:.2f} 元 | 日内变动 {market_snap.change_percent:+.2f}% | 成交量能 {market_snap.turnover_amount_yi:.2f} 亿元"
            )
        else:
            console.print("   -> 行情数据不可用：不把零值快照当作有效价格")
            state.execution_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] [行情事实对照] 未取得有效行情快照，暂停背离判定"
            )

        return assess_divergence(state).as_dict()

    def _reflect_on_divergence(
        self, state: AgentState, critique: Optional[Dict[str, Any]] = None
    ) -> ReflectionDecision:
        """Compose a decision from the same assessment used by the critique."""
        assessment = DivergenceAssessment.from_dict(critique) if critique is not None else assess_divergence(state)
        return build_reflection_decision(state, assessment)

    def reflect_and_refine(
        self,
        initial_result: AgentState,
        critique: Dict[str, Any],
        **kwargs: Any,
    ) -> AgentState:
        """步骤三：反思背离根源，生成可解释性因果推导建议"""
        progress_callback: Optional[Callable[[float, str], None]] = kwargs.get("progress_callback")
        if progress_callback:
            progress_callback(0.90, "Step 4/4: 触发多源立体反思机制 (Reflection Loop)...")
        console.print("[yellow]Step 4/4: 触发多源立体反思机制 (Reflection Loop)...[/yellow]")
        state = initial_result
        with self.tracer.span("divergence_reflection", "reflect", inputs={"average_sentiment": state.average_sentiment}) as span:
            state.reflection = self._reflect_on_divergence(state, critique)
            span.outputs = {"divergence_type": getattr(state.reflection.divergence_type, "value", str(state.reflection.divergence_type))}

        # 构建多智能体博弈辩论结果
        if state.debate_result is None:
            debate_node = MultiAgentDebateNode(llm=self.llm)
            state.debate_result = debate_node.run(state, state.catalysts, state.risks)

        if state.reflection:
            ref = state.reflection
            div_val = getattr(ref.divergence_type, "value", str(ref.divergence_type))
            risk_val = getattr(ref.risk_level, "value", str(ref.risk_level))
            state.execution_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] [多维反思决策] 背离研判: {div_val} (风险等级: {risk_val}) | "
                f"风控策略建议: {ref.action_suggestion}"
            )
        return state

    def run(self, stock_code: str, max_posts: int = 30, use_llm: bool = True, **kwargs: Any) -> AgentState:
        """
        启动多源交叉金融研判 Agent 任务
        融合 Hello Agents 经典反思范式与现代化多智能体博弈辩论：
        - 默认模式：执行 execute_initial -> evaluate_critique -> reflect_and_refine 4阶段反思闭环，
                    并自动附带基本面催化剂挖掘与多空多智能体辩论 (Bull vs Bear Debate)；
        - workflow_mode=True: 切换为纯并发流水线编排器 (FinancialWorkflowPipeline)。
        """
        workflow_mode: bool = kwargs.get("workflow_mode", False)
        progress_callback: Optional[Callable[[float, str], None]] = kwargs.get("progress_callback")

        # 每次研判重置链路追踪器，避免跨任务累计
        self.tracer = AgentTracer()
        self.add_message(Message.user(f"研判标的股票代码: {stock_code}"))

        if workflow_mode:
            final_state = self.pipeline.run(
                stock_code=stock_code,
                max_posts=max_posts,
                use_llm=use_llm,
                engine_mode=kwargs.get("engine_mode"),
                progress_callback=progress_callback,
                tracer=self.tracer,
            )
        else:
            state = self.execute_initial(stock_code, max_posts=max_posts, use_llm=use_llm, **kwargs)
            critique = self.evaluate_critique(state, **kwargs)
            final_state = self.reflect_and_refine(state, critique, **kwargs)

        self.add_message(Message.assistant(f"完成标的 [{stock_code}] 研判报告"))

        # 链路追踪汇总写入审计日志
        trace_summary = self.tracer.get_summary()
        failed_hint = f" | 失败环节: {', '.join(trace_summary['failed_spans'])}" if trace_summary["has_error"] else ""
        final_state.execution_logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] [链路追踪] 全流程共 {trace_summary['total_spans']} 个追踪跨度，"
            f"累计耗时 {trace_summary['total_latency_seconds']}s{failed_hint}"
        )
        if progress_callback:
            progress_callback(1.0, f"研判完成，已生成标的 [{stock_code}] 决策报告")
        return final_state
