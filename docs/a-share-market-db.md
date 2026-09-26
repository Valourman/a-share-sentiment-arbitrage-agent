# 全量 A 股 SQLite 日行情库

## 作用与边界

`src/market_data/` 从东方财富公开全市场行情接口读取**沪深北当前上市 A 股**，存入项目根目录下 `data/a_shares.sqlite3`。不依赖账号或 API Key；与现有个股秒级工具/舆情分析链路解耦。

- `stocks`：交易所、6 位代码、现时名称、行业标签、首次/末次被本地同步看到的交易日。保留曾经入库的标的，不因暂时未出现就删除。
- `daily_quotes`：以 `(trade_date, stock_id)` 唯一，保存**当时**名称、行业及每日价格和量额。每日覆盖当次全市场名录；无可确认的当日成交行情时标为 `no_quote`，价格与量额均为 `NULL`，**不等同于已证实停牌**。
- `sync_runs`：成功/失败时间与质量统计；失败不写入任何不完整的 `stocks`/`daily_quotes` 批次。

首次同步只记录数据源当前可确认的**最近完整交易日**，后续靠每天运行累积日序列。公开全市场快照**不是历史日线接口**：本实现没有对上市以来的过去日线批量回补，也没有对退市股票做完整历史回溯。如需多年历史，须另选真正的历史数据接口并约定起始日期、复权口径与限速方案。

## 运行

项目根目录、Python 3.10+、已安装 `pyproject.toml` 依赖：

```bash
python -m src.market_data init
python -m src.market_data sync
python -m src.market_data stats
python -m src.market_data history 600519 --limit 30
```

默认库为 `data/a_shares.sqlite3`；若自定义位置，**在子命令前**放 `--db`：

```bash
python -m src.market_data --db D:/market/a_shares.sqlite3 sync
```

可选 `sync --date YYYY-MM-DD` **只用于核对**数据源的真实交易日；不匹配即失败，不会按指定日期改写来源时间戳。失败信息写入 `sync_runs.error`，CLI 以非零状态码退出；`stats` 查看最近一次运行结果。周末/假日重复得到最近交易日是正常的：相同 `(日期, 股票)` 幂等更新，不生成休市日行情。

### 设置每天自动运行（需用户自行启用）

Windows 下将 `scripts/sync_a_shares.cmd` 配置到**任务计划程序**：触发器为每天 **18:00 北京时间**（当地系统须为 UTC+8，若不在东八区需换算）；操作的“程序或脚本”设为该 `.cmd` 的**绝对路径**。脚本从仓库目录执行，优先使用 `.venv\Scripts\python.exe`，否则使用 PATH 下的 `python`。请先在终端手动运行脚本确认项目依赖与访问公开接口正常。可根据实际更新时间增加晚间重试触发器，重复执行安全。代码不会擅自注册系统计划任务。

Linux/macOS 可自行设 cron/其他调度器，如服务器为中国标准时间：

```cron
0 18 * * * cd /绝对路径/项目 && /绝对路径/项目/.venv/bin/python -m src.market_data sync >> /绝对路径/market-sync.log 2>&1
```

如果机器并非东八区，请在调度器换算执行时间；程序内部始终用 `Asia/Shanghai` 判定交易日及收盘缓冲。**只运行 `init` 不会自动抓取数据；只有执行 `sync` 才会采集。**

## 来源、字段与质量检查

来源是东方财富公开 `https://push2.eastmoney.com/api/qt/clist/get` 快照接口（非有服务级别保证的官方数据协议）。筛选深圳主板/创业板、上海主板/科创板和北交所；一页最多按 **100 只**分页拉取，逐页间隔 1.5 秒，并对临时错误限次重试。行业来自源字段 `f100`，是**东方财富标签**，不保证属于证监会/申万统一分类；无标签保留 `NULL`，每天的标签另存于 `daily_quotes`，不会凭空推断。

