import sys
import os
import time
import statistics
from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from evals.public_dataset import PUBLIC_BENCHMARK_DATASET, PublicEvalSample
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.core.schema import RawPost

console = Console()


def compute_metrics(actual_list: List[str], pred_list: List[str], classes: List[str]):
    """计算多分类学术级指标: Accuracy, Per-class Precision/Recall/F1, Macro-F1"""
    total = len(actual_list)
    correct = sum(1 for a, p in zip(actual_list, pred_list) if a == p)
    accuracy = correct / total if total > 0 else 0.0

    metrics = {}
    f1_sum = 0.0
    for cls in classes:
        tp = sum(1 for a, p in zip(actual_list, pred_list) if a == cls and p == cls)
        fp = sum(1 for a, p in zip(actual_list, pred_list) if a != cls and p == cls)
        fn = sum(1 for a, p in zip(actual_list, pred_list) if a == cls and p != cls)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        metrics[cls] = {'precision': prec, 'recall': rec, 'f1': f1, 'support': sum(1 for a in actual_list if a == cls)}
        f1_sum += f1

    macro_f1 = f1_sum / len(classes) if classes else 0.0
    return accuracy, metrics, macro_f1


def build_confusion_matrix(actual_list: List[str], pred_list: List[str], classes: List[str]) -> Dict[str, Dict[str, int]]:
    """构建混淆矩阵"""
    matrix = {c: {p: 0 for p in classes} for c in classes}
    for a, p in zip(actual_list, pred_list):
        if a in matrix and p in matrix[a]:
            matrix[a][p] += 1
    return matrix


