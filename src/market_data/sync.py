"""全市场快照转逐日行情：严守来源日期、全量检查与事务边界。"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import logging
import math
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from .eastmoney import EastmoneySource, Universe
from .models import StockDay, SyncResult
from .storage import DEFAULT_DB, init_database, record_failure, write_day


SHANGHAI = ZoneInfo("Asia/Shanghai")
EARLIEST_SAME_DAY_SYNC = time(16, 0)  # 下午收盘后缓冲，拒绝分时数据当收盘价
MIN_UNIVERSE_STOCKS = 4000  # 防止公开接口只返回单市场/约半数股票仍显示“成功”
MIN_DATED_QUOTE_RATIO = 0.80
MIN_INDUSTRY_RATIO = 0.80  # 防止上游 f100 集体失效后把全库行业清空
MIN_DOMINANT_DATE_RATIO = 0.95
MAX_SOURCE_AGE_DAYS = 14  # 允许长假，拒绝长期不刷新的数据源

logger = logging.getLogger(__name__)


class SyncError(ValueError):
    """日期、证券归属、字段或全量质量检查不通过。"""


@dataclass(frozen=True)
class _RawStock:
    code: str
    exchange: str
    name: str
    industry: str | None
    quote_time: datetime | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    previous_close: float | None
    volume_lots: int | None
    amount_yuan: float | None
    quotable: bool


def _number(value: object, field: str) -> float | None:
    if value is None or value in ("", "-", "--"):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SyncError(f"{field} 数值格式无效: {value!r}")
    try:
        number = float(value)
    except ValueError as exc:
        raise SyncError(f"{field} 数值格式无效: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise SyncError(f"{field} 不能为负数/无穷大: {value!r}")
    return number


def _quote_time(value: object) -> datetime | None:
    if value is None or value in ("", "-", 0):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise SyncError(f"f124 时间戳无效: {value!r}")
    try:
        timestamp = int(value)
        if timestamp <= 0 or str(value) != str(timestamp):
            raise ValueError(value)
        return datetime.fromtimestamp(timestamp, SHANGHAI)
    except (ValueError, OverflowError, OSError) as exc:
        raise SyncError(f"f124 时间戳无效: {value!r}") from exc


def _normalise(row: dict[str, Any]) -> _RawStock:
    code = row.get("f12")
    market = row.get("f13")
    name = row.get("f14")
    if not isinstance(code, str) or not re.fullmatch(r"\d{6}", code):
        raise SyncError(f"股票代码 f12 无效: {code!r}")
    if isinstance(market, bool) or market not in (0, 1):
        raise SyncError(f"{code} 市场代码 f13 无效: {market!r}")
    if code.startswith("6") and market == 1:
        exchange = "SH"
    elif code.startswith(("0", "3")) and market == 0:
        exchange = "SZ"
    elif code.startswith(("4", "8", "92")) and market == 0:
        exchange = "BJ"
    else:
        raise SyncError(f"{code} 不属于预期的沪深北 A 股（f13={market!r}）")
    if not isinstance(name, str) or not name.strip():
        raise SyncError(f"{code} 缺少股票名称 f14")
    industry = row.get("f100")
    industry = industry.strip() if isinstance(industry, str) else None
    if industry in ("", "-", "--", "—"):
        industry = None

    open_ = _number(row.get("f17"), f"{code}.f17")
    high = _number(row.get("f15"), f"{code}.f15")
    low = _number(row.get("f16"), f"{code}.f16")
    close = _number(row.get("f2"), f"{code}.f2")
    previous_close = _number(row.get("f18"), f"{code}.f18")
    volume = _number(row.get("f5"), f"{code}.f5")
    amount = _number(row.get("f6"), f"{code}.f6")
    if volume is not None and not volume.is_integer():
        raise SyncError(f"{code} 成交量 f5 不是整手数")
    volume_lots = int(volume) if volume is not None else None
    quotable = (
        all(price is not None and price > 0 for price in (open_, high, low, close))
        and volume_lots is not None and volume_lots > 0
        and amount is not None
    )
    if quotable and (high < max(open_, low, close) or low > min(open_, high, close)):
        raise SyncError(f"{code} OHLC 高低价不一致")
    return _RawStock(
        code=code,
        exchange=exchange,
        name=name.strip(),
        industry=industry,
        quote_time=_quote_time(row.get("f124")),
        open=open_,
        high=high,
        low=low,
        close=close,
        previous_close=previous_close if previous_close and previous_close > 0 else None,
        volume_lots=volume_lots,
        amount_yuan=amount,
        quotable=quotable,
    )


def prepare_day(
    universe: Universe,
    *,
    now: datetime,
    requested_date: date | None = None,
    min_stocks: int = MIN_UNIVERSE_STOCKS,
    min_quote_ratio: float = MIN_DATED_QUOTE_RATIO,
    min_industry_ratio: float = MIN_INDUSTRY_RATIO,
    max_age_days: int = MAX_SOURCE_AGE_DAYS,
) -> tuple[list[StockDay], SyncResult]:
    """全批次转换与校验；返回前不接触数据库。"""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now 必须包含时区")
    if (
        min_stocks < 1 or not 0 < min_quote_ratio <= 1
        or not 0 < min_industry_ratio <= 1 or max_age_days < 0
    ):
        raise ValueError("质量阈值无效")
    local_now = now.astimezone(SHANGHAI)
    if universe.total < min_stocks or len(universe.rows) != universe.total:
        raise SyncError(
            f"全市场批次不足/不完整：服务端 {universe.total}，实际 {len(universe.rows)}，"
            f"下限 {min_stocks}"
        )
    raw_stocks = [_normalise(row) for row in universe.rows]
    industry_count = sum(row.industry is not None for row in raw_stocks)
    if industry_count < math.ceil(universe.total * min_industry_ratio):
        raise SyncError(
            f"行业标签覆盖率 {industry_count}/{universe.total}，"
            f"低于 {min_industry_ratio:.0%} 下限；请检查数据源 f100"
        )
    stock_ids = {(row.exchange, row.code) for row in raw_stocks}
    if len(stock_ids) != universe.total:
        raise SyncError("证券代码重复，拒绝整批入库")
    quote_dates = [
        row.quote_time.date()
        for row in raw_stocks
        if row.quotable and row.quote_time is not None
    ]
    if not quote_dates:
        raise SyncError("无带有有效来源日期的行情")
    date_counts = Counter(quote_dates)
    trade_date, dated_count = date_counts.most_common(1)[0]
    if dated_count < math.ceil(universe.total * min_quote_ratio):
        raise SyncError(
            f"{trade_date} 有效同日行情 {dated_count}/{universe.total}，"
            f"低于 {min_quote_ratio:.0%} 下限"
        )
    if dated_count / len(quote_dates) < MIN_DOMINANT_DATE_RATIO:
        raise SyncError(f"接口跨日期混合过多：{dict(date_counts)}")
    if any(day > trade_date for day in quote_dates):
        raise SyncError(f"接口正在从 {trade_date} 更新至新交易日，稍后重试")
    if requested_date is not None and trade_date != requested_date:
        raise SyncError(f"数据源实际交易日 {trade_date}，不等于要求的 {requested_date}")
    if trade_date > local_now.date():
        raise SyncError(f"数据源交易日 {trade_date} 晚于本地 {local_now.date()}")
    if local_now.date() - trade_date > timedelta(days=max_age_days):
        raise SyncError(f"数据源交易日 {trade_date} 已超过 {max_age_days} 天")
    if trade_date == local_now.date() and local_now.time() < EARLIEST_SAME_DAY_SYNC:
        raise SyncError(f"{trade_date} 尚未过收盘缓冲时间 16:00（北京时间）")
    if any(row.quote_time and row.quote_time > local_now + timedelta(minutes=5) for row in raw_stocks):
        raise SyncError("出现未来的报价时间戳，拒绝入库")

    days: list[StockDay] = []
    for row in raw_stocks:
        traded = bool(row.quotable and row.quote_time and row.quote_time.date() == trade_date)
        days.append(
            StockDay(
                trade_date=trade_date.isoformat(),
                stock_id=f"{row.exchange}:{row.code}",
                code=row.code,
                exchange=row.exchange,
                name=row.name,
                industry=row.industry,
                open=row.open if traded else None,
                high=row.high if traded else None,
                low=row.low if traded else None,
                close=row.close if traded else None,
                previous_close=row.previous_close if traded else None,
                volume_lots=row.volume_lots if traded else None,
                amount_yuan=row.amount_yuan if traded else None,
                quote_time=row.quote_time.isoformat(timespec="seconds") if row.quote_time else None,
                quote_status="traded" if traded else "no_quote",
            )
        )
    traded_count = sum(day.quote_status == "traded" for day in days)
    result = SyncResult(
        trade_date=trade_date.isoformat(),
        expected_stocks=universe.total,
        written_stocks=len(days),
        traded_quotes=traded_count,
        no_quote_stocks=len(days) - traded_count,
        missing_industries=sum(day.industry is None for day in days),
    )
    return days, result


def sync_latest(
    db_path: str | Path = DEFAULT_DB,
    *,
    source: EastmoneySource | None = None,
    requested_date: date | None = None,
    now: datetime | None = None,
    min_stocks: int = MIN_UNIVERSE_STOCKS,
    min_quote_ratio: float = MIN_DATED_QUOTE_RATIO,
    min_industry_ratio: float = MIN_INDUSTRY_RATIO,
) -> SyncResult:
    """只同步公开接口的最新完整交易日；重复调用按 (交易日, 股票) 幂等更新。"""
    local_now = now or datetime.now(SHANGHAI)
    started_at = local_now.astimezone(SHANGHAI).isoformat(timespec="seconds")
    init_database(db_path)
    try:
        if source is None:
            with EastmoneySource() as provider:
                universe = provider.fetch_all()
        else:
            universe = source.fetch_all()
        days, result = prepare_day(
            universe,
            now=local_now,
            requested_date=requested_date,
            min_stocks=min_stocks,
            min_quote_ratio=min_quote_ratio,
            min_industry_ratio=min_industry_ratio,
        )
        finished_at = (local_now if now else datetime.now(SHANGHAI)).isoformat(timespec="seconds")
        write_day(db_path, days, result, started_at=started_at, finished_at=finished_at)
        return result
    except Exception as exc:
        try:
            record_failure(db_path, started_at=started_at, error=f"{type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("同步失败，同时无法写入失败审计记录")
        raise
