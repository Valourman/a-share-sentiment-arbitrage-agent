# Agent 全链路日志与可观测性审计追踪系统需求规格说明书 (PRD)

| 文档版本 | 发布日期 | 状态 | 编写人 | 核心评审者 |
| :--- | :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-10-04 | 待评审 (Draft) | AI 架构小组 | 研发团队 / 算法团队 |

---

## 1. 文档概述

### 1.1 背景与现状
当前 **A-Share Sentiment Arbitrage Agent** 已具备端到端多源研判（股吧消歧、基本面催化提取、多空对抗辩论、盘面终审仲裁）的核心流水线能力。但在实际研发调试、模型选型对比以及 Bad Case 排查过程中，面临以下工程痛点：

1. **调用过程黑盒化**：`HelloAgentsLLM.chat` 仅返回最终文本结果，中间发出的完整 Messages（System Prompt、few-shot 样本、动态注入的资讯）及原始响应未被结构化沉淀；
2. **Token 与成本计量粗糙**：当前仅能统计端到端的大致耗时，缺乏针对每个节点、每个智能体角色的 Token（Prompt Tokens / Completion Tokens）精确统计，难以进行成本精细化核算；
3. **自愈与重试过程不可视**：当大模型输出不符合 Pydantic 规范触发结构化纠偏、或触发反思自愈重试时，缺乏对“重试前脏输出”与“重试后修正输出”的对比记录，排查 Prompt 缺陷成本高；
4. **日志割裂且缺乏行业生态兼容**：前端仅显示格式化字符串流水，难以进行自动化回溯，也无法无缝接入工业界标准的 LLM 可观测性系统（如 Langfuse、OpenTelemetry 等）。

### 1.2 建设目标
构建一套**轻量开箱即用、本地无外部依赖运行、同时全面兼容 OpenTelemetry 与 Langfuse 行业规范**的 Agent 全链路日志与可观测性审计系统。
- **开箱即用**：开发与测试环境下，通过本地 SQLite 与 JSONL 零配置落盘，提供极低的接入成本；
- **调试友好**：前端 Streamlit 提供专属“链路追踪与调试看板”，支持按标的代码、执行状态、耗时瀑布流可视化定位性能瓶颈与异常节点；
- **标准开放**：核心数据结构对齐 OpenTelemetry GenAI 规范与 Langfuse 数据模型，提供标准 Exporter 插件体系，支持未来无感接入 APM 服务。

### 1.3 适用受众
- **算法工程师 / 开发者**：用于调试 Prompt、分析 Token 开销、重现并修复 Bad Case；
- **测试与 QA**：用于流水线端到端回归测试用例导出、稳定性和时延压测指标收集；
- **量化策略研究员**：用于审计智能体对抗推导链与最终诱多仲裁结论的推导一致性。

---

## 2. 核心概念与数据实体模型

系统建立树状层次追踪模型，遵循标准分布式链路追踪语义：

```text
Trace (一次完整的标的研判会话 / Run)
  ├── Span (阶段级: Phase 1 并发感知流)
  │     ├── Span (工具级: 股吧抓取)
  │     └── Span (工具级: L1 行情快照)
  ├── Span (阶段级: Phase 2 情绪消歧与反讽穿透)
  │     ├── LLM Call (大模型推理: 帖子 #1 消歧分类)
  │     └── LLM Call (大模型推理: 帖子 #2 消歧分类)
  ├── Span (阶段级: Phase 4 多空对抗辩论)
  │     ├── LLM Call (多头研究员立论)
  │     └── LLM Call (空头研究员质询)
  └── Span (阶段级: Phase 5 盘面终审与背离仲裁)
        └── Event (结构化解析异常与自愈纠偏)
```

### 2.1 实体术语定义

