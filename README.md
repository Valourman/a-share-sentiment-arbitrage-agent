<h1 align="center">A-Share Sentiment Arbitrage Agent</h1>

<p align="center">面向 A 股市场的多源舆情反讽研判、因果催化归因与量价背离预警多智能体系统</p>

<p align="center">
  <a href="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python Version" /></a>
  <a href="https://img.shields.io/badge/Contract-Pydantic%20V2-2094f3?style=flat-square"><img src="https://img.shields.io/badge/Contract-Pydantic%20V2-2094f3?style=flat-square" alt="Pydantic V2" /></a>
  <a href="https://valourman.github.io/a-share-sentiment-arbitrage-agent/"><img src="https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-4285F4?style=flat-square" alt="Live Demo" /></a>
  <a href="https://github.com/Valourman/a-share-sentiment-arbitrage-agent"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" /></a>
</p>

本项目是一个针对 A 股市场复杂舆情与盘面波动的金融量化多智能体系统。系统采用生产级工作流流水线（Financial Multi-Agent Workflow Pipeline），贯穿并发异构数据感知、散户反讽与黑话语义穿透、公告与资讯因果催化提炼、多空研究员对抗辩论，以及秒级量价背离终审仲裁，输出结构化的风控决策与交易参考。

## 核心特性

| 特性 | 功能说明与技术实现 |
| :--- | :--- |
| **多源并发感知流 (DataOps)** | 线程池并发采集股吧发帖、主流财经资讯、官方重大披露与秒级 L1 盘面快照，大幅缩减网络 I/O 耗时 |
| **深层反讽与黑话穿透** | 基于大语言模型穿透“主力又送钱了”、“真牛逼天天跌”等隐晦表达，准确识别真实多空立场与心理动机 |
| **公告与基本面因果催化** | 深度解析新闻及上市公司法定披露公告，结构化提取高置信度利好驱动（Catalysts）与负向冲击（Risks） |
| **多空对抗辩论机制 (Debate Protocol)** | 调度多头研究员 (BullAnalyst) 与空头研究员 (BearAnalyst) 围绕量价与基本面论据展开交叉质询，提炼多空分歧焦点与态势 |
| **盘面事实终审与背离预警** | 将多空博弈结论交叉对照客观秒级量价（涨跌幅、换手、成交量），判定诱多陷阱 (`BULL_TRAP`) 或恐慌磨底 (`PANIC_BOTTOM`) |
| **强类型契约与容错自愈** | 基于 Pydantic V2 构建全链路强类型数据契约，具备校验自愈重试与多级引擎路由（LLM / TypeSafe Jev / Mock 规则引擎） |

## 架构设计

系统依据 `src/workflow/pipeline.py` 实现 5 阶段多智能体协作流水线，各节点职责与数据流转如下：

```text
┌────────────────────────────────────────────────────────┐
│ 阶段 1: 并发感知流 (IngestionNode)                       │
│ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐ │
│ │ 股吧散户发帖  │ │ 主流财经资讯  │ │ 上市公司披露   │ │
│ └───────┬───────┘ └───────┬───────┘ └────────┬───────┘ │
│         │                 │                  │         │
│         │    ┌────────────┴───┐              │         │
│         │    │ 秒级 L1 盘面快照│              │         │
│         │    └────────────┬───┘              │         │
└─────────┼─────────────────┼──────────────────┼─────────┘
          │ (帖子语料)       │ (行情基准)        │ (资讯/公告)
          ▼                 │                  ▼
┌──────────────────┐        │     ┌──────────────────────┐
│ 阶段 2: 情绪消歧  │        │     │ 阶段 3: 基本面催化归因 │
│ Disambiguation   │        │     │ FundamentalCatalyst  │
│ (多线程反讽穿透) │        │     │ (利好驱动/负向风险)   │
└─────────┬────────┘        │     └──────────┬───────────┘
          │ (情绪置信度)     │                │ (结构化催化项)
          └────────────┐    │    ┌───────────┘
                       ▼    ▼    ▼
          ┌──────────────────────────────────┐
          │ 阶段 4: 多智能体多空对抗辩论       │
          │ MultiAgentDebateNode             │
          │ ┌──────────────┐ ┌─────────────┐ │
          │ │ 多头研究员   │ │ 空头研究员  │ │
          │ │ BullAnalyst  │ │ BearAnalyst │ │
          │ └──────┬───────┘ └──────┬──────┘ │
          │        └───────┬────────┘        │
          │                ▼                 │
          │      提炼核心分歧焦点与博弈倾向   │
          └────────────────┬─────────────────┘
                           │ (辩论决议 & 分歧焦点)
                           ▼
          ┌──────────────────────────────────┐
          │ 阶段 5: 盘面背离终审仲裁          │
          │ ArbitrageArbitrationNode         │
          │ 交叉比对量价客观事实，输出风控评级 │
          └──────────────────────────────────┘
```

