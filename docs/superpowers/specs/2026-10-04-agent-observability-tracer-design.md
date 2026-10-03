# Agent 全链路日志与可观测性审计追踪系统设计方案与技术规格书

- **文档状态**：已冻结 (Design Ready)
- **对应 PRD**：[docs/specs/agent-observability-tracer-prd.md](../../specs/agent-observability-tracer-prd.md)
- **目标领域**：开发者与算法调试为主的智能体可观测性系统（本地开箱即用 + 兼容行业标准）

---

## 1. 架构目标与设计原则

1. **零阻断原则 (Fail-Safe First)**：可观测性属于旁路监控能力，数据库锁、网络波动或序列化异常严禁向上传导中断核心交易舆情研判主流程。
2. **轻量与可扩展 (Lightweight & Standard-Aligned)**：本地默认依靠 SQLite 与按日轮转的 JSON Lines 文件运行，不强依赖任何第三方云服务；同时核心数据模型全面兼容 OpenTelemetry GenAI 规范与 Langfuse API 协议。
3. **上下文透明传递 (Context Propagation)**：利用 Python `contextvars` 机制，在多线程与流水线各子任务间实现隐式链路透传，避免污染现有多智能体节点签名。

---

## 2. 核心架构与模块划分

```text
src/core/tracer/
  ├── __init__.py           # 导出 AgentTracer, TracerContext
  ├── context.py            # ContextVar 线程安全上下文栈管理
  ├── schema.py             # Pydantic V2 契约 (TraceRecord, SpanRecord, LLMCallRecord 等)
  ├── manager.py            # AgentTracer 核心生命周期管理器
  ├── costing.py            # Token 计量与多模型成本换算引擎
  └── exporters/            # 存储与导出器插件包
        ├── __init__.py
        ├── base.py         # BaseTracerExporter 抽象基类
        ├── sqlite.py       # 本地 SQLite 导出器 (data/traces.sqlite3)
        ├── jsonl.py        # 本地 JSON Lines 轮转导出器 (logs/traces/*.jsonl)
        └── langfuse.py     # Langfuse 行业标准导出器 (旁路异步)
```

---

## 3. 关键组件技术细节

### 3.1 上下文穿透 (`context.py`)
使用 `contextvars.ContextVar` 存储当前正在运行的 `TraceContext`。当进入新的 `span()` 时，自动设置当前 Span 为 Active Span，并在退出时自动退栈并计算 Duration。针对工作流的 `ThreadPoolExecutor`，提供 `copy_context().run()` 封装或显式上下文绑定机制。

### 3.2 大模型交互透明拦截 (`src/core/llm.py`)
在 `HelloAgentsLLM.chat` 中包装追踪探针：
- 发起调用前：记录模型名、输入 Messages 快照、超参数、时间戳；
- 收到回复后：提取 `response.usage`（Prompt Tokens, Completion Tokens），记录耗时与原始文本；
- 触发错误时：记录异常类型与错误信息；
- 自动调用敏感信息脱敏器过滤潜在密钥字段。

### 3.3 容错自愈事件捕获
在 `JsonFixer`、Pydantic 重试循环以及反思纠偏节点中，显式调用：
```python
tracer.record_healing_event(
    reason="Pydantic ValidationError on CatalystItem",
    original=malformed_json_str,
    fixed=corrected_json_str
)
```
使得开发者在界面上能直观对比“大模型第一次输出的畸变数据”与“修正后的合规数据”。

### 3.4 导出器抽象与调度 (`exporters/`)
- 主线程研判完成后，`tracer.end_trace()` 会将聚合好的 `TraceSummary` 对象分发至已注册的 Exporter 列表中；
- `SQLiteExporter`：基于轻量单连接或线程池写入，具备 `WAL` 模式开启以支持高并发读写；
- `JsonlExporter`：按日将完整 Trace 树追加落盘，格式紧凑，便于日志收集分析；
- `LangfuseExporter`：检查环境配置，若激活则将 Trace 映射并推送到远程监控服务端。

---

## 4. 自审检查清单 (Self-Review Checklist)

- [x] **无占位符 (No Placeholders)**：无 TBD 或待定内容，全流程技术方案均有明确定义。
- [x] **内部一致性 (Consistency)**：数据契约与主 PRD 完全保持一致（统一采用 Pydantic V2 强类型约束）。
- [x] **范围清晰 (Scope Check)**：紧扣“开发者与算法调试为主的可观测性”需求，不膨胀无关功能。
- [x] **无歧义性 (Ambiguity Free)**：对多线程上下文传递、失败降级、Token 计费均有明确策略。
