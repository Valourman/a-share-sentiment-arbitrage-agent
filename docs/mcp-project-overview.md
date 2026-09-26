# 项目概览：A 股舆情反讽研判与盘面背离预警 Agent

## 定位

这是一个 Python 金融智能体项目，目标是把 A 股散户社区的情绪、财经资讯与公告，同公开行情快照放在一起分析，识别反讽和情绪—价格背离，输出结构化研判与审计日志。项目同时包含通用 Agent 框架、可选金融 RAG 知识库、评测脚本和多套界面。

## 核心处理链

1. `src/tools/scraper.py`：分别从东方财富股吧抓取并过滤发帖，从新浪财经抓取个股新闻、公告。`src/agent/engine.py` 当前依次调用三种采集方法。
2. `src/tools/analyzer.py`：识别多空、反讽和 A 股黑话，支持 TypeSafe Jev、OpenAI 兼容 LLM 与规则 Mock；LLM 解析通过 `src/core/parser.py` 和 Pydantic 契约做校验与重试。主业务入口未显式传 `engine_mode` 时依 `use_llm` 在 LLM / Mock 间选择；对话入口可以使用 `auto` 路由。
3. `src/tools/market.py`：调用新浪行情接口获取现价、前收、涨跌幅、成交额。取数失败会返回 `is_trading=False` 的零值快照。
4. `src/agent/engine.py` 调度采集与研判，`src/agent/decision.py` 统一执行背离规则：有效数据下，平均情绪 ≥ 0.20 且涨跌幅 < -0.5% 为 `BULL_TRAP`，平均情绪 ≤ -0.20 且涨跌幅 ≥ 0% 为 `PANIC_BOTTOM`，其他为 `CONSISTENT`；行情或舆情样本不可用时为 `INSUFFICIENT_DATA`，不把零值行情解释成平盘。结果封装于 `src/agent/state.py`，并记录 `execution_logs` 与执行链路。

## 目录与入口

| 路径 | 作用 |
| --- | --- |
| `src/agent/` | 核心金融研判 Agent、对话式 Agent、状态和背离决策。 |
| `src/core/`、`src/agents/` | 配置、模型网关、强类型消息/解析/追踪，以及通用 Agent 范式。 |
| `src/tools/` | 采集、行情、情绪分析和工具注册体系。 |
| `src/knowledge/`、`src/memory/` | 可选的稠密检索 + BM25 + RRF 金融知识库、记忆组件；知识库未见在主研判链中直接调用。 |
| `src/protocols/` | MCP 客户端相关代码与实验性 A2A 骨架。 |
| `app.py` | Streamlit 交互工作台，实际调用 `SentimentArbitrageAgent.run()`。 |
| `frontend/`、`server.py` | 三套静态视觉页面与静态服务器；`frontend/index.html` 使用内置价格样例与延时模拟，并非实时后端接口。 |
| `tests/`、`evals/` | 单元测试和 15 条自建、35 条公开范式语料的评测脚本。 |

## 运行方式

要求 Python ≥ 3.10。按 `README.md` 安装 `pip install -e ".[dev]"`，可从 `.env.example` 复制配置并填写模型密钥。真实交互工作台执行 `streamlit run app.py`；静态界面执行 `python server.py`，默认监听 8080；测试为 `pytest -v tests/`；评测入口包括 `python -m evals.benchmark` 和 `python -m evals.public_benchmark`。

## 解读边界

- 静态页面中的行情、分析结论是演示数据；不要把它们当成实时报价或后端研判结果。
- 外部网页结构、网络与模型密钥会影响实际运行；行情取数失败的零值快照需要特别辨别，不能直接视作有效盘面。
- `README.md` 报告的高准确率来自有限样本，不能据此推断真实市场泛化效果。本轮已运行离线单元测试，但未验证实时行情或模型的市场效果；项目输出不构成投资建议。

分章节的框架对应关系和待补能力记录于 `docs/mcp-hello-agents-gap-analysis.md`。
