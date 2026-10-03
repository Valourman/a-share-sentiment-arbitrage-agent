"""P2 并发与资源生命周期加固专项单元测试套件

涵盖:
1. SQLite WAL 模式启用与并发读写能力验证
2. 统一 HTTP 会话与连接池管理、复用及安全生命周期释放
3. 文本切片与 BM25 检索对金融专有符号 ($AAPL、¥100 等) 的结构化解析与精确匹配
"""

import os
import tempfile
import httpx
from src.market_data.storage import _connect, init_database
from src.core.http import create_http_client, get_shared_http_client, close_shared_http_client
from src.tools.scraper import StockForumScraper
from src.tools.analyzer import FinancialSentimentAnalyzer
from src.tools.market import MarketDataTool
from src.knowledge.sparse_retriever import BM25Retriever
from src.knowledge.chunker import FinancialChunker
from src.knowledge.schema import Chunk, Document


# ==============================================================================
# P2-1: SQLite WAL 模式与并发读写验证
# ==============================================================================

def test_sqlite_wal_mode_enabled_on_persistent_db():
    """验证文件型 SQLite 数据库连接默认启用 WAL 模式"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_market.db")
        init_database(db_path)

        conn = _connect(db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()


def test_sqlite_wal_concurrent_readers_and_writers():
    """验证在 WAL 模式下多连接并发读取与写入不产生排他锁阻塞"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent_test.db")
        init_database(db_path)

        conn1 = _connect(db_path)
        conn2 = _connect(db_path)
        try:
            # 连接 1 写入事务
            conn1.execute("BEGIN IMMEDIATE")
            conn1.execute(
                "INSERT INTO sync_runs (trade_date, started_at, finished_at, status, source) VALUES (?, ?, ?, ?, ?)",
                ("2026-09-30", "2026-09-30 15:00:00", "2026-09-30 15:01:00", "success", "test_source")
            )
            # 连接 2 并发读取（WAL 模式下读不被写阻塞）
            rows = conn2.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0]
            assert rows == 0  # 尚未 commit，读取一致的旧快照

            conn1.commit()
            rows_after = conn2.execute("SELECT COUNT(*) FROM sync_runs").fetchone()[0]
            assert rows_after == 1
        finally:
            conn1.close()
            conn2.close()


# ==============================================================================
# P2-2: 统一 HTTP 会话与连接池复用及释放
# ==============================================================================

def test_unified_http_pool_creation_and_reuse():
    """验证全局与自定义 HTTP 客户端具备连接池配置与生命周期控制"""
    client = get_shared_http_client()
    assert isinstance(client, httpx.Client)
    assert not client.is_closed

    # 再次获取应当是同一个复用实例
    client2 = get_shared_http_client()
    assert client is client2

    # 显式关闭共享连接池
    close_shared_http_client()
    assert client.is_closed


def test_scraper_and_analyzer_and_market_tool_client_lifecycle():
    """验证感知工具支持依赖注入、连接池复用与显式 close / context 释放"""
    custom_client = create_http_client(timeout=3.0)
    try:
        # 1. 验证 Scraper 支持依赖注入与上下文关闭
        with StockForumScraper(client=custom_client) as scraper:
            assert scraper._get_client() is custom_client

        # 2. 验证 Analyzer 支持自定义 client
        with FinancialSentimentAnalyzer(http_client=custom_client) as analyzer:
            assert analyzer._get_http_client() is custom_client

        # 3. 验证 MarketDataTool 支持自定义 client
        with MarketDataTool(client=custom_client) as market_tool:
            assert market_tool._get_client() is custom_client
    finally:
        custom_client.close()


# ==============================================================================
# P2-3: 文本切片与 BM25 对金融符号 ($AAPL、¥100 等) 的解析与匹配
# ==============================================================================

def test_bm25_tokenize_financial_symbols():
    """验证 BM25Retriever._tokenize 正确保留金融 Cashtag、货币符号及百分比"""
    retriever = BM25Retriever()
    text = "重点关注 $AAPL 股价目标 ¥100，同时留意 $600519 涨幅突破 5.5% 和 $TSLA"
    tokens = retriever._tokenize(text)

    # 验证金融实体 token 存在
    assert "$aapl" in tokens
    assert "aapl" in tokens       # 同时派发脱符 token 保证通用检索
    assert "¥100" in tokens
    assert "$600519" in tokens
    assert "5.5%" in tokens
    assert "$tsla" in tokens


def test_bm25_search_exact_financial_symbols():
    """测试 BM25 稀疏索引对金融符号查询的高精确召回能力"""
    retriever = BM25Retriever()
    chunk1 = Chunk(chunk_id="c1", doc_id="d1", text="机构上调 $AAPL 目标价至 $220")
    chunk2 = Chunk(chunk_id="c2", doc_id="d2", text="苹果公司最新财报出炉，普通单词提到 aapl")
    chunk3 = Chunk(chunk_id="c3", doc_id="d3", text="贵州茅台批价回升，当前单瓶指导价为 ¥100 折扣")
    chunk4 = Chunk(chunk_id="c4", doc_id="d4", text="普通数值100元，不带金融币种符号")

    retriever.add_chunks([chunk1, chunk2, chunk3, chunk4])

    # 1. 查询带 $ 符号的 Cashtag
    results_cashtag = retriever.search("$AAPL", top_k=2)
    assert len(results_cashtag) > 0
    # 包含 $AAPL 标号的 chunk1 应排在首位
    assert results_cashtag[0][0].chunk_id == "c1"

    # 2. 查询带 ¥ 符号的货币金额
    results_currency = retriever.search("¥100", top_k=2)
    assert len(results_currency) > 0
    # 精确带 ¥100 符号的 chunk3 应排在首位
    assert results_currency[0][0].chunk_id == "c3"


def test_chunker_avoids_cutting_financial_symbols():
    """验证 FinancialChunker 在滑动窗口或长段硬切时不腰斩金融符号与金额"""
    chunker = FinancialChunker(chunk_size=30, chunk_overlap=10)
    # 构造正好在截断边界附近的金融符号
    content = "前期震荡整理阶段，主力资金持续大举买入 $AAPL 和 ¥100 目标筹码，预期后市爆发。"
    doc = Document(doc_id="doc_fin", title="金融符号切片测试", content=content)

    chunks = chunker.split(doc)
    assert len(chunks) >= 2

    # 拼接或遍历所有切片，验证没有任何一个切片把 $AAPL 截为 $ 或 AAPL 单独挂断
    for c in chunks:
        # 不应出现孤立且残缺的 $ 或 ¥ 后紧接切断
        assert not c.text.endswith("$")
        assert not c.text.endswith("¥")
        assert not c.text.endswith("￥")
