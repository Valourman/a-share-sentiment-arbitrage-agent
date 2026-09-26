"""全市场日库离线测试：无公网依赖，不将快照误认为历史日线。"""

from dataclasses import replace
from datetime import date, datetime
import sqlite3

import httpx
import pytest

from src.market_data.__main__ import main
from src.market_data.eastmoney import EastmoneySource, SourceError, Universe
from src.market_data.storage import (
    get_history,
    get_stats,
    init_database,
    write_day,
)
from src.market_data.sync import SHANGHAI, SyncError, prepare_day, sync_latest


SOURCE_DAY = date(2026, 9, 24)
SOURCE_TIME = int(datetime(2026, 9, 24, 15, 35, tzinfo=SHANGHAI).timestamp())
LATER = datetime(2026, 9, 25, 12, 0, tzinfo=SHANGHAI)


def row(code="600519", market=1, **changes):
    result = {
        "f12": code,
        "f13": market,
        "f14": "贵州茅台",
        "f100": "白酒Ⅱ",
        "f2": 1500.0,
        "f15": 1510.0,
        "f16": 1480.0,
        "f17": 1490.0,
        "f18": 1485.0,
        "f5": 12345,
        "f6": 123456789.01,
        "f124": SOURCE_TIME,
    }
    result.update(changes)
    return result


def small_universe():
    return Universe(
        total=3,
        rows=(
            row(),
            row("000001", 0, f14="平安银行", f100="银行"),
            row("920201", 0, f14="北交所示例", f100="医疗器械"),
        ),
    )


class FakeSource:
    def __init__(self, universe):
        self.universe = universe

    def fetch_all(self):
        return self.universe