## 使用示例

系统提供离线演示（免 API 密钥）、带大语言模型调度的全功能终端看板以及 Web 交互式大盘三种运行形态。

### 1. 离线快速演示模式 (免配置 API Key)

直接在终端执行：

```bash
python demo.py --mock
```

该命令将在终端加载长电科技（600584）的案例切片，执行 5 阶段工作流并输出彩色控制台看板，包括：
- 帖子情感倾向与反讽判定明细（置信度、反讽标签与深层动机）
- 官方公告与主流资讯提取出的催化项（POSITIVE / NEGATIVE）
- 多头研究员 vs 空头研究员辩论意见与核心分歧焦点
- 最终终审裁决（背离判定、风险等级 `HIGH / MEDIUM / LOW` 与可解释性处置建议）

### 2. 指定标的与真实 LLM 模式

在配置环境变量后，可指定任意 A 股代码进行实时全链路分析：

```bash
python demo.py --code 600667 --posts 20
```

### 3. Web 交互式控制台

启动基于 Streamlit 构建的可视化大盘：

```bash
streamlit run app.py
```

在浏览器中即可获得：实时输入标的代码、查看反讽穿透气泡流、多空辩论实时对垒卡片以及动态背离警报仪表盘。

### 4. 获奖级免构建前端交互终端 (Award-Winning Web UI)

系统内置两套达到 Awwwards / Webby / FWA 获奖级水准的高定零构建前端界面，直接通过 Python 内置服务启动：

```bash
python server.py
```

在浏览器中访问：
- **ALPHA-SENSE 旗舰落地页** (`http://localhost:8080/landing.html`)：
  - **量子引力星云背景**：原生 2D Canvas 物理粒子引力网格，响应窗口与鼠标微动
  - **5 阶段实况推演舱**：动态追踪感知流采集、Jev 反讽消歧、基本面催化、多空辩论与终审仲裁
  - **多空激辩竞技场 (Bull vs Bear Arena)**：多头研究员 vs 空头研究员质询对决与动态博弈力矩
  - **散户反讽穿透光谱 (Sarcasm Spectrum)**：可视化正话反说真实动机与 Noul 概率
  - **黄金基准评测大盘**：15 条真实黄金语料跨三方引擎横向对比
  - **极客微交互**：内置 Web Audio API 原生科技音效合成器与 `[⌘K / Ctrl+K]` 快捷指令
- **Gemini 量子决策大盘** (`http://localhost:8080/index.html`)：
  - 集成 Magic UI 级 `BorderBeam` 边框激光流光、`NumberTicker` 平滑数字翻牌、市场异动双向跑马灯
  - 支持深邃暗夜 (Obsidian Dark) 与冰川极简 (Glacier Light) 双主题切换
  - 提供多智能体思维链推理折叠与结构化交易风控处置指南

## 快速安装

确保系统已安装 Python 3.10 或更高版本：