| SQLite 字段 | 来源字段 | 单位/口径 |
| --- | --- | --- |
| `stocks.code`, `stocks.name`, `stocks.industry` | `f12`, `f14`, `f100` | 6 位代码（文本，保留前导零）；名称与行业以数据源为准 |
| `daily_quotes.trade_date`, `quote_time` | 多数有效行情的 `f124` | Unix 秒转**北京时间**，不是本机请求日期 |
| `open`, `high`, `low`, `close`, `previous_close` | `f17`, `f15`, `f16`, `f2`, `f18` | 元/股，**未复权**；`previous_close` 无可靠数值时可空 |
| `volume_lots`, `amount_yuan` | `f5`, `f6` | **手**（A 股通常 1 手=100 股）、**元**；不擅自换算为股/亿元 |
| `quote_status` | 校验结果 | `traded` 或 `no_quote`；后者价格量额为空，原因未确认 |

写入前必须同时满足：服务端 `total`、每页应有条数、唯一证券数一致；整体证券数至少 4000；行业标签覆盖至少 80%；有效同交易日行情不少于总数的 80%，有效时间戳中至少 95% 为同日；不包含更晚的交易日；不超过 14 天；若来源日期就是今天，必须已过北京时间 **16:00**。日期、证券市场或 OHLC 异常会拒绝整个批次。所有证券主数据、日行情与成功审计在同一 SQLite 事务内写入或回滚。`sync_runs` 的失败行与证券数据事务分开记载，以便发现断网/限流，不代表该日已入库。重跑同一天会更新已确认的成交行情，但不会用缺失行情覆盖已有有效价格或用空行业覆盖已知行业。

**注意**：公开接口可能限流、拒绝连接、改变分页/字段或收盘后延迟更新；仅有 1 个市场或 2900 多只股票时会拒绝“成功”。如果数据源仍返回昨日行情，程序只会处理该来源日，不会把昨日价格标成今日；`--date 今日` 可用于强制检查是否已更新。原始来源每天存在停牌、延时报价和数据修正等不确定性，不能作为权威结算数据或投资建议。

## SQLite 查询样例

```sql
-- 最近记录的交易日及其股票/有效报价数
SELECT trade_date, COUNT(*) AS stocks,
       SUM(quote_status = 'traded') AS quoted
FROM daily_quotes GROUP BY trade_date ORDER BY trade_date DESC LIMIT 5;

-- 某日按行业查询（以当日保存的标签为准）
SELECT s.code, d.name, d.industry, d.close, d.volume_lots, d.amount_yuan
FROM daily_quotes AS d JOIN stocks AS s USING(stock_id)
WHERE d.trade_date = '2026-09-24' AND d.industry = '白酒Ⅱ';

-- 股票近 20 个已存的交易日，含无行情状态
SELECT trade_date, open, high, low, close, quote_status
FROM daily_quotes WHERE stock_id = 'SH:600519'
ORDER BY trade_date DESC LIMIT 20;

-- 最新同步成功或失败及原因
SELECT run_id, trade_date, status, received_stocks, error
FROM sync_runs ORDER BY run_id DESC LIMIT 5;
```

SQLite 文件已被 `.gitignore` 排除，请自行备份 `data/a_shares.sqlite3`；长时间积累的数据量随交易日增长。离线测试：`python -m pytest -q tests/test_market_data.py`。

## 首次联网验证记录（2026-09-25）

当时接口首页返回 `total=5920`，100 条样本的行业标签可读，行情时间戳对应 **2026-09-24**。一次全市场导入在第 52 页遇到网络代理断连；随后接口请求又返回 502。安全检查没有通过，因此**本次未导入任何股票或日行情**；`data/a_shares.sqlite3` 目前仅有表结构和一条失败审计，`stats` 显示 `stocks=0`。这不代表服务已经持续同步。网络恢复后请重新运行 `python -m src.market_data sync`，再用 `stats` 核实 `last_run.status=success`、证券数和交易日期；无须重新建表。