def mock_source(pages, *, page_size=2, counts=None):
    def respond(request):
        index = int(request.url.params["pn"]) - 1
        assert request.url.params["fs"].startswith("m:0+t:6")
        payload = {
            "rc": 0,
            "data": {"total": counts[index] if counts else 3, "diff": pages[index]},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    return EastmoneySource(client, page_size=page_size, interval=0, attempts=1), client


def test_fetch_all_pages_and_unique_stocks():
    records = list(small_universe().rows)
    source, client = mock_source([records[:2], records[2:]])
    try:
        batch = source.fetch_all()
        assert batch.total == 3
        assert [item["f12"] for item in batch.rows] == ["600519", "000001", "920201"]
    finally:
        client.close()


@pytest.mark.parametrize(
    "pages,counts,error",
    [
        ([[row()], [row("000001", 0)]], [3, 3], "不完整"),
        ([[row(), row("000001", 0)], [row("920201", 0)]], [3, 4], "不完整"),
        ([[row(), row("000001", 0)], [row()]], [3, 3], "重复"),
    ],
)
def test_partial_changed_total_or_duplicate_pages_are_rejected(pages, counts, error):
    source, client = mock_source(pages, counts=counts)
    try:
        with pytest.raises(SourceError, match=error):
            source.fetch_all()
    finally:
        client.close()


def test_retry_transient_429(monkeypatch):
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json={"rc": 0, "data": {"total": 1, "diff": [row()]}})

    monkeypatch.setattr("src.market_data.eastmoney.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        source = EastmoneySource(client, page_size=1, interval=0, attempts=2)
        assert source.fetch_all().total == 1
    assert calls == 2


def test_convert_units_markets_and_real_source_date():
    days, summary = prepare_day(small_universe(), now=LATER, min_stocks=3)
    assert summary.trade_date == "2026-09-24"
    assert summary.traded_quotes == 3
    assert [day.stock_id for day in days] == ["SH:600519", "SZ:000001", "BJ:920201"]
    assert days[0].open == 1490.0 and days[0].close == 1500.0
    assert days[0].volume_lots == 12345  # 上游单位是「手」，不误写成「股」
    assert days[0].amount_yuan == 123456789.01


def test_missing_industry_and_unquoted_stock_have_nulls_not_fabricated_prices():
    rows = list(small_universe().rows)
    rows[2] = row("920201", 0, f14="北交所示例", f100="-", f2="-", f5=0)
    days, summary = prepare_day(
        Universe(3, tuple(rows)), now=LATER, min_stocks=3,
        min_quote_ratio=0.5, min_industry_ratio=0.5,
    )
    assert summary.no_quote_stocks == 1 and summary.missing_industries == 1
    assert days[2].industry is None
    assert days[2].quote_status == "no_quote"
    assert days[2].close is None and days[2].amount_yuan is None
    assert days[2].quote_time is not None  # 仍保留来源时间供排查


def test_today_before_close_and_requested_date_mismatch_are_rejected():
    with pytest.raises(SyncError, match="16:00"):
        prepare_day(
            small_universe(),
            now=datetime(2026, 9, 24, 14, 0, tzinfo=SHANGHAI),
            min_stocks=3,
        )
    with pytest.raises(SyncError, match="实际交易日"):
        prepare_day(
            small_universe(), now=LATER, requested_date=date(2026, 9, 25), min_stocks=3
        )


def test_stale_mixed_dates_and_incomplete_universe_are_rejected():
    with pytest.raises(SyncError, match="下限"):
        prepare_day(small_universe(), now=LATER)  # 默认拒绝仅 3 只的“全市场”
    old = datetime(2026, 9, 23, 15, 0, tzinfo=SHANGHAI)
    rows = list(small_universe().rows)
    rows[1] = row("000001", 0, f124=int(old.timestamp()))
    with pytest.raises(SyncError, match="混合"):
        prepare_day(Universe(3, tuple(rows)), now=LATER, min_stocks=3, min_quote_ratio=0.5)
    with pytest.raises(SyncError, match="超过"):
        prepare_day(
            small_universe(),
            now=datetime(2026, 10, 15, 12, tzinfo=SHANGHAI),
            min_stocks=3,
        )


def test_missing_industry_field_for_whole_market_is_rejected():
    rows = tuple({**record, "f100": "-"} for record in small_universe().rows)
    with pytest.raises(SyncError, match="行业标签覆盖率"):
        prepare_day(Universe(3, rows), now=LATER, min_stocks=3)


@pytest.mark.parametrize(
    "invalid,pattern",
    [
        (row("900901", 1), "不属于预期"),  # 上海 B 股不得混入
        (row(f15=1400.0), "OHLC"),
        (row(f6=float("nan")), "无穷大"),
    ],
)
def test_bad_market_or_financial_fields_fail_closed(invalid, pattern):
    records = list(small_universe().rows)
    records[0] = invalid
    with pytest.raises(SyncError, match=pattern):
        prepare_day(Universe(3, tuple(records)), now=LATER, min_stocks=3)


def test_sync_is_idempotent_and_preserves_known_industry_and_traded_quote(tmp_path):
    db = tmp_path / "a.sqlite3"
    first = sync_latest(db, source=FakeSource(small_universe()), now=LATER, min_stocks=3)
    assert first.written_stocks == 3
    records = list(small_universe().rows)
    records[0] = row(f14="茅台新名", f100="-", f2="-", f5=0)
    sync_latest(
        db,
        source=FakeSource(Universe(3, tuple(records))),
        now=LATER,
        min_stocks=3,
        min_quote_ratio=0.5,
        min_industry_ratio=0.5,
    )
    assert get_stats(db)["stocks"] == 3
    assert get_stats(db)["latest_daily_rows"] == 3
    history = get_history(db, "600519")
    assert len(history) == 1
    assert history[0]["name"] == "茅台新名"
    assert history[0]["industry"] == "白酒Ⅱ"
    assert history[0]["close"] == 1500.0 and history[0]["quote_status"] == "traded"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sync_runs WHERE status='success'").fetchone()[0] == 2
        assert conn.execute("SELECT industry FROM stocks WHERE code='600519'").fetchone()[0] == "白酒Ⅱ"


def test_error_logs_failure_without_creating_incomplete_day(tmp_path):
    db = tmp_path / "a.sqlite3"
    with pytest.raises(SyncError, match="实际交易日"):
        sync_latest(
            db,
            source=FakeSource(small_universe()),
            requested_date=date(2026, 9, 25),
            now=LATER,
            min_stocks=3,
        )
    stats = get_stats(db)
    assert stats["stocks"] == 0 and stats["latest_daily_rows"] == 0
    assert stats["last_run"]["status"] == "failed"
    assert "实际交易日" in stats["last_run"]["error"]


def test_network_failure_does_not_create_stock_data(tmp_path):
    db = tmp_path / "a.sqlite3"

    class BrokenSource:
        def fetch_all(self):
            raise SourceError("第 52 页网络断开")

    with pytest.raises(SourceError):
        sync_latest(db, source=BrokenSource(), now=LATER)
    stats = get_stats(db)
    assert stats["stocks"] == 0 and stats["latest_trade_date"] is None
    assert stats["last_run"]["status"] == "failed"


def test_db_transaction_rolls_back_on_constraint_violation(tmp_path):
    db = tmp_path / "a.sqlite3"
    init_database(db)
    days, result = prepare_day(small_universe(), now=LATER, min_stocks=3)
    days[1] = replace(days[1], volume_lots=-1)
    with pytest.raises(sqlite3.IntegrityError):
        write_day(db, days, result, started_at=LATER.isoformat(), finished_at=LATER.isoformat())
    assert get_stats(db)["stocks"] == 0
    assert get_stats(db)["latest_daily_rows"] == 0


def test_cli_initializes_database_and_queries_empty_stats(tmp_path, capsys):
    db = tmp_path / "other.sqlite3"
    assert main(["--db", str(db), "init"]) == 0
    assert db.is_file()
    assert main(["--db", str(db), "stats"]) == 0
    assert '"stocks": 0' in capsys.readouterr().out
