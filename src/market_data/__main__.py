"""python -m src.market_data [--db 文件] init|sync|stats|history。"""

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
import sys

from .storage import DEFAULT_DB, get_history, get_stats, init_database
from .sync import sync_latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="沪深北 A 股 SQLite 每日基础资料及行情")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"数据库文件，默认 {DEFAULT_DB}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="仅初始化数据表，不连接网络")
    sync = commands.add_parser("sync", help="同步公开数据源的最新完整交易日")
    sync.add_argument("--date", type=date.fromisoformat, help="要求数据源日期为 YYYY-MM-DD；不可伪造历史")
    commands.add_parser("stats", help="查看股票数量、最近日期和同步审计")
    history = commands.add_parser("history", help="查询某只股票的本地日行情")
    history.add_argument("code", help="6 位股票代码")
    history.add_argument("--limit", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = {"database": str(init_database(args.db)), "status": "initialized"}
        elif args.command == "sync":
            result = asdict(sync_latest(args.db, requested_date=args.date))
        elif args.command == "stats":
            result = get_stats(args.db)
        else:
            result = get_history(args.db, args.code, limit=args.limit)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"同步/查询失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
