import sys
import time
from rich.console import Console
from rich.table import Table
from evals.dataset import EVAL_DATASET
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.core.schema import RawPost

console = Console()

def run_evals():
    analyzer = FinancialSentimentAnalyzer()
    console.print(f'[bold cyan]>>> 启动 Agent 自动化量化评测流水线 (Evals Pipeline)[/bold cyan]')
    console.print(f'测试样本规模: [bold yellow]{len(EVAL_DATASET)}[/bold yellow] 条经典 A 股舆情语料')
    console.print(f'对照实验组 1: 规则基线引擎 (Rule Baseline)')
    console.print(f'对照实验组 2: 真实 LLM 语义引擎 ({analyzer.model_name})\n')

    rule_correct = 0
    rule_sarcasm_correct = 0
    llm_correct = 0
    llm_sarcasm_correct = 0

    table = Table(title='Agent 评测详细对齐结果 (Pass@1 对比)', show_header=True, header_style='bold magenta')
    table.add_column('ID', width=4)
    table.add_column('发帖语料片段', width=28)
    table.add_column('标准标注', width=12)
    table.add_column('基线判断', width=12)
    table.add_column('LLM 判断', width=12)
    table.add_column('LLM反讽对齐', width=12)

    total_sarcasm_samples = sum(1 for s in EVAL_DATASET if s.is_sarcasm)

    for sample in EVAL_DATASET:
        post = RawPost(title=sample.text)
        
        # 1. 跑规则基线
        res_rule = analyzer.analyze_mock(post)
        is_rule_stance_ok = (res_rule.stance.value == sample.expected_stance)
        is_rule_sarcasm_ok = (res_rule.is_sarcasm == sample.is_sarcasm)
        if is_rule_stance_ok:
            rule_correct += 1
        if sample.is_sarcasm and is_rule_sarcasm_ok:
            rule_sarcasm_correct += 1

        # 2. 跑真实 LLM
        res_llm = analyzer.analyze_with_llm(post)
        is_llm_stance_ok = (res_llm.stance.value == sample.expected_stance)
        is_llm_sarcasm_ok = (res_llm.is_sarcasm == sample.is_sarcasm)
        if is_llm_stance_ok:
            llm_correct += 1
        if sample.is_sarcasm and is_llm_sarcasm_ok:
            llm_sarcasm_correct += 1

        status_str = '[green]PASS[/green]' if is_llm_stance_ok else '[red]FAIL[/red]'
        sarcasm_str = '[green]PASS[/green]' if is_llm_sarcasm_ok else '[red]FAIL[/red]'
        
        table.add_row(
            str(sample.id),
            sample.text[:22] + '...',
            f'{sample.expected_stance} (反讽={sample.is_sarcasm})',
            f'{res_rule.stance.value}',
            f'{res_llm.stance.value} {status_str}',
            f'{res_llm.is_sarcasm} {sarcasm_str}'
        )

    console.print(table)

    total = len(EVAL_DATASET)
    rule_acc = (rule_correct / total) * 100
    llm_acc = (llm_correct / total) * 100
    rule_sarcasm_acc = (rule_sarcasm_correct / total_sarcasm_samples) * 100
    llm_sarcasm_acc = (llm_sarcasm_correct / total_sarcasm_samples) * 100

    summary_table = Table(title=' 最终量化指标汇总 (可直接写入简历)', show_header=True, header_style='bold green')
    summary_table.add_column('指标名称', width=26)
    summary_table.add_column('基线引擎 (Baseline)', width=20)
    summary_table.add_column('LLM + 自愈 Agent', width=20)
    summary_table.add_column('提升幅度 (Delta)', width=18)

    summary_table.add_row(
        '综合立场研判准确率 (Overall Acc)',
        f'{rule_acc:.1f}%',
        f'{llm_acc:.1f}%',
        f'[bold green]+{llm_acc - rule_acc:.1f}%[/bold green]'
    )
    summary_table.add_row(
        '复杂反讽/黑话识别率 (Sarcasm Acc)',
        f'{rule_sarcasm_acc:.1f}%',
        f'{llm_sarcasm_acc:.1f}%',
        f'[bold green]+{llm_sarcasm_acc - rule_sarcasm_acc:.1f}%[/bold green]'
    )

    console.print(summary_table)

if __name__ == '__main__':
    run_evals()
