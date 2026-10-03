<h1 align="center">A股情绪分析助手</h1>

<p align="center">读得懂股吧黑话反讽、分得清公告利好利空、自带多空 Agent 对辩的 A 股量化舆情分析系统</p>

<p align="center">
  <a href="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square" alt="Python Version" /></a>
  <a href="https://img.shields.io/badge/Contract-Pydantic%20V2-2094f3?style=flat-square"><img src="https://img.shields.io/badge/Contract-Pydantic%20V2-2094f3?style=flat-square" alt="Pydantic V2" /></a>
  <a href="https://valourman.github.io/a-share-sentiment-arbitrage-agent/"><img src="https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-4285F4?style=flat-square" alt="Live Demo" /></a>
  <a href="https://github.com/Valourman/a-share-sentiment-arbitrage-agent"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" /></a>
</p>

## 为什么做这个项目？

做 A 股舆情分析最让人头疼的是什么？是股吧老哥们实在太爱**反讽和说黑话**了。

满屏的“真牛逼天天跌”、“主力又来做慈善发红包了”，传统情感分析工具一看到“牛逼”、“红包”就机械地打上“强烈看多”，结果散户一跟进就被套在半山腰。

**A-Share Sentiment Arbitrage Agent** 就是为了解决这个问题打造的多智能体系统。它不再单看几个关键词，而是像专业投研团队一样协作：
1. **抓取全景信息**：多线程并发拉取股吧热帖、主流财经快讯、上市公司官方公告以及实时的量价行情。
2. **穿透阴阳怪气**：用大语言模型读懂字面背后的真实情绪，精准识别老哥们到底是真看好，还是被套后的气急败坏。
3. **梳理消息催化**：从海量公告和新闻里提炼出实打实的利好驱动（如资产重组、业绩暴增）与潜在暴雷风险。
4. **多空激烈对辩**：派出“多头研究员”和“空头研究员”两个 Agent 各自摆出论据互相对喷，揪出当下市场最大的分歧点。
5. **盘面事实仲裁**：聊得再热闹，最终还要看主力资金怎么走。系统拿辩论结论比对真实成交量、换手率和走势，一旦发现“散户狂吹但资金偷跑”，立刻发出诱多（`BULL_TRAP`）风控警报。

---

## 核心特性

| 特性 | 它是怎么工作的？ |
|:---|:---|
| **多源并发数据抓取** | 线程池并发采集股吧发帖、财经快讯、官方公告和秒级盘面快照，大幅缩短网络等待时间。 |
| **穿透黑话与反讽** | 借助大模型看穿“主力又送钱”、“天天跌真厉害”等阴阳怪气，还原散户真实的多空立场与心态。 |
| **公告与基本面催化归因** | 深度解析财报与官方披露，结构化提取确定性高的利好催化（Catalysts）与潜在风险冲击（Risks）。 |
| **多空 Agent 对抗辩论** | 让多头研究员 (BullAnalyst) 与空头研究员 (BearAnalyst) 围绕量价与基本面论据正面质询，挖出核心博弈焦点。 |
| **量价背离终审预警** | 将舆情博弈结论直接比对真实盘面量价，智能识别诱多出货 (`BULL_TRAP`) 或恐慌砸盘磨底 (`PANIC_BOTTOM`)。 |
| **强类型契约与容错自愈** | 全链路基于 Pydantic V2 构建强类型数据契约，大模型偶发格式错误支持自动纠偏重试，且支持 LLM / 本地规则无缝切换。 |

---

## 架构设计

系统基于 `src/workflow/pipeline.py` 实现 5 阶段工作流流水线，数据流转非常清晰直观：

```text
┌────────────────────────────────────────────────────────┐
│ 阶段 1: 并发抓取原始数据 (IngestionNode)                 │
│ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐ │
│ │ 股吧散户帖子  │ │ 主流财经资讯  │ │ 上市公司披露   │ │
│ └───────┬───────┘ └───────┬───────┘ └────────┬───────┘ │
│         │                 │                  │         │
│         │    ┌────────────┴───┐              │         │
│         │    │ 秒级实时行情快照│              │         │
│         │    └────────────┬───┘              │         │
└─────────┼─────────────────┼──────────────────┼─────────┘
          │ (帖子语料)       │ (行情基准)        │ (资讯/公告)
          ▼                 │                  ▼
┌──────────────────┐        │     ┌──────────────────────┐
│ 阶段 2: 情绪穿透  │        │     │ 阶段 3: 基本面催化提炼 │
│ Disambiguation   │        │     │ FundamentalCatalyst  │
│ (读懂反讽与真实意图)│     │     │ (梳理利好驱动/潜在风险)│
└─────────┬────────┘        │     └──────────┬───────────┘
          │ (真实情绪与置信度)│                │ (结构化利好利空)
          └────────────┐    │    ┌───────────┘
                       ▼    ▼    ▼
          ┌──────────────────────────────────┐
          │ 阶段 4: 多空研究员对抗辩论         │
          │ MultiAgentDebateNode             │
          │ ┌──────────────┐ ┌─────────────┐ │
          │ │ 多头研究员   │ │ 空头研究员  │ │
          │ │ BullAnalyst  │ │ BearAnalyst │ │
          │ └──────┬───────┘ └──────┬──────┘ │
          │        └───────┬────────┘        │
          │                ▼                 │
          │      提炼多空双方核心分歧点       │
          └────────────────┬─────────────────┘
                           │ (辩论决议与核心焦点)
                           ▼
          ┌──────────────────────────────────┐
          │ 阶段 5: 量价事实终审与风控仲裁    │
          │ ArbitrageArbitrationNode         │
          │ 结合客观量价事实，识别陷阱并输出建议│
          └──────────────────────────────────┘
```

