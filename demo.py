"""
A 股多源舆情反讽研判与盘面背离预警 Agent - 交互演示 Demo
对标 GitHub 热门项目 FinRobot / TradingAgents 多智能体协同架构

运行方式:
    python demo.py                   # 运行默认经典标的 (长电科技 · 典型诱多背离案例)
    python demo.py --code 600667     # 运行指定标的 (如太极实业)
    python demo.py --mock            # 强制使用全本地离线数据与规则快速演示
"""

import argparse
import sys

# 适配 Windows 控制台编码
if sys.platform == "win32":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.core.config import global_config
from src.core.llm import HelloAgentsLLM
from src.agent.engine import SentimentArbitrageAgent
from src.agent.decision import has_valid_market_snapshot

console = Console()


def render_banner():
    banner_text = Text()
    banner_text.append("A-Share Sentiment Arbitrage Multi-Agent Workflow Demo\n", style="bold cyan")
    banner_text.append("面向 A 股市场的多源舆情反讽研判与盘面背离预警智能体\n", style="bold white")
    banner_text.append("核心特性: 并发感知流 | 反讽黑话穿透 | 催化归因 | 多空多智能体辩论 (Bull vs Bear) | 盘面终审裁决", style="dim")
    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


def run_demo(stock_code: str = "600584", max_posts: int = 20, force_mock: bool = False):
    render_banner()

    use_llm = not force_mock and bool(global_config.openai_api_key)
    mode_str = "大语言模型 (LLM)" if use_llm else "启发式规则引擎 (Mock 离线极速演示)"
    console.print(f"[bold yellow]> 当前运行模式:[/bold yellow] [bold green]{mode_str}[/bold green]")
    console.print(f"[bold yellow]> 分析标的代码:[/bold yellow] [bold magenta]{stock_code}[/bold magenta]")
    console.print()

    # 初始化智能体
    agent = SentimentArbitrageAgent(llm=HelloAgentsLLM() if use_llm else None)

    # 执行 5 阶段工作流流水线
    console.print("[bold cyan]>>> 正在驱动 FinancialWorkflowPipeline 执行 5 阶段协同流...[/bold cyan]")
    state = agent.run(
        stock_code=stock_code,
        max_posts=max_posts,
        use_llm=use_llm,
        workflow_mode=True,
    )

    console.print()
    console.print("=" * 80)
    console.print("[bold green][OK] 工作流执行完毕，已生成全景多智能体研判看板[/bold green]")
    console.print("=" * 80)
    console.print()

    # 1. 标的行情与情绪速览表格
    overview_table = Table(title="【标的盘面与散户情绪全景对照】", border_style="bright_blue")
    overview_table.add_column("标的名称/代码", style="bold white", justify="center")
    overview_table.add_column("最新现价", justify="right")
    overview_table.add_column("日内涨跌幅", justify="right")
    overview_table.add_column("成交金额", justify="right")
    overview_table.add_column("散户有效样本", justify="center")
    overview_table.add_column("综合情绪指数", justify="right")

    m_snap = state.market_data
    if m_snap and has_valid_market_snapshot(m_snap):
        chg_style = "bold red" if m_snap.change_percent >= 0 else "bold green"
        chg_sign = "+" if m_snap.change_percent >= 0 else ""
        chg_str = f"[{chg_style}]{chg_sign}{m_snap.change_percent:.2f}%[/{chg_style}]"
        price_str = f"{m_snap.current_price:.2f} 元"
        turnover_str = f"{m_snap.turnover_amount_yi:.2f} 亿元"
    else:
        price_str = "暂无行情"
        chg_str = "—"
        turnover_str = "—"

    sent_style = "bold red" if state.average_sentiment >= 0 else "bold green"
    sent_sign = "+" if state.average_sentiment >= 0 else ""
    sent_str = f"[{sent_style}]{sent_sign}{state.average_sentiment:.2f}[/{sent_style}]"

    overview_table.add_row(
        f"{state.stock_name or stock_code} ({stock_code})",
        price_str,
        chg_str,
        turnover_str,
        f"{len(state.sentiment_list)} 条",
        sent_str,
    )
    console.print(overview_table)
    console.print()

    # 2. 散户发帖反讽与黑话消歧抽样
    if state.sentiment_list:
        sample_table = Table(title="【散户发帖深度消歧与反讽识别样例】", border_style="magenta")
        sample_table.add_column("序号", justify="center", width=6)
        sample_table.add_column("原始语料内容 (截取)", width=35)
        sample_table.add_column("判定立场", justify="center", width=12)
        sample_table.add_column("情绪分值", justify="right", width=10)
        sample_table.add_column("反讽翻转", justify="center", width=10)
        sample_table.add_column("股市黑话", width=18)

        for i, s in enumerate(state.sentiment_list[:4]):
            raw_title = getattr(s, "raw_title", "") or f"股吧讨论语料 #{i+1}"
            raw_title_brief = (raw_title[:32] + "...") if len(raw_title) > 34 else raw_title
            stance_val = getattr(s.stance, "value", str(s.stance))
            st_style = "red" if ("多" in stance_val or "BULL" in stance_val) else "green" if ("空" in stance_val or "BEAR" in stance_val) else "white"
            sarcasm_str = "[bold yellow]是 (反讽)[/bold yellow]" if s.is_sarcasm else "[dim]否[/dim]"
            slang_str = ", ".join(s.slang_detected) if s.slang_detected else "无"

            sample_table.add_row(
                f"#{i+1:02d}",
                raw_title_brief,
                f"[{st_style}]{stance_val}[/{st_style}]",
                f"{s.sentiment_score:+.2f}",
                sarcasm_str,
                slang_str,
            )
        console.print(sample_table)
        console.print()

    # 3. 基本面催化与风险驱动
    if state.catalysts or state.risks:
        cat_table = Table(title="【基本面与权威公告因果传导提炼】", border_style="yellow")
        cat_table.add_column("类别", justify="center", width=10)
        cat_table.add_column("信息来源与标题", width=40)
        cat_table.add_column("影响等级", justify="center", width=10)
        cat_table.add_column("核心逻辑要点", width=35)

        for c in state.catalysts[:2]:
            cat_table.add_row("[bold red]利好催化[/bold red]", c.source_title[:38], c.impact_level, c.key_insight[:33])
        for r in state.risks[:2]:
            cat_table.add_row("[bold green]风险警示[/bold green]", r.source_title[:38], r.impact_level, r.key_insight[:33])
        console.print(cat_table)
        console.print()

    # 4. 多智能体多空对抗辩论 (BullAnalyst vs BearAnalyst)
    if state.debate_result:
        dr = state.debate_result
        console.print("[bold yellow][Phase 4] 多智能体多空对抗博弈辩论 (Bull vs Bear Debate Protocol)[/bold yellow]")

        bull_text = f"[bold red]{dr.bull_opinion.agent_name} (置信度: {dr.bull_opinion.confidence:.2f})[/bold red]\n"
        bull_text += f"[bold white]核心观点:[/bold white] {dr.bull_opinion.core_thesis}\n\n"
        bull_text += "[bold white]核心论据:[/bold white]\n"
        for arg in dr.bull_opinion.arguments:
            bull_text += f"  - {arg}\n"

        bear_text = f"[bold green]{dr.bear_opinion.agent_name} (置信度: {dr.bear_opinion.confidence:.2f})[/bold green]\n"
        bear_text += f"[bold white]核心观点:[/bold white] {dr.bear_opinion.core_thesis}\n\n"
        bear_text += "[bold white]核心论据:[/bold white]\n"
        for arg in dr.bear_opinion.arguments:
            bear_text += f"  - {arg}\n"

        debate_table = Table(border_style="cyan", show_header=False, expand=True)
        debate_table.add_column("多方研究员陈述", ratio=1)
        debate_table.add_column("空方研究员陈述", ratio=1)
        debate_table.add_row(
            Panel(bull_text.strip(), border_style="red", title="[red]多方阵营 (Bull Analyst)[/red]"),
            Panel(bear_text.strip(), border_style="green", title="[green]空方阵营 (Bear Analyst)[/green]"),
        )
        console.print(debate_table)

        divergence_panel = (
            f"[bold cyan]多空核心分歧焦点:[/bold cyan] {dr.key_divergence_point}\n"
            f"[bold cyan]风控委员会裁决态势:[/bold cyan] [bold yellow]{dr.consensus_bias}[/bold yellow]\n"
            f"[dim]{dr.arbitration_summary}[/dim]"
        )
        console.print(Panel(divergence_panel, border_style="yellow", title="[yellow]风控委员会质询与定性[/yellow]"))
        console.print()

    # 5. 终审背离裁决与风控建议
    if state.reflection:
        ref = state.reflection
        div_str = getattr(ref.divergence_type, "value", str(ref.divergence_type))
        risk_str = getattr(ref.risk_level, "value", str(ref.risk_level))
        decision_content = (
            f"[bold white]背离研判状态:[/bold white] [bold red]{div_str}[/bold red]  |  "
            f"[bold white]风险等级:[/bold white] [bold yellow]{risk_str}[/bold yellow]\n\n"
            f"[bold white]多维因果推导逻辑:[/bold white] {ref.reflection_narrative}\n\n"
            f"[bold green]交易策略与风控提示:[/bold green] {ref.action_suggestion}"
        )
        console.print(Panel(decision_content, border_style="red" if ref.is_divergent else "green", title="[bold][Phase 5] 终审决策与风控警报[/bold]"))
        console.print()

    # 6. 链路追踪跨度与耗时汇总
    summary = agent.tracer.get_summary()
    trace_table = Table(title="【全链路追踪跨度监控 (AgentTracer)】", border_style="dim")
    trace_table.add_column("追踪跨度名称 (Span Name)", style="cyan")
    trace_table.add_column("环节类型", justify="center")
    trace_table.add_column("耗时 (秒)", justify="right")
    trace_table.add_column("执行状态", justify="center")

    for span in agent.tracer.spans:
        st_color = "green" if span.status == "success" else "red"
        trace_table.add_row(span.name, span.span_type, f"{span.duration:.3f}s", f"[{st_color}]{span.status}[/{st_color}]")

    console.print(trace_table)
    console.print(f"[dim]全链路累计跨度: {summary['total_spans']} 个 | 整体耗时: {summary['total_latency_seconds']} 秒[/dim]")
    console.print()
    console.print("[bold cyan][提示] 您还可以运行 [bold yellow]streamlit run app.py[/bold yellow] 体验完整的 Web 交互工作台！[/bold cyan]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A-Share Multi-Agent Sentiment Arbitrage Workflow Demo")
    parser.add_argument("--code", type=str, default="600584", help="股票代码 (如 600584, 600667, 600519)")
    parser.add_argument("--posts", type=int, default=15, help="抓取/分析的散户发帖样本数")
    parser.add_argument("--mock", action="store_true", help="强制使用本地规则与离线数据")
    args = parser.parse_args()

    run_demo(stock_code=args.code, max_posts=args.posts, force_mock=args.mock)
