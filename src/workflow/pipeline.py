from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional
from rich.console import Console

from src.core.llm import HelloAgentsLLM
from src.core.tracer import AgentTracer
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.market import MarketDataTool
from src.tools.registry import ToolRegistry, global_tool_registry
from src.tools.scraper import StockForumScraper
from src.workflow.nodes import (
    ArbitrageArbitrationNode,
    DisambiguationNode,
    FundamentalCatalystNode,
    IngestionNode,
    MultiAgentDebateNode,
)

if TYPE_CHECKING:
    from src.agent.state import AgentState

console = Console()


class FinancialWorkflowPipeline:
    """
    面向 A 股市场的多智能体多源协同研判工作流 (Financial Multi-Agent Workflow Pipeline)
    深度对标 GitHub 热门项目 FinRobot (AI4Finance) 与 TradingAgents (Debate Protocol)：

    工作流阶段：
    Phase 1: 并发感知流 (Parallel Ingestion) —— 股吧/资讯/公告/秒级盘面 4 路并发 I/O 抓取；
    Phase 2: 批量情绪消歧 (Batch Disambiguation) —— 多线程并发反讽穿透与立场聚合；
    Phase 3: 基本面催化挖掘 (Catalyst Extraction) —— 深度解析新闻与公告正文，提取利好驱动与负向风险；
    Phase 4: 多智能体多空辩论 (Multi-Agent Debate) —— 多头研究员 vs 空头研究员 构建对抗辩论；
    Phase 5: 盘面背离终审仲裁 (Divergence & Risk Arbitration) —— 交叉对照 L1 盘面事实与博弈共识，输出结构化风控决议。
    """
    def __init__(
        self,
        llm: Optional[HelloAgentsLLM] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        self.llm = llm or HelloAgentsLLM()
        self.tools = tools or global_tool_registry
        self.scraper: StockForumScraper = self.tools.get("stock_scraper") or StockForumScraper()
        self.market_tool: MarketDataTool = self.tools.get("market_data") or MarketDataTool()

        configured_analyzer = self.tools.get("sentiment_analyzer") if tools is not None else None
        self.analyzer: FinancialSentimentAnalyzer = configured_analyzer or FinancialSentimentAnalyzer(llm=self.llm)

        # 挂载工作流核心节点
        self.ingestion_node = IngestionNode(scraper=self.scraper, market_tool=self.market_tool)
        self.disambiguation_node = DisambiguationNode(analyzer=self.analyzer)
        self.catalyst_node = FundamentalCatalystNode(llm=self.llm)
        self.debate_node = MultiAgentDebateNode(llm=self.llm)
        self.arbitration_node = ArbitrageArbitrationNode()

    def run(
        self,
        stock_code: str,
        max_posts: int = 30,
        use_llm: bool = True,
        engine_mode: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        tracer: Optional[AgentTracer] = None,
    ) -> "AgentState":
        """
        执行完整多智能体研判工作流（含阶段级异常边界）
        任意阶段失败时将失败终态写入执行日志并通知进度回调，再向上抛出原始异常
        """
        from src.agent.state import AgentState

        state = AgentState(stock_code=stock_code)
        state.iteration_count = 1
        try:
            self._execute_phases(
                state,
                stock_code,
                max_posts=max_posts,
                use_llm=use_llm,
                engine_mode=engine_mode,
                progress_callback=progress_callback,
                tracer=tracer,
            )
        except Exception as e:
            now_str = datetime.now().strftime("%H:%M:%S")
            state.execution_logs.append(f"[{now_str}] [工作流异常终止] {type(e).__name__}: {e}")
            if progress_callback:
                progress_callback(1.0, f"工作流执行失败: {type(e).__name__}: {e}")
            raise
        return state

    def _execute_phases(
        self,
        state: "AgentState",
        stock_code: str,
        max_posts: int = 30,
        use_llm: bool = True,
        engine_mode: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        tracer: Optional[AgentTracer] = None,
    ) -> None:
        """按序执行 Phase 1-5 各阶段节点"""
        from src.agent.decision import has_valid_market_snapshot

        active_tracer = tracer or AgentTracer()
        console.print(f"[bold cyan]>>> 启动现代化多智能体工作流 (Workflow Pipeline): 标的 [{stock_code}][/bold cyan]")

        # ==========================================
        # Phase 1: 并发金融感知流
        # ==========================================
        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(f"[{now_str}] [工作流 Phase 1] 启动 4 路并发 I/O 感知采集 (股吧+资讯+公告+L1盘面)...")
        with active_tracer.span("workflow_phase1_ingestion", "tool", inputs={"stock_code": stock_code}) as span:
            posts, news, announcements, market_snap = self.ingestion_node.run(
                stock_code=stock_code,
                max_posts=max_posts,
                progress_callback=progress_callback,
            )
            span.outputs = {
                "posts": len(posts),
                "news": len(news),
                "announcements": len(announcements),
                "has_market": has_valid_market_snapshot(market_snap),
            }

        state.news_list = news
        state.announcements = announcements
        state.market_data = market_snap
        if market_snap and market_snap.stock_name and market_snap.stock_name != "未识别标的":
            state.stock_name = market_snap.stock_name
        elif not state.stock_name or state.stock_name == "未识别标的":
            from src.tools.stock_resolver import StockResolver
            resolved_name = StockResolver.search_name_by_code(stock_code)
            state.stock_name = resolved_name or (market_snap.stock_name if market_snap else None) or f"标的 {stock_code}"
        state.sentiment_sample_count = len(posts)

        now_str = datetime.now().strftime("%H:%M:%S")
        if has_valid_market_snapshot(market_snap):
            state.execution_logs.append(
                f"[{now_str}] [感知完成] 成功并发拉取散户语料 {len(posts)} 条，主流资讯 {len(news)} 篇，"
                f"官方披露 {len(announcements)} 份，最新盘面现价 {market_snap.current_price:.2f} 元 (涨跌 {market_snap.change_percent:+.2f}%)"
            )
        else:
            state.execution_logs.append(
                f"[{now_str}] [感知完成] 成功并发拉取散户语料 {len(posts)} 条，主流资讯 {len(news)} 篇，"
                f"官方披露 {len(announcements)} 份，盘面行情获取失败，已降级为无效快照"
            )

        # ==========================================
        # Phase 2: 批量情绪与反讽并发消歧
        # ==========================================
        state.execution_logs.append(f"[{now_str}] [工作流 Phase 2] 执行批量散户语料多模式消歧与反讽穿透...")
        with active_tracer.span("workflow_phase2_disambiguation", "llm", inputs={"samples": len(posts)}) as span:
            sentiment_results = self.disambiguation_node.run(
                posts=posts,
                use_llm=use_llm,
                engine_mode=engine_mode,
                progress_callback=progress_callback,
            )
            span.outputs = {"analyzed_count": len(sentiment_results)}

        state.sentiment_list = sentiment_results
        total_score = sum(r.sentiment_score for r in sentiment_results)
        if sentiment_results:
            state.average_sentiment = round(total_score / len(sentiment_results), 2)

        # 记录消歧细节到流水日志
        for idx, res in enumerate(sentiment_results):
            raw_stance = getattr(res.stance, "value", str(res.stance))
            slang_str = f"#{', #'.join(res.slang_detected)}" if res.slang_detected else "无特殊黑话"
            sarcasm_str = "【反讽翻转】" if res.is_sarcasm else "无反讽"
            post_title = getattr(posts[idx], "title", f"语料#{idx+1}") if idx < len(posts) else f"语料#{idx+1}"
            post_brief = (post_title[:40] + "...") if len(post_title) > 42 else post_title
            state.execution_logs.append(
                f"[{now_str}] [消歧 #{idx+1:02d}] “{post_brief}” | 立场: {raw_stance} | "
                f"得分: {res.sentiment_score:+.2f} | 黑话: {slang_str} | 反讽: {sarcasm_str}"
            )

        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(
            f"[{now_str}] [情绪聚合] 全样本情绪定格为 {state.average_sentiment:+.2f} (区间: -1.0 到 +1.0)"
        )

        # ==========================================
        # Phase 3: 基本面与深度催化挖掘
        # ==========================================
        if progress_callback:
            progress_callback(0.65, "工作流 Phase 3: 深度解析新闻与公告正文，提炼驱动催化剂与风险项...")

        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(f"[{now_str}] [工作流 Phase 3] 深度提炼新闻与公告传导逻辑 (催化剂/风险项)...")
        with active_tracer.span("workflow_phase3_catalyst", "analysis", inputs={"news": len(news), "ann": len(announcements)}) as span:
            catalysts, risks = self.catalyst_node.run(
                news_list=news,
                announcements=announcements,
                stock_name=state.stock_name,
            )
            span.outputs = {"catalysts": len(catalysts), "risks": len(risks)}

        state.catalysts = catalysts
        state.risks = risks
        state.execution_logs.append(
            f"[{now_str}] [催化挖掘] 成功提炼正向催化驱动 {len(catalysts)} 项，负向风险警示 {len(risks)} 项"
        )

        # ==========================================
        # Phase 4: 多智能体多空辩论对抗
        # ==========================================
        if progress_callback:
            progress_callback(0.80, "工作流 Phase 4: 触发多智能体博弈辩论 (BullAnalyst vs BearAnalyst)...")

        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(f"[{now_str}] [工作流 Phase 4] 开启多智能体博弈辩论 (多头研究员 vs 空头研究员)...")
        with active_tracer.span("workflow_phase4_debate", "debate", inputs={"sentiment": state.average_sentiment}) as span:
            debate_res = self.debate_node.run(
                state=state,
                catalysts=catalysts,
                risks=risks,
            )
            span.outputs = {"consensus_bias": debate_res.consensus_bias}

        state.debate_result = debate_res
        state.execution_logs.append(
            f"[{now_str}] [辩论决议] 多方置信度 {debate_res.bull_opinion.confidence:.2f} | "
            f"空方置信度 {debate_res.bear_opinion.confidence:.2f} | 博弈态势: {debate_res.consensus_bias}"
        )
        state.execution_logs.append(f"[{now_str}] [辩论分歧焦点] {debate_res.key_divergence_point}")

        # ==========================================
        # Phase 5: 终审风控与背离仲裁
        # ==========================================
        if progress_callback:
            progress_callback(0.92, "工作流 Phase 5: 汇总盘面量价与多空博弈，生成终审风控决策...")

        now_str = datetime.now().strftime("%H:%M:%S")
        state.execution_logs.append(f"[{now_str}] [工作流 Phase 5] 终审委员会结合客观盘面基准执行裁决...")
        with active_tracer.span("workflow_phase5_arbitration", "reflect", inputs={"divergence_check": True}) as span:
            decision = self.arbitration_node.run(state=state, debate_result=debate_res)
            span.outputs = {"divergence_type": str(decision.divergence_type)}

        state.reflection = decision
        now_str = datetime.now().strftime("%H:%M:%S")
        div_val = getattr(decision.divergence_type, "value", str(decision.divergence_type))
        risk_val = getattr(decision.risk_level, "value", str(decision.risk_level))
        state.execution_logs.append(
            f"[{now_str}] [终审决策定案] 背离形态: {div_val} (风控等级: {risk_val}) | "
            f"决策建议: {decision.action_suggestion}"
        )

        if progress_callback:
            progress_callback(1.0, f"工作流执行完毕，已输出标的 [{stock_code}] 全景研判报告。")
