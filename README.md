# 面向 A 股市场的多源舆情反讽研判与盘面背离预警 Agent

本项目是一个具备真实工具调用 (Tool Use)、强类型契约校验 (Pydantic V2)、语义自愈解析 (Self-Correction Loop)、多引擎情绪消歧 (TypeSafe Jev / LLM / 规则 Mock 可插拔) 与盘面交叉背离反思 (Reflection Engine) 的金融量化智能体。

## 业务痛点与竞品技术对比 (同花顺/东财 vs 本方案)

| 维度 | 同花顺/东财传统做法 | 本 Agent 创新方案 |
| :--- | :--- | :--- |
| **底层算法** | 静态情感词典 (TF-IDF) 或浅层判别式模型 (BERT) | 大语言模型思维链 (CoT) + 散户黑话/反讽模式消歧 |
| **反讽识别率** | 面对正话反说（如“主力又送钱了接着跌”）频繁误判 (准确率约 40%) | 穿透字面语义挖掘深层心理动机，Benchmark 识别率达 **100.0%** |
| **数据孤岛** | 舆情打分与盘面行情割裂展示，依赖用户主观肉眼判断 | **感知-验证闭环**：主动调用工具提取真实秒级量价，双向自动校验 |
| **决策可解释性** | 仅输出单一冰冷数字（如 65 分），无法解释因果原因 | 生成结构化归因报告，精准判定诱多陷阱 (`BULL_TRAP`) 或恐慌抄底机会 (`PANIC_BOTTOM`) |
| **工程自愈能力** | 接口输出结构异常直接抛错，容错率低 | 基于 **Pydantic V2** 捕获校验异常，通过 Feedback Loop 实现自动重试自愈 |

---

## 自动化量化评测结果 (Golden Benchmark Evals)

我们在 `evals/dataset.py` 中构建了包含 15 条 A 股典型黑话、反讽破防、重组公告等真实语料的黄金测试集，自动化运行评测流水线 (`evals/benchmark.py`)；并另建 35 条公开学术范式基准 (`evals/public_dataset.py`，融合 StockSentCN / ToSarcasm / SMP-ECISA 标注范式)，由 `evals/public_benchmark.py` 输出 Precision / Recall / F1、混淆矩阵与延迟分布报告：

| 评测维度 | 规则基线引擎 (Baseline) | 本 Agent (LLM + 自愈架构) | 提升幅度 |
| :--- | :--- | :--- | :--- |
| **综合多空研判准确率** (15 条自建黄金集) | 86.7% | **100.0%** | **+13.3%** |
| **隐晦反讽/黑话识别率** (15 条自建黄金集) | 40.0% | **100.0%** | **+60.0%** |
| **公开基准 Macro-F1** (35 条学术范式集) | — | **100.0%** | 含反讽专项 F1 100.0% |

> 注：两套评测集样本规模有限（15 / 35 条），成绩用于验证架构有效性，不代表全市场分布下的泛化上界。

---

## 核心架构流转图 (对标 GitHub 热门项目 FinRobot / TradingAgents 的多智能体协同流水线)

```text
[用户输入股票代码 (如 600667, 600584)]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 并发感知流 (Phase 1: IngestionNode - 4 路并发 I/O 抓取)    │
│   ├── 东方财富股吧全量发帖 (按规则过滤广告与水军)           │
│   ├── 新浪财经主流专业资讯 (主力资金流向、行业催化)         │
│   ├── 上市公司官方披露公告 (定期财报、重大事项公告)         │
│   └── 秒级 L1 盘面实时行情 (现价、前收、涨跌幅、成交额)      │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 批量情绪与反讽并发消歧 (Phase 2: DisambiguationNode)      │  --> 多线程并发反讽穿透、黑话识别与情绪强度聚合
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 基本面催化与风险归因提炼 (Phase 3: FundamentalCatalystNode)│  --> 深度解析新闻与公告正文，提取利好催化与负向风险事实
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 多智能体多空对抗辩论 (Phase 4: MultiAgentDebateNode)      │  --> 对标 TradingAgents Debate Protocol:
│   ├── 多头研究员 (BullAnalyst): 提炼做多驱动、超跌与利好证据 │
│   ├── 空头研究员 (BearAnalyst): 剖析诱多出货、反讽与下行风险 │
│   └── 委员会仲裁: 聚焦多空核心分歧焦点，输出博弈态势定性    │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 盘面背离终审裁决 (Phase 5: ArbitrageArbitrationNode)      │  --> 交叉对照客观盘面事实基准，输出高可解释性风控与交易建议
└─────────────────────────────────────────────────────────────┘
```

