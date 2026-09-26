"""SQLite 数据模型、日批次事务与只读查询。"""

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from .models import StockDay, SyncResult


DEFAULT_DB = Path("data/a_shares.sqlite3")
SOURCE = "eastmoney_clist"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    stock_id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    exchange TEXT NOT NULL CHECK (exchange IN ('SH', 'SZ', 'BJ')),
    name TEXT NOT NULL,
    industry TEXT,
    industry_source TEXT,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    UNIQUE (exchange, code)
);
CREATE INDEX IF NOT EXISTS idx_stocks_industry ON stocks(industry);

CREATE TABLE IF NOT EXISTS daily_quotes (
    trade_date TEXT NOT NULL,
    stock_id TEXT NOT NULL REFERENCES stocks(stock_id),
    name TEXT NOT NULL,
    industry TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    previous_close REAL,
    volume_lots INTEGER,
    amount_yuan REAL,
    quote_time TEXT,
    quote_status TEXT NOT NULL CHECK (quote_status IN ('traded', 'no_quote')),
    fetched_at TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (trade_date, stock_id),
    CHECK (quote_status != 'traded' OR (
        open > 0 AND high >= low AND low > 0 AND close > 0
        AND volume_lots > 0 AND amount_yuan >= 0
    )),
    CHECK (quote_status != 'no_quote' OR (
        open IS NULL AND high IS NULL AND low IS NULL AND close IS NULL
        AND previous_close IS NULL AND volume_lots IS NULL AND amount_yuan IS NULL
    ))
);
CREATE INDEX IF NOT EXISTS idx_daily_stock_date ON daily_quotes(stock_id, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_date_industry ON daily_quotes(trade_date, industry);

CREATE TABLE IF NOT EXISTS sync_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    expected_stocks INTEGER,
    received_stocks INTEGER,
    traded_quotes INTEGER,
    no_quote_stocks INTEGER,
    missing_industries INTEGER,
    source TEXT NOT NULL,
    error TEXT
);
"""


def _connect(path: str | Path, *, create: bool = False) -> sqlite3.Connection:
    db_path = Path(path).expanduser()
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    elif not db_path.is_file():
        raise FileNotFoundError(f"数据库不存在: {db_path}，请先执行 init 或 sync")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_database(path: str | Path = DEFAULT_DB) -> Path:
    """只建表，不将任何缺乏来源时间戳的数据写成行情。"""
    with closing(_connect(path, create=True)) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            raise RuntimeError(f"不支持的数据库版本 {version}；当前版本 {SCHEMA_VERSION}")
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()
    return Path(path).expanduser()


STOCK_UPSERT = """
INSERT INTO stocks (
    stock_id, code, exchange, name, industry, industry_source,
    first_seen_date, last_seen_date
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(stock_id) DO UPDATE SET
    name=CASE WHEN excluded.last_seen_date >= stocks.last_seen_date
              THEN excluded.name ELSE stocks.name END,
    industry=CASE WHEN excluded.industry IS NOT NULL
                       AND excluded.last_seen_date >= stocks.last_seen_date
                  THEN excluded.industry ELSE stocks.industry END,
    industry_source=CASE WHEN excluded.industry IS NOT NULL
                              AND excluded.last_seen_date >= stocks.last_seen_date
                         THEN excluded.industry_source ELSE stocks.industry_source END,
    first_seen_date=MIN(stocks.first_seen_date, excluded.first_seen_date),
    last_seen_date=MAX(stocks.last_seen_date, excluded.last_seen_date)
"""

DAILY_UPSERT = """
INSERT INTO daily_quotes (
    trade_date, stock_id, name, industry, open, high, low, close,
    previous_close, volume_lots, amount_yuan, quote_time, quote_status,
    fetched_at, source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(trade_date, stock_id) DO UPDATE SET
    name=excluded.name,
    industry=COALESCE(excluded.industry, daily_quotes.industry),
    open=CASE WHEN excluded.quote_status='traded' THEN excluded.open ELSE daily_quotes.open END,
    high=CASE WHEN excluded.quote_status='traded' THEN excluded.high ELSE daily_quotes.high END,
    low=CASE WHEN excluded.quote_status='traded' THEN excluded.low ELSE daily_quotes.low END,
    close=CASE WHEN excluded.quote_status='traded' THEN excluded.close ELSE daily_quotes.close END,
    previous_close=CASE WHEN excluded.quote_status='traded'
                        THEN excluded.previous_close ELSE daily_quotes.previous_close END,
    volume_lots=CASE WHEN excluded.quote_status='traded'
                     THEN excluded.volume_lots ELSE daily_quotes.volume_lots END,
    amount_yuan=CASE WHEN excluded.quote_status='traded'
                    THEN excluded.amount_yuan ELSE daily_quotes.amount_yuan END,
    quote_time=CASE WHEN excluded.quote_status='traded'
                    THEN excluded.quote_time ELSE daily_quotes.quote_time END,
    quote_status=CASE WHEN excluded.quote_status='traded'
                      THEN 'traded' ELSE daily_quotes.quote_status END,
    fetched_at=excluded.fetched_at,
    source=excluded.source
"""


def write_day(
    path: str | Path,
    days: list[StockDay],
    result: SyncResult,
    *,
    started_at: str,
    finished_at: str,
) -> None:
    """主数据、行情和成功审计在同一个事务内提交；失败时全部回滚。"""
    if len(days) != result.expected_stocks or not days:
        raise ValueError("批次条数必须与服务端全市场证券数量相同")
    with closing(_connect(path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                STOCK_UPSERT,
                [
                    (
                        day.stock_id, day.code, day.exchange, day.name,
                        day.industry, "eastmoney_f100" if day.industry else None,
                        day.trade_date, day.trade_date,
                    )
                    for day in days
                ],
            )
            conn.executemany(
                DAILY_UPSERT,
                [
                    (
                        day.trade_date, day.stock_id, day.name, day.industry,
                        day.open, day.high, day.low, day.close, day.previous_close,
                        day.volume_lots, day.amount_yuan, day.quote_time,
                        day.quote_status, finished_at, SOURCE,
                    )
                    for day in days
                ],
            )
            conn.execute(
                """INSERT INTO sync_runs (
                    trade_date, started_at, finished_at, status, expected_stocks,
                    received_stocks, traded_quotes, no_quote_stocks,
                    missing_industries, source
                ) VALUES (?, ?, ?, 'success', ?, ?, ?, ?, ?, ?)""",
                (
                    result.trade_date, started_at, finished_at,
                    result.expected_stocks, len(days), result.traded_quotes,
                    result.no_quote_stocks, result.missing_industries, SOURCE,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def record_failure(path: str | Path, *, started_at: str, error: str) -> None:
    """记录失败原因；绝不将不完整证券批次当作成功批次提交。"""
    with closing(_connect(path)) as conn:
        conn.execute(
            """INSERT INTO sync_runs (started_at, finished_at, status, source, error)
               VALUES (?, ?, 'failed', ?, ?)""",
            (
                started_at,
                datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
                SOURCE,
                error[:500],
            ),
        )
        conn.commit()


def get_stats(path: str | Path = DEFAULT_DB) -> dict[str, object]:
    with closing(_connect(path)) as conn:
        stocks = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        latest = conn.execute("SELECT MAX(trade_date) FROM daily_quotes").fetchone()[0]
        latest_rows = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN quote_status='traded' THEN 1 ELSE 0 END) AS traded
               FROM daily_quotes WHERE trade_date=?""",
            (latest,),
        ).fetchone()
        missing = conn.execute("SELECT COUNT(*) FROM stocks WHERE industry IS NULL").fetchone()[0]
        last_run = conn.execute(
            "SELECT * FROM sync_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
    return {
        "stocks": stocks,
        "missing_industries": missing,
        "latest_trade_date": latest,
        "latest_daily_rows": latest_rows["total"],
        "latest_traded_quotes": latest_rows["traded"] or 0,
        "last_run": dict(last_run) if last_run else None,
    }


def get_history(path: str | Path, code: str, *, limit: int = 30) -> list[dict[str, object]]:
    if not code.isdigit() or len(code) != 6 or not 1 <= limit <= 1000:
        raise ValueError("code 必须为 6 位数字，limit 必须在 1..1000 之间")
    with closing(_connect(path)) as conn:
        rows = conn.execute(
            """SELECT s.code, s.exchange, d.trade_date, d.name, d.industry,
                      d.open, d.high, d.low, d.close, d.previous_close,
                      d.volume_lots, d.amount_yuan, d.quote_time, d.quote_status
               FROM daily_quotes AS d JOIN stocks AS s ON s.stock_id=d.stock_id
               WHERE s.code=? ORDER BY d.trade_date DESC LIMIT ?""",
            (code, limit),
        ).fetchall()
    return [dict(row) for row in rows]
