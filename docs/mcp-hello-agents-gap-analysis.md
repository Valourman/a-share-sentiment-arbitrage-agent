# Hello-Agents 框架对照、整理与待补能力

## 对照范围

参照 Datawhale [Hello-Agents](https://hello-agents.datawhale.cc/#/) 教程第 4、7、8、9、10、12 章，对当前 A 股舆情 Agent 的分层、实际调用链及业务安全边界进行盘点。教程是渐进式学习路线，并非每个章节的示例都必须进入金融产品；这里将“实现了一个同名类”与“完整实现了相应协议/能力”严格区分。

## 本轮代码整理

- 保留 `src/agent/base_reflection.py` 旧导入路径，但让通用 `ReflectionAgent` 只在 `src/agents/reflection_agent.py` 维护一份；`src/agent/` 专注金融业务。
- 将规则判定与文案从 `src/agent/engine.py` 提取到 `src/agent/decision.py`，使采集、校验、决策职责分开；反思阶段使用批判阶段的同一份结果，不再重复判断。
- 每个业务 Agent 默认创建绑定到自身 LLM 的情绪工具，避免全局注册器在导入时创建的模型客户端绕开 Streamlit 会话设置；明确传入的工具注册器仍可覆盖它。
- 明确区分有效行情、零值失败快照和无舆情样本；不足时输出 `INSUFFICIENT_DATA / UNKNOWN`，Streamlit 和对话入口不将其作为买卖信号。反思说明不再凭涨跌幅推断主力资金流向。
- 增加 `tests/test_framework_alignment.py` 回归场景；未将外部 API 真实性纳入离线单测。

## 分章节对应与缺口

| 章节/层 | 已有实现 | 尚缺或仅部分实现 | 优先级 |
| --- | --- | --- | --- |
| 第 4、7 章：经典范式与框架底座 | `src/core/` 的 Agent、Message、LLM、配置、异常、追踪；`src/agents/` 的 Simple/ReAct/Reflection/Plan-and-Solve/FunctionCall；`src/tools/` 的 Tool/Registry/Chain。 | 通用 `ReflectionAgent.max_iterations` 未形成多轮迭代；业务链直接调用具象工具方法，并非统一从注册器执行；各工具返回类型没有统一契约；包导入时注册全局工具具有副作用。 | P1 |
| 第 8 章：记忆与 RAG | `src/memory/` 有短时 TTL 和 `MemoryTool`；`src/knowledge/` 有分块、BM25、向量检索与 RRF，另有 `FinancialKnowledgeTool`。 | “长期记忆”和默认向量索引仍为进程内存；默认哈希 embedding 不是可验证的语义模型；主研判链尚未调用 RAG，也未将新闻/公告正文入库、标注来源时间后用于反思。 | P1 |
| 第 9 章：上下文工程 | 对话入口保存焦点股票和历史；研判状态保留新闻、公告与审计日志。 | 没有 `ContextBuilder` 一类的预算、筛选、压缩与证据来源控制；仍有长提示词拼接。教程的 NoteTool、TerminalTool 面向长程代码任务，金融应用是否需要应按场景评估。 | P1 |
| 第 10 章：MCP / A2A / ANP | `src/protocols/mcp/` 与 `src/protocols/a2a/` 提供进程内工具/任务对象。 | MCP 类不具备标准 JSON-RPC 初始化、传输、资源/提示词协商；A2A 缺少远程 Agent Card、HTTP 任务生命周期；ANP 未实现。现有类不能直接作为互操作协议服务。 | P2（如需跨进程集成则 P1） |
| 第 12 章：评估 | `tests/` 覆盖解析器、工具和业务规则；`evals/` 提供 15 条自建、35 条范式语料评测脚本。 | 仍缺独立时间切分与更大规模盲测、系统化的外部源故障/过期数据矩阵（当前仅补了零值行情与无样本的基础分支）、错误来源归因与实盘外推验证；README 的高准确率不能当作生产效果。 | P1 |
| 应用交付 | `app.py` 是实际 Streamlit 入口；`server.py` 可提供静态页面。 | `frontend/index.html` 等静态演示页使用内置行情，没有后端 API；爬虫依赖第三方网页结构与网络，需监控、重试和数据时间戳校验；对话中仍有基于简单阈值的过度确定性因果措辞，须进一步审校。 | P0/P1 |

## 建议后续顺序

1. **P0 数据与表述安全**：为行情快照定义来源、时间戳、可用性与停牌状态；对对话模板做金融风险审校，禁止把情绪背离叙述成已证实的资金流向；标记离线/演示数据。
2. **P1 框架贯通**：统一 Tool 调用/返回与注入方式；为舆情、新闻正文、公告构建带引用和 token 预算的领域 ContextBuilder，按需求将 RAG/记忆接入主链，并建立端到端离线评测。
3. **P2 按需扩展**：只有业务确需跨应用调用时实现标准 MCP/A2A 传输；不要把教程中的 NoteTool/TerminalTool 或 ANP 当成硬性前置条件。

## 验证说明

- `python -m pytest -q tests/`：95 passed；存在 `pytest-asyncio` 默认 fixture loop scope 未配置的弃用警告，未导致测试失败。
- `python -m ruff check src/agent/decision.py tests/test_framework_alignment.py`、`git diff --check`：通过；`get_diagnostics` 对 `src/agent/`、`app.py` 和新测试文件未报告错误或警告。
- 离线单测并不能证明 live API、新闻/行情时效性或真实市场研判准确度；这些项目仍需独立验证。
