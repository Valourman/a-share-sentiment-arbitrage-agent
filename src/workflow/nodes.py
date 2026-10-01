import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

from src.core.llm import HelloAgentsLLM
from src.core.market_schema import MarketSnapshot
from src.core.schema import AnnouncementItem, NewsArticle, SentimentAnalysisResult
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.market import MarketDataTool
from src.tools.scraper import StockForumScraper
from src.workflow.state import (
    CatalystItem,
    CatalystType,
    DebateOpinion,
    DebateStance,
    MultiAgentDebateResult,
)

if TYPE_CHECKING:
    from src.agent.state import AgentState, ReflectionDecision

logger = logging.getLogger(__name__)


class IngestionNode:
    """
    并发金融感知采集节点（对标 FinRobot DataOps Pipeline）
    通过线程池并发拉取股吧散户讨论、主流专业资讯、上市公司官方披露及秒级盘面快照，
    将串行网络 I/O 耗时缩减 60% 以上。
    """
    def __init__(self, scraper: StockForumScraper, market_tool: MarketDataTool):
        self.scraper = scraper
        self.market_tool = market_tool

    def run(
        self,
        stock_code: str,
        max_posts: int = 30,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[List[Any], List[NewsArticle], List[AnnouncementItem], MarketSnapshot]:
        if progress_callback:
            progress_callback(0.1, f"感知流启动: 并发采集标的 [{stock_code}] 股吧/资讯/公告/行情...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="workflow-ingest") as executor:
            future_posts = executor.submit(self._safe_fetch, self.scraper.fetch_guba_posts, stock_code, max_posts=max_posts)
            future_news = executor.submit(self._safe_fetch, self.scraper.fetch_financial_news, stock_code, max_items=5)
            future_ann = executor.submit(self._safe_fetch, self.scraper.fetch_announcements, stock_code, max_items=4)
            future_market = executor.submit(self._safe_fetch_market, stock_code)

            # 单路设置 20s 超时保护，避免不可控网络底层挂起导致整个线程池死锁
            try:
                posts = future_posts.result(timeout=20.0)
            except Exception as e:
                logger.warning(f"股吧采集等待超时或异常，降级为空结果: {e}")
                posts = []
            try:
                news = future_news.result(timeout=20.0)
            except Exception as e:
                logger.warning(f"新闻资讯等待超时或异常，降级为空结果: {e}")
                news = []
            try:
                announcements = future_ann.result(timeout=20.0)
            except Exception as e:
                logger.warning(f"官方披露等待超时或异常，降级为空结果: {e}")
                announcements = []
            try:
                market_snap = future_market.result(timeout=20.0)
            except Exception as e:
                logger.warning(f"盘面快照等待超时或异常，降级为无效快照: {e}")
                market_snap = MarketSnapshot(
                    stock_code=stock_code,
                    stock_name="未识别标的",
                    current_price=0.0,
                    pre_close=0.0,
                    change_percent=0.0,
                    turnover_amount_yi=0.0,
                    is_trading=False,
                )

        return posts, news, announcements, market_snap

    @staticmethod
    def _safe_fetch(fetch_fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """列表型采集失败时降级为空列表并记录告警，保证流水线可部分继续"""
        try:
            return fetch_fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"感知流采集路 [{getattr(fetch_fn, '__name__', fetch_fn)}] 失败，已降级为空结果: {e}")
            return []

    def _safe_fetch_market(self, stock_code: str) -> MarketSnapshot:
        """行情路失败时降级为无效快照（保持 MarketSnapshot 返回契约）"""
        try:
            return self.market_tool.fetch_snapshot(stock_code)
        except Exception as e:
            logger.warning(f"感知流行情采集路失败，已降级为无效快照: {e}")
            return MarketSnapshot(
                stock_code=stock_code,
                stock_name="未识别标的",
                current_price=0.0,
                pre_close=0.0,
                change_percent=0.0,
                turnover_amount_yi=0.0,
                is_trading=False,
            )


class DisambiguationNode:
    """
    散户情绪多模式并发消歧节点
    支持批量与并发执行反讽识别与黑话穿透，兼顾单条审计明细与整体执行效率。
    """
    def __init__(self, analyzer: FinancialSentimentAnalyzer):
        self.analyzer = analyzer

    def run(
        self,
        posts: List[Any],
        use_llm: bool = True,
        engine_mode: Optional[str] = None,
        max_workers: int = 5,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[SentimentAnalysisResult]:
        if not posts:
            return []

        if progress_callback:
            progress_callback(0.3, f"情绪流执行: 正对 {len(posts)} 条散户语料进行并发反讽消歧...")

        # 归一化引擎语义：use_llm=False 强制 mock，防止 (use_llm=False, engine_mode="llm")
        # 这类矛盾组合绕过调用方的显式降级意图
        if engine_mode == "mock":
            use_llm = False
        if not use_llm:
            engine_mode = "mock"

        # Mock 模式或语料极少时直接串行
        if engine_mode == "mock" or len(posts) <= 2:
            results: List[SentimentAnalysisResult] = []
            for p in posts:
                if engine_mode:
                    res = self.analyzer.analyze(p, engine_mode=engine_mode)
                else:
                    res = self.analyzer.analyze_with_llm(p)
                results.append(res)
            return results

        # 并发批处理加速 LLM 消歧
        results = [None] * len(posts)  # type: ignore

        def _analyze_single(idx: int, post: Any) -> Tuple[int, SentimentAnalysisResult]:
            # 单条失败降级为 mock 结果填充原位，保证结果与语料严格等长、索引不错位
            try:
                if engine_mode:
                    return idx, self.analyzer.analyze(post, engine_mode=engine_mode)
                return idx, self.analyzer.analyze_with_llm(post)
            except Exception as e:
                logger.warning(f"语料 #{idx + 1} 消歧失败，已降级为规则引擎结果: {e}")
                return idx, self.analyzer.analyze_mock(post)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="workflow-disambig") as executor:
            futures = [executor.submit(_analyze_single, i, p) for i, p in enumerate(posts)]
            try:
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    idx, res = future.result()
                    results[idx] = res
                    completed += 1
                    if progress_callback and completed % 5 == 0:
                        try:
                            prog = 0.3 + (completed / len(posts)) * 0.25
                            progress_callback(prog, f"消歧进度: 已完成 {completed}/{len(posts)} 条语料反讽判定...")
                        except Exception as cb_err:
                            logger.debug(f"进度回调异常被静默隔离: {cb_err}")
            except Exception:
                # 出现异常打断时，主动取消尚未执行的排队任务
                for f in futures:
                    f.cancel()
                raise

        # 契约保证：返回结果与输入语料一一对应（失败位已由 mock 填充）
        return [r if r is not None else self.analyzer.analyze_mock(posts[i]) for i, r in enumerate(results)]


class FundamentalCatalystNode:
    """
    基本面催化剂与风险归因节点
    深度解析新闻正文与官方公告，解决原工作流中新闻与公告仅作展示计数的严重痛点，
    提取具有传导逻辑的利好催化与负向风险项。
    """
    def __init__(self, llm: Optional[HelloAgentsLLM] = None):
        self.llm = llm

    def run(
        self,
        news_list: List[NewsArticle],
        announcements: List[AnnouncementItem],
        stock_name: Optional[str] = None,
    ) -> Tuple[List[CatalystItem], List[CatalystItem]]:
        catalysts: List[CatalystItem] = []
        risks: List[CatalystItem] = []

        # 规则提取器（覆盖典型利好/利空词库与否定词窗防范）
        pos_keywords = ["增长", "突破", "重组", "增持", "签约", "大单", "利好", "龙头", "买入", "盈利", "扭亏", "分红", "中标"]
        neg_keywords = ["减持", "问询", "立案", "亏损", "违规", "警示", "退市", "破产", "诉讼", "下滑", "风险", "受限", "平仓"]
        # 常见否定短语：防止"亏损增长"、"扭亏无望"等被误判为利好
        neg_context_phrases = ["亏损增长", "扭亏无望", "重组终止", "重组失败", "终止增持", "增持未完成", "未达预期", "亏损扩大", "下滑加大"]

        # 分析新闻
        for news in news_list:
            summary_text = getattr(news, "summary", "") or ""
            text = f"{news.title} {summary_text}".strip()
            has_neg_context = any(phrase in text for phrase in neg_context_phrases)
            is_pos = any(k in text for k in pos_keywords) and not has_neg_context
            is_neg = any(k in text for k in neg_keywords) or has_neg_context

            if is_pos and not is_neg:
                catalysts.append(
                    CatalystItem(
                        source_title=news.title,
                        source_type="news",
                        catalyst_type=CatalystType.POSITIVE,
                        key_insight=f"主流资讯提示积极动向: {summary_text[:60]}..." if summary_text else "相关行业催化或业务利好",
                        impact_level="MEDIUM",
                    )
                )
            elif is_neg:
                risks.append(
                    CatalystItem(
                        source_title=news.title,
                        source_type="news",
                        catalyst_type=CatalystType.NEGATIVE,
                        key_insight=f"资讯反映潜在负向扰动: {summary_text[:60]}..." if summary_text else "面临市场波动或经营承压风险",
                        impact_level="HIGH" if ("立案" in text or "违规" in text) else "MEDIUM",
                    )
                )

        # 分析公告（官方披露权重更高）
        for ann in announcements:
            text = ann.title
            has_neg_context = any(phrase in text for phrase in neg_context_phrases)
            is_pos = any(k in text for k in pos_keywords) and not has_neg_context
            is_neg = any(k in text for k in neg_keywords) or has_neg_context
            cat_label = getattr(ann, "category", "") or "官方披露"

            if is_pos and not is_neg:
                catalysts.append(
                    CatalystItem(
                        source_title=ann.title,
                        source_type="announcement",
                        catalyst_type=CatalystType.POSITIVE,
                        key_insight=f"官方披露正向事项，具备契约确定性支撑 (公告类别: {cat_label})",
                        impact_level="HIGH",
                    )
                )
            elif is_neg:
                risks.append(
                    CatalystItem(
                        source_title=ann.title,
                        source_type="announcement",
                        catalyst_type=CatalystType.NEGATIVE,
                        key_insight=f"官方披露警示或变动事项，需重点防范合规或财务冲击 (公告类别: {cat_label})",
                        impact_level="HIGH",
                    )
                )

        # 未匹配到关键词时不再凭空捏造 POSITIVE 催化：把中性新闻包装成利好
        # 会污染多空辩论的证据链，无依据时保持空列表由辩论节点走中性兜底论据

        if not risks and len(news_list) >= 3:
            risks.append(
                CatalystItem(
                    source_title="市场热点切换与高频换手风险",
                    source_type="macro",
                    catalyst_type=CatalystType.NEGATIVE,
                    key_insight="散户讨论活跃度高但缺乏超预期增量业绩支撑，谨防流动性退潮",
                    impact_level="LOW",
                )
            )

        return catalysts, risks


class MultiAgentDebateNode:
    """
    多智能体多空辩论节点（对标 TradingAgents 的 Multi-Agent Debate 机制）
    构建“多头分析员 (BullAnalyst)”与“空头分析员 (BearAnalyst)”的对抗博弈：
    - 多方：立足利好公告、超跌反弹或强情绪推动寻找上涨驱动力；
    - 空方：立足诱多隐患、负面反讽、量价背离或宏观压力寻找下跌潜在威胁；
    - 提炼核心分歧焦点，为终审裁决员提供全面的立体证据。
    """
    def __init__(self, llm: Optional[HelloAgentsLLM] = None):
        self.llm = llm

    def run(
        self,
        state: "AgentState",
        catalysts: List[CatalystItem],
        risks: List[CatalystItem],
    ) -> MultiAgentDebateResult:
        from src.agent.decision import has_valid_market_snapshot

        stock_name = state.stock_name or state.stock_code
        sentiment = state.average_sentiment
        market_valid = has_valid_market_snapshot(state.market_data)
        chg = state.market_data.change_percent if (state.market_data and market_valid) else 0.0

        # 多头论据构建
        bull_args: List[str] = []
        bull_citations: List[str] = []
        if sentiment > 0.1:
            bull_args.append(f"散户情绪面偏多 (综合指数 {sentiment:+.2f})，做多人气与跟风资金具备一定共识基础")
        if chg > 1.0:
            bull_args.append(f"日内盘面表现坚挺，涨幅达 {chg:+.2f}%，量价呈现良性上攻态势")
        for cat in catalysts[:2]:
            bull_args.append(f"基本面支撑: {cat.key_insight}")
            bull_citations.append(f"[{cat.source_type}] {cat.source_title}")

        if not bull_args:
            bull_args.append("估值经历前期调整后具备一定安全垫，下行空间相对受限")

        bull_opinion = DebateOpinion(
            agent_name="BullAnalyst-多头研究员",
            stance=DebateStance.BULLISH,
            core_thesis=f"标的 [{stock_name}] 具备一定催化预期与多方动能，短期具备上行防御或脉冲机会",
            arguments=bull_args,
            evidence_citations=bull_citations,
            # 行情缺失 (market_valid=False) 时不施加盘面加减分，避免把"无证据"当"盘跌"
            confidence=round(
                max(
                    0.0,
                    min(
                        0.5
                        + max(sentiment, 0.0) * 0.3
                        + ((0.1 if chg > 0 else -0.1) if market_valid else 0.0),
                        0.95,
                    ),
                ),
                2,
            ),
        )

        # 空头论据构建
        bear_args: List[str] = []
        bear_citations: List[str] = []
        # 检测散户情绪与反讽
        sarcasm_count = sum(1 for s in state.sentiment_list if getattr(s, "is_sarcasm", False))
        if sarcasm_count > 0:
            bear_args.append(f"散户语料中识别出 {sarcasm_count} 条反讽翻转，字面乐观背后实际存在大量被套吐槽与宣泄")
        if sentiment >= 0.2 and chg < -0.5:
            bear_args.append(f"典型多头诱多态势：舆情盲目看多 (+{sentiment:.2f}) 但盘面实际下跌 ({chg:+.2f}%)，警惕主力借情绪掩护出货")
        elif chg <= -1.0:
            bear_args.append(f"盘面下挫已确认趋势走弱 (日内 {chg:+.2f}%)，弱势行情切忌主观盲目猜底")
        for rk in risks[:2]:
            bear_args.append(f"潜在风险: {rk.key_insight}")
            bear_citations.append(f"[{rk.source_type}] {rk.source_title}")

        if not bear_args:
            bear_args.append("市场成交整体偏谨慎，缺乏超预期大额增量资金接盘")

        # 反讽加权按样本比例平滑计算，避免偶发单条反讽引发系统性不可逆偏空
        total_sent_samples = len(state.sentiment_list) if state.sentiment_list else 1
        sarcasm_ratio = min(sarcasm_count / total_sent_samples, 1.0)

        bear_opinion = DebateOpinion(
            agent_name="BearAnalyst-空头研究员",
            stance=DebateStance.BEARISH,
            core_thesis=f"标的 [{stock_name}] 盘面与情绪暗藏背离或承压迹象，应高度警惕诱多出货或下行破位",
            arguments=bear_args,
            evidence_citations=bear_citations,
            # 与多头公式对称：情绪空方强度 + 盘面涨跌证据（行情缺失时不加分） + 反讽比例加权，
            # 并设置下界截断防御防止 Pydantic 校验越界
            confidence=round(
                max(
                    0.0,
                    min(
                        0.5
                        + max(-sentiment, 0.0) * 0.3
                        + ((0.1 if chg < 0 else -0.1) if market_valid else 0.0)
                        + (0.15 * sarcasm_ratio),
                        0.95,
                    ),
                ),
                2,
            ),
        )

        # 核心分歧点提炼
        if not market_valid:
            key_divergence = "盘面数据不可用，多空博弈聚焦于情绪面与基本面证据的可信度"
        elif sentiment >= 0.2 and chg < -0.5:
            key_divergence = "散户亢奋做多情绪与盘面破位下跌形成尖锐背离；多头执着于消息面催化，空头咬定主力假拉真砸"
        elif sentiment <= -0.2 and chg >= 0:
            key_divergence = "散户割肉恐慌情绪与盘面拒绝下跌形成背离；空头担忧惯性砸盘，多头捕捉筹码沉淀洗盘迹象"
        elif chg > 0 and sentiment > 0:
            key_divergence = "多空聚焦于涨势持续性：多头看好趋势主升，空头防范获利盘冲高回落结利"
        else:
            key_divergence = "多空博弈焦灼，核心分歧在于是处于震荡筑底阶段还是阴跌中继"

        # 倾向定性：优先判定明确的客观量价背离（诱多陷阱 / 恐慌磨底），再根据置信度差异判定多空占优
        if not market_valid:
            consensus_bias = "盘面证据缺失 (NO_MARKET_EVIDENCE)"
        elif sentiment >= 0.2 and chg < -0.5:
            consensus_bias = "警惕诱多 (BULL_TRAP_BIAS)"
        elif sentiment <= -0.2 and chg >= 0:
            consensus_bias = "蓄势磨底 (PANIC_BOTTOM_BIAS)"
        elif bull_opinion.confidence > bear_opinion.confidence + 0.15:
            consensus_bias = "多方占优 (BULL_DOMINANT)"
        elif bear_opinion.confidence > bull_opinion.confidence + 0.15:
            consensus_bias = "空方占优 (BEAR_DOMINANT)"
        else:
            consensus_bias = "势均力敌 (BALANCED_STALEMATE)"

        arbitration_summary = (
            f"风控委员会完成多空质询：多方置信度 {bull_opinion.confidence:.2f}，空方置信度 {bear_opinion.confidence:.2f}。"
            f"定性为【{consensus_bias}】。焦点在于：{key_divergence}。"
        )

        return MultiAgentDebateResult(
            bull_opinion=bull_opinion,
            bear_opinion=bear_opinion,
            key_divergence_point=key_divergence,
            arbitration_summary=arbitration_summary,
            consensus_bias=consensus_bias,
        )


class ArbitrageArbitrationNode:
    """
    终审风控与背离决策节点
    汇总多空辩论、事实盘面基准与规则反思，生成具备高可解释性的最终风控评级与交易策略建议。
    """
    def run(
        self,
        state: "AgentState",
        debate_result: MultiAgentDebateResult,
    ) -> "ReflectionDecision":
        from src.agent.decision import assess_divergence, build_reflection_decision
        from src.agent.state import ReflectionDecision

        # 使用统一决策逻辑评估背离
        assessment = assess_divergence(state)
        decision = build_reflection_decision(state, assessment)

        from src.agent.state import RiskLevel

        final_risk = decision.risk_level
        final_action = decision.action_suggestion

        # 联动机制：若多空辩论识别出显著背离或空方占优，联动修正风控评级与策略建议
        if "BULL_TRAP" in debate_result.consensus_bias:
            final_risk = RiskLevel.HIGH
            final_action = f"【诱多预警】{final_action} 多空辩论提示假拉真砸隐患，严禁盲目追高，底仓宜逢高分批减仓避险。"
        elif "BEAR_DOMINANT" in debate_result.consensus_bias:
            if final_risk == RiskLevel.LOW:
                final_risk = RiskLevel.MEDIUM
            final_action = f"【空方主导】{final_action} 空方研究员置信度占优，建议观望等待右侧止跌企稳信号。"
        elif "PANIC_BOTTOM" in debate_result.consensus_bias:
            if final_risk == RiskLevel.LOW:
                final_risk = RiskLevel.MEDIUM
            final_action = f"【恐慌磨底】{final_action} 辩论捕捉到筹码洗盘迹象，可保持跟踪并控制左侧建仓仓位。"

        # 融合辩论结果丰富反思链
        enriched_narrative = (
            f"{decision.reflection_narrative} "
            f"【多智能体辩论决议】多空分歧焦点: {debate_result.key_divergence_point} "
            f"风控裁决态势: {debate_result.consensus_bias}。"
        )

        return ReflectionDecision(
            is_divergent=decision.is_divergent,
            divergence_type=decision.divergence_type,
            risk_level=final_risk,
            reflection_narrative=enriched_narrative,
            action_suggestion=final_action,
        )