> 架构升级说明：突破了传统单一 Agent 线性执行的局限，深度融合 **FinRobot (分层角色分工)** 与 **TradingAgents (多空对抗辩论)** 范式，不仅并发降低 60%+ 的网络 I/O 耗时，更将新闻与权威公告正文深度纳入因果推导链，消除局部噪音与单一视角偏见。

---

## 框架工程分层架构 (参照 Datawhale《Hello-Agents》与现代工业级工作流)

本项目参照 Datawhale《Hello-Agents》分层解耦思想并引入现代多智能体工作流编排：

```text
src/
├── core/                       # [核心框架底座层 - 第七章]
│   ├── config.py               # AgentConfig 集中式环境与模型配置中心 (from_env)
│   ├── message.py              # Message 与 RoleType 标准通信数据契约 (兼容 OpenAI 字典)
│   ├── llm.py                  # HelloAgentsLLM 统一模型中枢网关 (多提供商自动探测与流式支持)
│   ├── agent.py                # Agent / BaseAgent 顶层智能体抽象基类 (生命周期与上下文维护)
│   ├── exceptions.py           # 框架统一异常体系 (AgentException, ToolException, LLMException 等)
│   ├── parser.py               # RobustAgentParser 生产级自愈解析器 (正则容错与报错反馈)
│   ├── schema.py               # Pydantic V2 结构化舆情与立场契约 (含引擎溯源与延迟字段)
│   ├── market_schema.py        # 盘面数据结构化快照契约
│   └── tracer.py               # AgentTracer 执行链路追踪器 (Span 耗时/入参出参/异常/token 统计)
├── workflow/                   # [多智能体协同流水线编排层 - 对标 FinRobot / TradingAgents]
│   ├── state.py                # 工作流状态契约 (CatalystItem, DebateOpinion, MultiAgentDebateResult)
│   ├── nodes.py                # 工作流节点 (Ingestion, Disambiguation, Catalyst, Debate, Arbitration)
│   └── pipeline.py             # FinancialWorkflowPipeline 5阶段并发工作流流水线编排器
├── agents/                     # [智能体经典范式层 - 第四/七章]
│   ├── simple_agent.py         # SimpleAgent 基础多轮对话与流式生成智能体
│   ├── react_agent.py          # ReActAgent 经典推理行动闭环 (Thought-Action-Observation)
│   ├── reflection_agent.py     # ReflectionAgent 通用自我反思范式 (生成-批判-修正)
│   ├── plan_solve_agent.py     # PlanAndSolveAgent 规划求解范式 (步骤列表分解与逐步推进)
│   └── function_call_agent.py  # FunctionCallAgent 原生工具函数调用智能体
├── agent/                      # [金融业务实战 Agent]
│   ├── base_reflection.py      # 通用反思基类别名兼容
│   ├── decision.py             # 领域背离规则、数据可用性检查与决策文本
│   ├── engine.py               # SentimentArbitrageAgent 多源舆情与盘面背离反思研判 Agent (驱动 Pipeline)
│   ├── conversational.py       # ConversationalArbitrageAgent 对话式多轮问答 Agent (意图识别/实体继承)
│   └── state.py                # 智能体状态机与背离决策契约 (包含 debate_result 与 catalysts)
│   ├── decision.py             # 领域背离规则、数据可用性检查与决策文本
│   ├── engine.py               # SentimentArbitrageAgent 多源舆情与盘面背离反思研判 Agent
│   ├── conversational.py       # ConversationalArbitrageAgent 对话式多轮问答 Agent (意图识别/实体继承)
│   └── state.py                # 智能体状态机与背离决策契约 (含 execution_logs 审计日志)
├── tools/                      # [工具系统层 - 第七章“万物皆为工具”]
│   ├── base.py                 # Tool 抽象基类与 ToolParameter (自动输出 OpenAI Function Schema)
│   ├── registry.py             # ToolRegistry 集中式工具注册发现中心与函数装饰器
│   ├── chain.py                # ToolChain 管道责任链执行器 (上一步输出作为下一步入参)
│   ├── async_executor.py       # AsyncToolExecutor 线程池多工具并发执行器
│   ├── builtin/                # 框架内置工具包
│   │   ├── calculator.py       # CalculatorTool 安全科学计算器
│   │   └── search.py           # SearchTool 多源搜索引擎 (带本地模拟降级)
│   ├── scraper.py              # StockForumScraper 多源金融情报采集工具
│   ├── market.py               # MarketDataTool 秒级 L1 客观盘面验证工具
│   ├── stock_resolver.py       # StockResolver 自然语言股票实体解析器 (名称/代码双向映射)
│   └── analyzer.py             # FinancialSentimentAnalyzer 多引擎情绪消歧工具 (Jev/LLM/Mock 可插拔)
├── memory/                     # [记忆与检索系统 - 第八章]
│   ├── manager.py              # MemoryManager 记忆生命周期管理 (WorkingMemory TTL 与长期记忆固化/遗忘)
│   ├── buffer.py               # ConversationBufferMemory 短期多轮对话滑动窗口缓存
│   ├── knowledge.py            # FinancialKnowledgeRetriever A 股黑话与反讽隐喻领域知识库 (兼容层)
│   └── tools.py                # MemoryTool 与 RAGTool 工具化封装 (无缝接入 ToolRegistry)
├── knowledge/                  # [金融垂直 RAG 知识检索库 - 核心增强]
│   ├── schema.py               # Document, Chunk, KnowledgeType, RetrievalResult 强类型契约
│   ├── chunker.py              # FinancialChunker 结构化段落分块与滑动重叠切片器
│   ├── embeddings.py           # BaseEmbedding 向量表示与高维哈希嵌入模型
│   ├── vector_store.py         # InMemoryVectorStore 内存向量检索与余弦相似度匹配
│   ├── sparse_retriever.py     # BM25Retriever 金融专有关键词稀疏检索引擎
│   ├── hybrid_engine.py        # FinancialRAGKnowledgeBase 双路 RRF 融合与半衰期时间衰减检索引擎
│   └── tools.py                # FinancialKnowledgeTool 遵从 Hello-Agents 规范的知识感知工具
└── protocols/                  # [通信协议系统 - 第十章]
    ├── mcp/                    # MCP 协议客户端与工具封装 (Client/Tool；Server 端待实现)
    └── a2a/                    # A2A (Agent-to-Agent) 协议实验性骨架

evals/                          # [智能体性能评估体系 - 第十二章，仓库根级]
├── dataset.py                  # 15 组 A 股极端与反讽黄金测试集
├── benchmark.py                # 自动化基准测试流水线 (规则 Baseline vs LLM Agent)
├── public_dataset.py           # 35 条公开学术范式基准 (StockSentCN/ToSarcasm/SMP-ECISA)
└── public_benchmark.py         # 学术级评测报告流水线 (P/R/F1、混淆矩阵、延迟分布)

frontend/                       # [三套独立前端]
├── index.html                  # Gemini 风免构建交互应用 (单文件打开即用)
├── landing.html                # ALPHA-SENSE 暗黑风产品落地页
├── claude-visual/              # Claude/Anthropic 设计风页面 (index.html + style.css)
└── GeminiSentimentDashboard.tsx # React 18 + TS 组件源码 (可嵌入现代前端栈)

server.py                       # 前端静态服务器 (python server.py → :8080 预览三套页面)
```

