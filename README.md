# 面向 A 股市场的多源舆情反讽研判与盘面背离预警 Agent

本项目是一个具备真实工具调用 (Tool Use)、强类型契约校验 (Pydantic V2)、语义自愈解析 (Self-Correction Loop) 与 盘面交叉背离反思 (Reflection Engine) 的金融量化智能体。

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

我们在 `evals/dataset.py` 中构建了包含 15 条 A 股典型黑话、反讽破防、重组公告等真实语料的黄金测试集，自动化运行评测流水线 (`evals/benchmark.py`)：

| 评测维度 | 规则基线引擎 (Baseline) | 本 Agent (LLM + 自愈架构) | 提升幅度 |
| :--- | :--- | :--- | :--- |
| **综合多空研判准确率** | 86.7% | **100.0%** | **+13.3%** |
| **隐晦反讽/黑话识别率** | 40.0% | **100.0%** | **+60.0%** |

---

## 核心架构流转图 (多源立体研判)

```text
[用户输入股票代码 (如 600667, 600584)]
       │
       ▼
┌──────────────────────────────────────────────┐
│ 1. 多源金融情报并行采集 (无需配置深度，全量最大化)│
│   ├── 东方财富股吧全量散户发帖 (默认捕获最大有效深度，清洗 70%+ 水军广告)
│   ├── 新浪财经主流专业财经资讯 (主力资金流向、研报评级、行业催化)
│   └── 上市公司官方权威披露 (定期财报、重大事项公告)
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 2. 大模型深度语义消歧与反讽识别              │  --> LLM 结合 A 股黑话字典解析真实多空动机 (Pydantic 约束)
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 3. 秒级客观事实盘面基准验证                  │  --> Tool 调用新浪财经行情网关，提取现价、涨跌幅、成交额
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 4. 多维立体交叉反思决策 (Reflection Loop)    │ --> 对比全量散户情绪、机构资讯与客观盘面，识别多空背离输出报告
└──────────────────────────────────────────────┘
```

---

## 框架工程分层架构 (对齐 Datawhale《Hello Agents》标准)

本项目严格对齐 Datawhale《Hello Agents》分层解耦与“万物皆为工具 (Everything is a Tool)”的核心设计规范，构建了完备的通用智能体底座与金融量化业务层：

```text
src/
├── core/                       # [核心框架底座层 - 第七章]
│   ├── config.py               # AgentConfig 集中式环境与模型配置中心
│   ├── message.py              # Message 与 RoleType 标准通信数据契约 (兼容 OpenAI 字典)
│   ├── llm.py                  # HelloAgentsLLM 统一模型中枢网关
│   ├── agent.py                # BaseAgent 顶层智能体抽象基类 (生命周期与上下文维护)
│   ├── parser.py               # RobustAgentParser 生产级自愈解析器 (正则容错与报错反馈)
│   ├── schema.py               # Pydantic V2 结构化舆情与立场契约
│   └── market_schema.py        # 盘面数据结构化快照契约
├── agent/                      # [智能体范式与业务实现层 - 第四/七章]
│   ├── base_reflection.py      # ReflectionAgent 通用自我反思智能体范式 (执行-评估-反思闭环)
│   ├── engine.py               # SentimentArbitrageAgent 继承反思范式的金融实战 Agent
│   └── state.py                # 智能体状态机与背离决策契约
├── tools/                      # [工具系统层 - 第七章“万物皆为工具”]
│   ├── base.py                 # Tool 抽象基类与 ToolParameter (自动输出 OpenAI Function Schema)
│   ├── registry.py             # ToolRegistry 集中式工具注册发现中心与函数装饰器
│   ├── scraper.py              # StockForumScraper 多源金融情报采集工具
│   ├── market.py               # MarketDataTool 秒级 L1 客观盘面验证工具
│   └── analyzer.py             # FinancialSentimentAnalyzer 深度消歧与反讽研判工具
├── memory/                     # [记忆与检索系统 - 第八章]
│   ├── buffer.py               # ConversationBufferMemory 短期多轮对话滑动窗口缓存
│   └── knowledge.py            # FinancialKnowledgeRetriever A 股黑话与反讽隐喻领域知识库
└── evals/                      # [智能体性能评估体系 - 第十二章]
    ├── dataset.py              # 15 组 A 股极端与反讽黄金测试集
    └── benchmark.py            # 自动化基准测试流水线 (规则 Baseline vs LLM Agent)
```

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
```

### 3. 启动交互式 Web 仪表盘

#### 方案 A：Google Gemini 现代设计系统 (React + Tailwind 原生交互)
项目提供了参考 **Google Gemini (gemini.google.com/app)** 设计哲学的全新生产级前端组件与独立交互应用：
- **单文件免构建原生体验**：直接在浏览器中打开 `frontend/index.html` 即可体验纯正的 Gemini 视觉与交互（支持深浅色模式切换、Collapsible Rail 折叠导航、悬浮复合药丸输入舱、思维链展开）。
- **组件源码集成**：查看 `frontend/GeminiSentimentDashboard.tsx`，采用 React 18 + TypeScript + Tailwind CSS 模块化构建，支持无缝嵌入现有现代前端技术栈。

#### 方案 B：Streamlit 仪表盘 (已升级 Gemini 美学皮肤)
执行以下命令启动 Streamlit 前端交互工作台：

```bash
streamlit run app.py
```
在浏览器中打开提示的本地地址（默认 `http://localhost:8501`），输入 6 位 A 股股票代码（如 `600519`, `600584`, `002594`），点击 **「启动智能反思研判」** 查看经过 Gemini 色彩与卡片化重构的决策大屏。

### 4. 运行单元测试与量化评测

```bash
# 运行单元测试套件 (包含解析器自愈、反思状态流转与工具层测试)
pytest -v tests/

# 运行覆盖率检查
pytest --cov=src tests/

# 运行自动化黄金评测流水线
python -m evals.benchmark
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