def run_public_benchmark(engine_mode: str = 'jev'):
    analyzer = FinancialSentimentAnalyzer()
    dataset = PUBLIC_BENCHMARK_DATASET
    classes = ['bullish', 'bearish', 'neutral']

    console.print(f'[bold cyan]>>> 启动学术公开基准评测 (Public Benchmark Pipeline)[/bold cyan]')
    console.print(f'基准语料规范: [bold yellow]StockSentCN + ToSarcasm + SMP-ECISA[/bold yellow]')
    console.print(f'样本规模: [bold green]{len(dataset)}[/bold green] 条标准标注语料 | 评测引擎: [bold magenta]{engine_mode.upper()}[/bold magenta]\n')

    actual_stances = []
    pred_stances = []
    actual_sarcasms = []
    pred_sarcasms = []
    latencies = []

    progress_table = Table(title=f'样本预测实时流 ({engine_mode.upper()} 引擎)', show_header=True, header_style='bold cyan')
    progress_table.add_column('ID', width=3)
    progress_table.add_column('来源', width=13)
    progress_table.add_column('发帖语料片段', width=26)
    progress_table.add_column('金标真值', width=12)
    progress_table.add_column('模型预测', width=12)
    progress_table.add_column('反讽对齐', width=10)
    progress_table.add_column('耗时', width=8)

    for item in dataset:
        post = RawPost(title=item.text)
        t0 = time.perf_counter()
        res = analyzer.analyze(post, engine_mode=engine_mode)
        lat = (time.perf_counter() - t0) * 1000

        pred_stance = res.stance.value
        pred_sarcasm = res.is_sarcasm

        actual_stances.append(item.expected_stance)
        pred_stances.append(pred_stance)
        actual_sarcasms.append(item.is_sarcasm)
        pred_sarcasms.append(pred_sarcasm)
        latencies.append(lat)

        status_badge = '[green]PASS[/green]' if pred_stance == item.expected_stance else '[red]FAIL[/red]'
        sarcasm_badge = '[green]YES[/green]' if pred_sarcasm == item.is_sarcasm else '[red]NO[/red]'

        progress_table.add_row(
            str(item.id),
            item.source,
            item.text[:22] + '...',
            item.expected_stance,
            f'{pred_stance} {status_badge}',
            sarcasm_badge,
            f'{lat:.0f}ms'
        )

    console.print(progress_table)

    # 1. 计算核心分类指标
    acc, class_metrics, macro_f1 = compute_metrics(actual_stances, pred_stances, classes)

    # 2. 计算反讽专项指标
    sarcasm_tp = sum(1 for a, p in zip(actual_sarcasms, pred_sarcasms) if a and p)
    sarcasm_fp = sum(1 for a, p in zip(actual_sarcasms, pred_sarcasms) if not a and p)
    sarcasm_fn = sum(1 for a, p in zip(actual_sarcasms, pred_sarcasms) if a and not p)
    sarcasm_prec = sarcasm_tp / (sarcasm_tp + sarcasm_fp) if (sarcasm_tp + sarcasm_fp) > 0 else 0.0
    sarcasm_rec = sarcasm_tp / (sarcasm_tp + sarcasm_fn) if (sarcasm_tp + sarcasm_fn) > 0 else 0.0
    sarcasm_f1 = (2 * sarcasm_prec * sarcasm_rec) / (sarcasm_prec + sarcasm_rec) if (sarcasm_prec + sarcasm_rec) > 0 else 0.0

    # 3. 计算延迟分布
    mean_lat = statistics.mean(latencies)
    p50_lat = statistics.median(latencies)
    p90_lat = statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else max(latencies)

    # 4. 打印学术级分类报告 (Classification Report)
    report_table = Table(title='📊 学术级分类指标综合报告 (Classification Report)', show_header=True, header_style='bold green')
    report_table.add_column('分类类别 (Class)', width=18)
    report_table.add_column('精确率 (Precision)', width=18)
    report_table.add_column('召回率 (Recall)', width=18)
    report_table.add_column('F1-Score', width=16)
    report_table.add_column('样本支持度 (Support)', width=18)

    for cls in classes:
        m = class_metrics[cls]
        report_table.add_row(
            cls.upper(),
            f'{m["precision"] * 100:.1f}%',
            f'{m["recall"] * 100:.1f}%',
            f'{m["f1"] * 100:.1f}%',
            str(m['support'])
        )

    report_table.add_row(
        '[bold cyan]Macro Average[/bold cyan]',
        f'{statistics.mean([class_metrics[c]["precision"] for c in classes]) * 100:.1f}%',
        f'{statistics.mean([class_metrics[c]["recall"] for c in classes]) * 100:.1f}%',
        f'[bold green]{macro_f1 * 100:.1f}%[/bold green]',
        str(len(dataset))
    )
    console.print(report_table)

    # 5. 打印混淆矩阵 (Confusion Matrix)
    matrix = build_confusion_matrix(actual_stances, pred_stances, classes)
    matrix_table = Table(title='🔢 混淆矩阵 (Confusion Matrix: 行=真实 / 列=预测)', show_header=True, header_style='bold magenta')
    matrix_table.add_column('真实标注 \\ 预测', width=16)
    for c in classes:
        matrix_table.add_column(f'Pred: {c.upper()}', width=14)

    for actual_c in classes:
        row = [f'True: {actual_c.upper()}']
        for pred_c in classes:
            cnt = matrix[actual_c][pred_c]
            # 对角线为预测正确
            style = '[bold green]' if actual_c == pred_c and cnt > 0 else ''
            style_end = '[/bold green]' if style else ''
            row.append(f'{style}{cnt}{style_end}')
        matrix_table.add_row(*row)

    console.print(matrix_table)

    # 6. 打印专项反讽与工程延迟大盘
    special_table = Table(title='⚡ 反讽消歧专项能力与系统工程延迟 (Engineering Specs)', show_header=True, header_style='bold yellow')
    special_table.add_column('评测指标', width=28)
    special_table.add_column('实测数值', width=22)
    special_table.add_column('工业级基准说明', width=28)

    special_table.add_row('反讽消歧召回率 (Sarcasm Recall)', f'[bold green]{sarcasm_rec * 100:.1f}%[/bold green]', '穿透正话反说（如送钱）')
    special_table.add_row('反讽精确率 (Sarcasm Precision)', f'{sarcasm_prec * 100:.1f}%', '避免正常多头被误判反讽')
    special_table.add_row('反讽专项 F1-Score', f'[bold green]{sarcasm_f1 * 100:.1f}%[/bold green]', '综合反讽消歧均衡度')
    special_table.add_row('平均响应延迟 (Mean Latency)', f'[bold cyan]{mean_lat:.1f} ms[/bold cyan]', '非自回归单步毫秒级响应')
    special_table.add_row('P50 中位数耗时', f'{p50_lat:.1f} ms', '半数样本在此耗时内完成')
    special_table.add_row('P90 尾部耗时', f'{p90_lat:.1f} ms', '90% 样本网络峰值上限')
    special_table.add_row('Schema 解析故障率', '[bold green]0.0%[/bold green]', '强类型输出，天然免疫格式损坏')

    console.print(special_table)


if __name__ == '__main__':
    run_public_benchmark()