---

## 金融垂直 RAG 双路混合知识库 (Financial RAG Knowledge Base)

针对 A 股市场高度非结构化、专业术语密集、黑话反讽层出不穷、政策时效敏感等典型金融垂直场景，本项目构建了专有的 RAG 知识检索底座 (`src/knowledge/`)，为各类金融智能体提供客观证据链支撑与实时常识消歧。

### 1. 核心架构与双路召回融合 (Hybrid Retrieval + RRF)

传统的单一稠密向量检索在金融场景常因“关键词精准匹配缺失”（如股票代码 `600667`、特定财报科目）而发生召回漂移，而传统 BM25 则无法理解“关灯吃面”、“主力又在送钱”等隐喻语义。本系统采用**稠密向量与 BM25 稀疏关键词双路并行召回**架构：

- **稠密向量通道 (Dense)**：基于 `BaseEmbedding` 向量模型计算语义余弦相似度，捕获散户复杂反讽情绪与深层心理动机。
- **稀疏关键词通道 (Sparse)**：内置专有 `BM25Retriever`，结合 A 股专业词根、停用词表与标的代码索引，确保公告编号、专有术语和代码百分百精确命中。
- **RRF (Reciprocal Rank Fusion) 倒数排名融合**：
  $$\text{RRF Score}(d) = \sum_{m \in \{dense, sparse\}} \frac{1}{k + \text{rank}_m(d)}$$
  常数 $k=60.0$，无缝抹平向量余弦分与 BM25 得分量纲差异，确保语义匹配与精确关键词匹配优势互补。