1. **Trace（追踪全流程）**：一次完整的研判请求，拥有全局唯一的 `trace_id`，记录标的代码、引擎模式、整体耗时、状态与汇总指标。
2. **Span（执行跨度）**：Trace 树上的分支节点，表示一个有明确生命周期的执行单元（如阶段 `phase`、智能体执行 `agent_step`、工具调用 `tool`）。
3. **LLM Generation / Call（模型生成调用）**：专属的叶子节点，记录单次请求大模型的模型名、温度、System Prompt、输入消息列表、输出内容、Token 用量、首字延迟（TTFT）与总耗时。
4. **Self-Healing Event（自愈事件）**：模型输出格式破坏、API 超时或工具异常时触发的自愈决策事件，记录错误特征、修复动作及重试前后对比。

---

## 3. 功能需求详细说明 (FR)

### FR-1: 线程/协程安全的分层上下文管理 (ContextVar)
- **需求描述**：在流水线并发和多线程/异步场景下，追踪器必须能够自动继承当前上下文层级，无需在所有底层业务方法中手动传递追踪实例。
- **验收标准**：
  1. 基于 Python 标准库 `contextvars.ContextVar` 维护当前活跃的 `trace_id` 与父 `span_id` 堆栈；
  2. 支持使用上下文管理器 `with tracer.span(name="...", span_type="...") as s:` 自动建立父子级联关系；
  3. 当并发节点（如 `ThreadPoolExecutor` 并发抓取股吧与行情）执行时，支持通过上下文传播（Context Propagation）自动绑定到主 Trace。

### FR-2: LLM 网关原生拦截与消息快照 (HelloAgentsLLM 集成)
- **需求描述**：在 `HelloAgentsLLM.chat` 与 `stream_chat` 内部原生集成追踪探针，捕获全部入参出参。
- **验收标准**：
  1. **输入快照**：自动序列化记录请求的消息列表（含 `role: system`、`role: user`、`role: assistant`）、温度参数、模型版本；
  2. **输出快照**：自动记录模型生成的原始文本；若包含 Function Call / Tool Call，记录所选工具名与生成入参；
  3. **耗时度量**：精准记录请求发起时间戳、首字返回时间戳（流式场景）、结束时间戳，计算精确毫秒级耗时；
  4. **异常捕获**：当 API 抛出超时、认证错误、频控限制（429）或内容风控拦截时，捕获异常堆栈并标记调用状态为 `FAILED`。

### FR-3: 细粒度 Token 计量与成本核算体系
- **需求描述**：对所有模型交互进行精确的消耗统计，支持根据模型类型估算财务成本。
- **验收标准**：
  1. 优先提取 OpenAI API 返回的 `response.usage`（`prompt_tokens`, `completion_tokens`, `total_tokens`）；
  2. 在无法直接获取 API Usage 的降级或本地模型场景下，内置基于字符与分词规则的估算保底（Fallback Tokenizer）；
  3. 支持配置主流模型价格字典（如 DeepSeek-V3、GPT-4o、Qwen 等的输入/输出百万元单价），在 Trace 汇总中实时核算单次研判总金额（CNY / USD）。

### FR-4: 异常容错与自愈链路可观测 (Self-Healing Tracing)
- **需求描述**：记录模型生成非预期输出时系统的自愈纠偏过程，为 Prompt 优化提供依据。
- **验收标准**：
  1. 当 Pydantic 解析失败触发 `JsonFixer` 或重试提示词时，显式记录 `LLMHealingEvent`；
  2. 记录项包含：原始报错信息、第一次生成之畸变文本、重试所追加的纠偏 Prompt、第二次修正文本及最终解析判定；
  3. 支持统计各业务节点（情绪消歧、催化提取、多空辩论）的自愈触发率。

### FR-5: 双模存储与导出架构 (Dual-Mode Exporter)
系统设计分层解耦的存储抽象 `TracerExporter`：

```text
                ┌───────────────────────────────────┐
                │        AgentTracer Engine         │
                └─────────────────┬─────────────────┘
                                  │ 触发落盘 / 导出
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
       ┌───────────────────────┐     ┌───────────────────────┐
       │   本地开箱即用导出器   │     │   行业标准兼容导出器  │
       ├───────────────────────┤     ├───────────────────────┤
       │ • SQLiteExporter      │     │ • LangfuseExporter    │
       │ • JsonlExporter       │     │ • OpenTelemetryExporter│
       └───────────────────────┘     └───────────────────────┘
```