```bash
git clone https://github.com/Valourman/a-share-sentiment-arbitrage-agent.git
cd a-share-sentiment-arbitrage-agent
python -m venv .venv
```

激活虚拟环境：
- Windows: `.venv\Scripts\activate`
- macOS / Linux: `source .venv/bin/activate`

安装项目依赖：

```bash
pip install -e .
```

## 快速起步

这是验证系统运行状态的最短路径：

1. **环境自检与极速体验（零配置）**：
   ```bash
   python demo.py --mock
   ```
   终端成功输出多空辩论及终审仲裁看板即表示核心工作流运行正常。

2. **配置大模型密钥（在线模式）**：
   复制环境变量模板并填入 OpenAI 或兼容服务的 API 凭证：
   ```bash
   cp .env.example .env
   ```
   编辑 `.env`：
   ```env
   OPENAI_API_KEY=your_actual_api_key
   OPENAI_BASE_URL=https://api.openai.com/v1
   MODEL_NAME=gpt-4o
   ```

3. **运行完整分析流水线**：
   ```bash
   python demo.py --code 600584
   ```

## 环境配置

系统通过 `src/core/config.py` 与 `.env` 文件支持灵活的引擎配置：

| 环境变量 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | 空 | 商业模型调用密钥（支持 OpenAI、DeepSeek、Qwen 等兼容端点） |
| `OPENAI_BASE_URL` | 空 | 兼容模型服务的基础 URL（未设置时使用 OpenAI 官方端点） |
| `MODEL_NAME` | `gpt-4o` | 用于反讽消歧与多空辩论的主模型标识 |
| `TYPESAFE_API_KEY` | 空 | TypeSafe Jev 快思考决策引擎密钥（可选，未设置时自动路由至 LLM 或规则） |
| `DEFAULT_SENTIMENT_ENGINE` | `auto` | 情绪消歧引擎模式：`auto` / `llm` / `mock` |
| `LANGFUSE_PUBLIC_KEY` | 空 | 可观测性跟踪公钥（可选） |

## 自动化量化评测基准

系统内置了两套自动化评估流水线，用于验证语义分析与反讽识别的准确性：

### 1. 真实黄金语料基准 (Golden Benchmark)

位于 `evals/dataset.py`，包含 15 条 A 股典型黑话、反讽破防与重组预期的真实语料：

```bash
python -m evals.benchmark
```

| 评测维度 | 样本规模 | 准确率表现 | 评测说明 |
| :--- | :--- | :--- | :--- |
| **综合多空立场判定 (Stance)** | 15 条 | **100.0%** | 准确识别散户多空预期与分歧态势 |
| **隐晦反讽 / 黑话穿透 (Sarcasm)** | 5 条反讽样本 | **100.0%** | 精准识别正话反说与情绪破防语境 |

> ⚠️ 评测口径说明：以上为 **15 条手工构造样本** 上的结果，部分语料与规则引擎关键词存在重叠（循环验证风险），不能据此推断真实市场语料上的泛化表现。生产使用前建议以真实股吧抽样 + 独立人工标注重建基准。

### 2. 公开学术范式基准 (Public Academic Benchmark)

位于 `evals/public_dataset.py`，融合 StockSentCN / ToSarcasm / SMP-ECISA 范式构建 35 条评估样本：

```bash
python -m evals.public_benchmark
```

流水线输出多分类标准指标（Precision / Recall / Macro-F1 与混淆矩阵），验证模型在学术标注规范下的判别稳定性。

## 常用开发与测试命令

```bash
# 运行全部单元测试
pytest

# 运行覆盖率检查（需先自行安装: pip install pytest-cov）
pytest --cov=src

# 执行代码风格与静态类型检查
ruff check .

# 启动本地免构建前端静态服务 (展示 landing 与轻量看板)
python server.py
```

## 开源协议

本项目基于 [MIT 许可证](https://github.com/Valourman/a-share-sentiment-arbitrage-agent) 开源。