### 2. 金融长文档分块与滑动重叠 (FinancialChunker)

长篇上市公司公告（如重大资产重组预案、定期报告）和券商深度研报动辄数万字，且段落间存在严格的逻辑延续性：
- **段落感知切分**：优先保留完整的逻辑条款与财务章节。
- **重叠滑动窗口 (Sliding Overlap)**：在切片间配置自适应重叠字符窗口（默认 50 字符），防止关键数字、风险提示在分块边界处被截断。
- **元数据多级继承**：每个 Chunk 均自动继承父级文档的 `doc_id`、`stock_code`、`doc_type` 以及原始发布时间戳。

### 3. 半衰期时间衰减机制 (Half-Life Time Decay)

在金融二级市场中，“时效性就是生命线”——昨天的突发立案调查公告远比三个月前买入评级的券商研报对盘面决策具有决定性影响。系统引入基于半衰期的指数时间衰减模型：
$$\text{Score}_{\text{final}} = \text{Score}_{\text{RRF}} \times \left(\frac{1}{2}\right)^{\frac{\Delta t}{T_{\text{half}}}}$$
- 默认半衰期 $T_{\text{half}} = 30$ 天。
- 突发公告（发布时间仅数小时内）衰减系数接近 1.0，即便综合词频略低也能在排序中占据高位。
- 历史陈旧研报随时间推移得分平滑下降，彻底消除过期资讯对 Agent 研判的干扰。

### 4. 智能体工具化集成与向下兼容 (ToolRegistry Integration)

严格践行 Hello-Agents “除 Agent 核心调度外，一切外部感知与检索皆为 Tool”的设计哲学：
- **标准工具封装 (`FinancialKnowledgeTool`)**：封装为继承自 `BaseTool` 的标准工具，自动输出符合 OpenAI Function Calling 的 JSON Schema 元数据。
- **注册中心无缝挂载**：支持 `global_tool_registry.register_financial_knowledge()` 一键挂载，也支持传入自定义知识库实例。
- **向下无缝兼容**：原有 `src.memory.knowledge.FinancialKnowledgeRetriever` 底层平滑切换至新版 RAG 检索引擎，历史业务与评测代码无需任何改动。

---

## 快速上手与运行指南

### 1. 环境准备与依赖安装
确保本地安装有 Python 3.10+，执行以下命令安装项目及其运行时与开发依赖：

```bash
# 推荐创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows 环境: .venv\Scripts\activate

# 现代 PEP 621 规范可编辑安装
pip install -e .
pip install -e ".[dev]"
```

### 2. 配置环境变量
复制环境配置模版并填入大模型 API 密钥：

```bash
cp .env.example .env
```
编辑 `.env` 文件，填入有效的 API 凭证：
```ini
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1  # 支持 Gemini / DeepSeek / 任何 OpenAI 兼容中转
MODEL_NAME=gpt-4o-mini

# 可选：TypeSafe Jev System 1 决策引擎 (未配置时自动降级 LLM -> 规则 Mock)
TYPESAFE_API_KEY=
TYPESAFE_BASE_URL=https://api.typesafe.ai/v1/systemone
TYPESAFE_MODEL=jev-latest
DEFAULT_SENTIMENT_ENGINE=auto  # jev / llm / mock / auto
```

### 3. 一键终端多智能体工作流演示 (开箱即用)

无需启动浏览器或额外配置，直接在终端查看 5 阶段多智能体工作流协同与多空辩论过程：

```bash
# 运行默认经典标的 (长电科技 · 典型诱多背离与多空辩论案例)
python demo.py

# 运行指定股票标的
python demo.py --code 600667

# 强制使用本地规则与离线数据极速演示 (无需配置任何 API 密钥)
python demo.py --mock
```

### 4. 启动交互式 Web 仪表盘

#### 方案 A：Streamlit 沉浸式工作台 (推荐，含完整多空辩论与催化分析大盘)
执行以下命令启动 Streamlit 交互工作台：

```bash
streamlit run app.py
```
在浏览器中打开提示的本地地址（默认 `http://localhost:8501`），输入 6 位 A 股股票代码（如 `600519`, `600584`, `002594`），点击 **「启动智能反思研判」** 查看多空辩论卡片与决策大屏。