#### 5.1 本地存储规范（默认启用）
- **SQLite 存储**：保存在 `data/traces.sqlite3`，建立两张核心表：
  - `agent_traces`：存储 Trace 级元数据（`trace_id`, `stock_code`, `status`, `start_time`, `duration`, `total_tokens`, `total_cost`, `summary_json`）；
  - `agent_spans`：存储细粒度节点（`span_id`, `trace_id`, `parent_id`, `name`, `span_type`, `inputs_json`, `outputs_json`, `tokens`, `duration`, `error`）。
- **JSONL 归档**：按日期保存在 `logs/traces/trace-YYYY-MM-DD.jsonl`，每行一个完整 Trace 树的 JSON 序列化对象，方便日志采集工具（Filebeat / Promtail / Fluentd）收集。

#### 5.2 行业标准兼容规范（可选配置）
- **Langfuse 兼容**：当环境变量中检测到 `LANGFUSE_PUBLIC_KEY` 与 `LANGFUSE_SECRET_KEY` 时自动激活，映射 Trace、Span 与 Generation 契约，支持旁路异步推送，不阻塞核心逻辑；
- **OpenTelemetry (OTel) 兼容**：输出对齐 OpenTelemetry Semantic Conventions for Generative AI systems（如 `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens` 等）。

### FR-6: 开发者交互与调试看板 (Streamlit 集成)
在现有 `app.py` 界面开辟专属“可观测性与追踪控制台”扩展面板：
1. **甘特瀑布图 (Waterfall Chart)**：直观展现 5 个阶段与各个工具调用、LLM 调用的起止时序与耗时重叠情况；
2. **LLM 入参/出参一键展开**：点击任一生成节点，支持左右分栏或标签页查看完整的 Prompt（支持高亮渲染）与生成的原始内容；
3. **Bad Case 调试导出**：支持一键导出当前 Trace 为标准 Python 单元测试脚本格式，或导出为可直接使用的 cURL 测试用例。

### FR-7: 安全防御与敏感脱敏策略
- **需求描述**：防止开发者密钥或用户隐私在日志沉淀过程中泄漏。
- **验收标准**：
  1. 所有入参/环境变量中的敏感字段（如 `api_key`, `authorization`, `password`, `token`）在落盘前强制执行正则表达式脱敏（替换为 `sk-***`）；
  2. 针对超大文本（如公告原始几十页正文），支持设置最大捕获字符上限（默认 4KB），超长字段自动截断并保留 `[TRUNCATED: original length N]` 标记，防止日志膨胀。

---

## 4. 非功能性需求 (NFR)

### 4.1 性能与开销约束
- **延迟影响**：在开启全量本地 SQLite / JSONL 追踪模式下，增加的端到端 CPU 耗时开销不得超过总时延的 **3%**；
- **I/O 策略**：本地文件追加与网络上报应采用批量缓冲区（Buffer Flush）或独立后台守护线程，严禁因网络抖动阻断研判主线程。

### 4.2 可靠性与熔断降级 (Fail-Safe)
- **静默容错**：追踪器内部产生的任何异常（包括数据库锁死、磁盘占满、网络异常），必须在内部捕获并记录标准 Python Warning，**严禁向上传播中断研判主工作流**。

### 4.3 存储生命周期管理
- 提供内建清理脚本或配置项 `TRACE_RETENTION_DAYS`（默认保留 30 天）；
- 单个 Trace 序列化后的平均体积控制在 50KB ~ 200KB 之间。

---

## 5. 数据模型设计 (Pydantic V2 契约)