---

## 快速上手

从零运行只需要三步，新手建议先从免 API Key 的演示模式开始体验。

### 1. 准备运行环境

确保你的电脑安装了 Python 3.10 或更高版本：

```bash
# 克隆代码仓库
git clone https://github.com/Valourman/a-share-sentiment-arbitrage-agent.git
cd a-share-sentiment-arbitrage-agent

# 创建并激活虚拟环境
python -m venv .venv

# Windows 激活方式：
.venv\Scripts\activate
# macOS / Linux 激活方式：
source .venv/bin/activate

# 安装项目依赖
pip install -e .
```

### 2. 体验免 Key 离线演示（0 成本，推荐首选）

不需要配置任何 API 密钥，直接运行下面的命令：

```bash
python demo.py --mock
```

程序会加载长电科技（600584）的真实切片样本，并在几秒钟内在终端输出完整的彩色分析看板：
- 股吧帖子是看多还是看空？有没有反讽？深层动机是什么？
- 官方公告和新闻里提炼出了哪些正向和负向催化？
- 看多研究员与看空研究员辩论了什么，分歧在哪？
- 最终终审裁决：有没有量价背离风险？给出的建议是观望、减仓还是跟进？

### 3. 接入真实大模型（在线实测）

如果你想接入真实大模型分析实时股票：

1. 复制环境配置模板：
   ```bash
   cp .env.example .env
   ```

2. 打开 `.env` 填入你的大模型密钥（兼容 OpenAI、DeepSeek、通义千问等所有兼容接口）：
   ```env
   OPENAI_API_KEY=你的真实Key
   OPENAI_BASE_URL=https://api.openai.com/v1
   MODEL_NAME=gpt-4o
   ```

3. 运行全链路实时分析：
   ```bash
   # 指定股票代码（例如 600584），分析最新 20 条讨论
   python demo.py --code 600584 --posts 20
   ```

---

## 界面展示

如果你不想只看黑底白字的命令行，系统为你准备了开箱即用的可视化界面：

### 1. 交互式数据大盘 (Streamlit)

适合交互式实操与动态复盘：

```bash
streamlit run app.py
```

在浏览器里可以直接输入任意股票代码，实时查看散户情绪气泡图、多空对辩卡片和量价背离警报仪表盘。

### 2. 本地免构建前端看板

系统内置了一套轻量静态前端，不需要装 Node.js 或前端依赖，直接启动 Python 原生服务：

```bash
python server.py
```

启动后在浏览器打开 `http://localhost:8080/` 即可浏览多智能体推演过程与决策大盘。线上预览也可直接访问：[GitHub Pages 在线 Demo](https://valourman.github.io/a-share-sentiment-arbitrage-agent/)。

---

## 评测与基准测试

为了验证系统到底能不能看懂股吧老哥的黑话，项目内置了两套评测流水线：

### 1. 真实黑话基准 (Golden Benchmark)

在 `evals/dataset.py` 中整理了真实的 A 股经典黑话与反讽语料，直接运行评测：

```bash
python -m evals.benchmark
```

- **多空立场识别 (Stance)**：测试能否准确看穿股吧散户的真实做多或做空意图。
- **反讽与黑话穿透 (Sarcasm)**：专门针对“正话反说”与破防语境进行判别。

*说明：基准库样本主要用于阶段性回归检验。真实交易环境中语料变化多端，建议在实盘或模拟盘前结合具体标的抽样验证。*

### 2. 学术范式基准 (Public Benchmark)

参考公开金融情感学术标注标准构建的测试集，运行方式：

```bash
python -m evals.public_benchmark
```

可一键输出标准多分类指标（查准率 Precision、查全率 Recall、F1 分数），验证判定逻辑的稳定性。

---

## 环境配置参数

系统所有核心配置均在 `.env` 或 `src/core/config.py` 中管理，常用选项如下：

| 环境变量 | 默认值 | 作用说明 |
|:---|:---|:---|
| `OPENAI_API_KEY` | 空 | 大模型调用密钥（支持 OpenAI、DeepSeek、Qwen 等任意兼容端点） |
| `OPENAI_BASE_URL` | 空 | 模型服务地址（不填则默认走 OpenAI 官方接口） |
| `MODEL_NAME` | `gpt-4o` | 负责反讽分析与多空辩论的主模型名称 |
| `TYPESAFE_API_KEY` | 空 | TypeSafe Jev 决策引擎密钥（可选，未填时自动转为大模型或内置规则） |
| `DEFAULT_SENTIMENT_ENGINE` | `auto` | 情绪分析引擎切换：`auto`（自动路由）/ `llm`（纯大模型）/ `mock`（内置规则） |
| `LANGFUSE_PUBLIC_KEY` | 空 | 可选的 Langfuse 调用链路追踪公钥 |

---

## 常用开发与测试指令

项目内置了完整的测试用例与静态分析工具，日常开发测试常用以下命令：

```bash
# 运行全部单元测试
pytest

# 运行代码覆盖率统计（需先安装 pytest-cov）
pytest --cov=src

# 运行代码风格与类型检查
ruff check .

# 启动本地免构建轻量网页服务
python server.py
```

---

## 开源协议

本项目基于 [MIT 许可证](https://github.com/Valourman/a-share-sentiment-arbitrage-agent) 开源，欢迎提交 Issue 和 Pull Request 一起交流！