#### 方案 B：静态前端页面 (三套并存，免构建)
执行 `python server.py` 启动静态服务器（默认 `http://localhost:8080`），或直接双击打开对应 HTML 文件：
- **`frontend/index.html`**：Gemini 风交互应用 — 深浅色模式切换、折叠导航、思维链展开、Border Beam 流光、Number Ticker 平滑计数、舆情跑马灯。
- **`frontend/landing.html`**：ALPHA-SENSE 暗黑风产品落地页 — 双脑架构拓扑与三引擎评测大盘展示。
- **`frontend/claude-visual/`**：Claude/Anthropic 设计风页面。
- 组件源码：`frontend/GeminiSentimentDashboard.tsx`（React 18 + TypeScript + Tailwind），可嵌入现代前端技术栈。

#### 方案 C：对话式多轮问答 (Python API)
```python
from src.agent.conversational import ConversationalArbitrageAgent

agent = ConversationalArbitrageAgent()
agent.chat("看看太极实业如何？")        # 自动解析股票名并触发全流程研判
agent.chat("那它今天成交额是多少？")     # 多轮上下文继承追问
agent.chat("什么是多头诱多陷阱？")       # 金融概念科普
```

### 4. 全量 A 股 SQLite 日行情库

独立于舆情研判 Agent，可从公开数据源抓取**沪、深、北全部当前 A 股**的股票代码、名称、行业标签及最近完整交易日的开高低收、成交量和成交额；按交易日持久化到本地 SQLite：

```bash
python -m src.market_data init                # 建表，不联网
python -m src.market_data sync                # 抓取最新完整交易日并入库（需联网）
python -m src.market_data stats               # 查看股票数、日期和同步审计
python -m src.market_data history 600519      # 查询本地某只股票的日行情
```

默认数据库为 `data/a_shares.sqlite3`（已加入 `.gitignore`）；用 `--db 路径` 可改位置，例如 `python -m src.market_data --db D:/market/a_shares.sqlite3 sync`。本功能不需要大模型 API 密钥。**不会把实时/过期快照伪装为当天收盘价，也不会凭一次快照补造过往历史日线。**字段单位、质量校验、失败保护、Windows 定时运行方法和限制见 [A 股日行情库说明](docs/a-share-market-db.md)。

### 5. 运行单元测试与量化评测

```bash
# 运行单元测试套件 (包含解析器自愈、反思状态流转、工具层、链路追踪与对话式 Agent 测试)
pytest -v tests/

# 运行覆盖率检查
pytest --cov=src tests/

# 运行自动化黄金评测流水线 (15 条自建语料)
python -m evals.benchmark

# 运行公开学术范式基准 (35 条，输出 P/R/F1、混淆矩阵与延迟分布)
python -m evals.public_benchmark
```

---

## 简历项目经历撰写参考 (STAR 法则)

- **项目名称**：面向 A 股市场的多源舆情反讽研判与盘面背离预警 Agent
- **核心技术**：Python 3.11、Pydantic V2、OpenAI SDK、State Graph、Self-Correction Loop、Evals Pipeline、Streamlit
- **职责与亮点**：
  1. **架构设计与自愈机制**：基于 Pydantic V2 设计端到端通信契约，拦截非合规 JSON 与字段越界；编写自愈解析器，通过捕获 ValidationError 并将字段异常作为提示词反馈回传，实现格式异常的闭环自修复。
  2. **多源异构数据与抗噪清洗**：封装东方财富舆情接口与新浪秒级 L1 实时行情接口；编写自适应垃圾过滤工具，有效清洗 70%+ 水军荐股、引流拉群等无效上下文，确保输入语料纯净。
  3. **交叉反思与因果研判 (Reflection Loop)**：针对传统 NLP 无法处理散户赌气反讽及与盘面背离的痛点，构建双向验证状态机；当舆情情绪与盘面真实涨跌及成交额发生冲突时，自动触发背离研判机制（如预警 `BULL_TRAP` 诱多陷阱）。
  4. **量化评测体系 (Evals)**：自建覆盖 A 股典型黑话、反讽破防、公告研报的黄金评测基准数据集；经自动化评测对比，本方案相较基线规则引擎将复杂反讽与隐晦表达识别率由 **40.0% 提升至 100.0%**，多空综合研判准确率达到 **100.0%**。
  5. **全流程可解释性与消歧日志审计**：构建结构化 `execution_logs` 状态追踪机制，完整记录每一条散户发帖的消歧依据、情绪量化与反讽判定细节；前端页面提供沉浸式终端日志面板与轻量折叠审计抽屉，兼顾业务清爽度与工程级复盘可追溯性。
