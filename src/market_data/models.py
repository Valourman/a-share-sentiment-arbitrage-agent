"""独立于上游接口和 SQLite 的已校验日行情契约。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StockDay:
    trade_date: str
    stock_id: str
    code: str
    exchange: str
    name: str
    industry: str | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    previous_close: float | None
    volume_lots: int | None
    amount_yuan: float | None
    quote_time: str | None
    quote_status: str  # traded / no_quote；no_quote 不伪造停牌原因或行情


@dataclass(frozen=True)
class SyncResult:
    trade_date: str
    expected_stocks: int
    written_stocks: int
    traded_quotes: int
    no_quote_stocks: int
    missing_industries: int
    source: str = "eastmoney_clist"