```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SpanType(str, Enum):
    PHASE = "phase"
    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    EVENT = "event"


class SpanStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_cny: float = 0.0


class LLMGenerationDetail(BaseModel):
    model: str
    temperature: float = 0.7
    system_prompt: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    raw_response: str = ""
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: Optional[str] = None


class TraceSpanRecord(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    span_type: SpanType
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    status: SpanStatus = SpanStatus.RUNNING
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Any] = None
    llm_detail: Optional[LLMGenerationDetail] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None


class TraceSummary(BaseModel):
    trace_id: str
    stock_code: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    status: SpanStatus = SpanStatus.RUNNING
    total_spans: int = 0
    total_llm_calls: int = 0
    total_tokens: TokenUsage = Field(default_factory=TokenUsage)
    has_self_healing: bool = False
    error_count: int = 0
    spans: List[TraceSpanRecord] = Field(default_factory=list)
```

---

## 6. 接口规范 (API Specification)

### 6.1 核心追踪上下文 API

```python
class AgentTracer:
    """全局/单次会话追踪器核心入口"""

    def start_trace(self, stock_code: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """开启一条根追踪链路，返回 trace_id，并绑定到当前线程 ContextVar"""

    def end_trace(self, status: SpanStatus = SpanStatus.SUCCESS) -> TraceSummary:
        """结束当前追踪链路，触发全部 Exporter 持久化并返回聚合汇总指标"""

    def span(self, name: str, span_type: SpanType, inputs: Optional[Dict[str, Any]] = None):
        """上下文管理器，创建并管理当前 Span 的生命周期"""

    def record_llm_call(self, span_id: str, detail: LLMGenerationDetail) -> None:
        """记录底层 LLM 的完整输入输出及用量细节"""

    def record_healing_event(self, reason: str, original: str, fixed: str) -> None:
        """记录格式自愈与纠偏事件"""
```

### 6.2 导出器插件接口 (TracerExporter Interface)

```python
from abc import ABC, abstractmethod

class BaseTracerExporter(ABC):
    @abstractmethod
    def export(self, trace_summary: TraceSummary) -> bool:
        """将完整的 Trace 数据导出至目标存储端，返回是否导出成功"""

    @abstractmethod
    def shutdown(self) -> None:
        """释放资源、刷新残留缓冲区"""
```

---

## 7. 实施路线与里程碑规划

| 阶段 | 核心目标 | 交付物 | 预计耗时 |
| :--- | :--- | :--- | :--- |
| **M1: 核心契约与上下文引擎** | 升级 `src/core/tracer.py`，实现 `contextvars` 树状层级模型与 Pydantic V2 契约 | 单元测试覆盖率 > 90% 的新 Tracer 核心 | 1-2 天 |
| **M2: LLM 网关原生拦截与计量** | 在 `HelloAgentsLLM` 中嵌入透明拦截探针，支持 Token 自动统计与脱敏 | 支持捕获全部 Prompt / Completion / Token | 1 天 |
| **M3: 本地持久化与双模导出器** | 实现 `SQLiteExporter`、`JsonlExporter` 及标准 `LangfuseExporter` 接口骨架 | 自动化测试验证本地读写与多环境兼容 | 2 天 |
| **M4: 工作流节点集成与自愈记录** | 在 `FinancialWorkflowPipeline` 的 5 大节点与容错自愈模块中注入追踪 | 端到端真实运行生成完整的链路追踪记录 | 1-2 天 |
| **M5: Streamlit 前端调试看板** | 在界面中实现耗时瀑布流展示、LLM 入参/出参抽屉、Bad Case 调试导出 | 可视化交互控制台 | 2 天 |

---

## 8. 验收标准 (Definition of Done)

1. **测试覆盖**：
   - 新增代码单元测试覆盖率不低于 **85%**；
   - 包含并发追踪、跨线程上下文传递、异常降级拦截等核心边界用例。
2. **零阻断验证**：
   - 模拟本地磁盘无写权限或 Langfuse 密钥失效，工作流研判流水线必须正常出具分析报告，不受日志系统异常影响。
3. **数据完整性验证**：
   - 每次完整研判后，本地 SQLite 数据库中能精准查询到对应的 Trace、全部 5 个阶段的 Span，以及至少 4 次以上 LLM 调用的完整 Prompt、原始 Response 与 Token 消耗。
4. **代码与规范同步**：
   - 遵循 PEP 8 与 Ruff 规范，无静态检查告警；
   - 同步更新系统配置说明与环境依赖文档。
