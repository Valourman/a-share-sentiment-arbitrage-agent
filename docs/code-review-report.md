# Agent 项目全面代码审查报告

- **审查日期**：2026-09-30
- **审查范围**：`src/`（core / agent / agents / workflow / protocols / tools / market_data / memory / knowledge，共 62 个 .py 文件）、`app.py`、`server.py`、`demo.py`、`frontend/`、`evals/`、`tests/`（24 个文件）、`docs/`、`pyproject.toml`、`.github/workflows/`、`.gitignore`
- **审查方法**：4 个并行子代理逐文件静态审查 + 对 P0/P1 关键结论的逐行人工复核 + 工具实测（`ruff check .` 通过、`git ls-files`/`git log` 核实文件跟踪状态）
- **问题统计**：P0 严重 2 项 · P1 重要 16 项 · P2 一般约 40 项 · P3 轻微约 60 项（P3 合并归类呈现）

---

## 执行摘要

项目整体架构意图清晰（5 阶段流水线 + 工具注册表 + Pydantic V2 契约），`src/market_data` 与 `tests/test_market_data.py` 质量较高。但存在两类核心风险：

1. **安全与正确性硬伤**：计算器工具存在可被白名单绕过的 `eval()`（RCE）；Streamlit 看板存在存储型 XSS；`FunctionCallAgent` 的 tool-calling 协议在第二轮必然失败（功能不可用）；仅配置 `OPENAI_API_KEY` 时 LLM 客户端永不初始化。
2. **评测可信度问题**：黄金基准语料与规则引擎关键词逐字重合，README 宣称的 "100.0%" 属循环验证；评测脚本在无 API Key 时静默降级为 mock 引擎，输出指标失真。

此外存在多项**系统性架构冗余**：`src/agent` 与 `src/agents` 职责重叠、两套知识检索实现并存、三套 HTTP 客户端栈、`index.html` 双份维护、import 即注册全局工具等。

---

## 一、P0 严重问题（2 项）

### P0-1 计算器 eval 沙箱可绕过，存在远程代码执行（RCE）风险

- **位置**：`src/tools/builtin/calculator.py:51-58`
- **证据**：
  ```python
  if not re.match(r"^[0-9\.\+\-\*\/\(\)\,\s\^a-zA-Z_]+$", expr):  # 放行字母、下划线、点号、括号
      return "错误: 表达式包含不安全字符"
  result = eval(python_expr, {"__builtins__": {}}, self.SAFE_NAMES)
  ```
- **原因**：以"字符白名单"做 eval 前置过滤，但 Python 对图遍历只需 `.`、字母、下划线、括号——全部被放行。`{"__builtins__": {}}` 无法阻止属性链逃逸。
- **影响**：表达式 `().__class__.__base__.__subclasses__()` 完全由合法字符组成，可遍历已加载类实现任意代码执行。同文件 `^ → **` 替换使 `9^9^9` 变为天文数字幂运算，一次调用即可造成 CPU/内存 DoS。该工具已注册进全局工具注册表，LLM 可被诱导调用。
- **建议**：彻底移除 `eval`，改为 `ast.parse` + 节点类型白名单（仅 `Expression/BinOp/UnaryOp/Call/Name/Constant`，禁止 `Attribute/Subscript`）的解释执行；对幂运算底数/指数加幅值上限。`calculator.py:61` 的错误回显原始表达式也应改为通用错误信息（细节入日志）。

### P0-2 FunctionCallAgent 工具调用协议在第二轮必然失败（功能死代码）

- **位置**：`src/agents/function_call_agent.py:44, 63-94`，根因在 `src/core/message.py:26-34`
- **证据**：agent 把 `tool_calls`/`tool_call_id` 塞进 `Message.metadata`（第 63-68、88-93 行），下一轮 `m.to_openai_dict()` 序列化时**只输出 role/content/name**，metadata 被整体丢弃。
- **原因**：`Message` 协议模型没有 `tool_calls`/`tool_call_id` 一等字段，试图用 metadata 兜底但序列化出口不读取。
- **影响**：OpenAI tool-calling 协议要求 assistant 消息携带 `tool_calls`、tool 消息携带 `tool_call_id`；第二轮请求必然返回 400，`FunctionCallAgent` 对任何真实工具调用均不可用。
- **建议**：为 `Message` 增加 `tool_calls: Optional[List[Dict]]` 与 `tool_call_id: Optional[str]` 字段，`to_openai_dict()` 显式输出；agent 直接构造这两个字段。

---

## 二、P1 重要问题（16 项）

### 安全与配置

**P1-1 app.py 存储型 XSS：第三方抓取内容未转义注入 `unsafe_allow_html=True`**
- 位置：`app.py:1095`（股吧帖子原文）、`app.py:1100`（消歧依据）、`app.py:1036-1051`（催化项）、`app.py:1119-1141`（新闻/公告标题）、`app.py:1003-1015`（辩论论点）、`app.py:927-930`、`app.py:877`。
- 原因：来自东方财富股吧、新浪新闻/公告（任何人可发布的文本）直接 f-string 拼入 `st.markdown(..., unsafe_allow_html=True)`；同文件 `app.py:1154` 对执行日志做了手工转义，说明有转义意识但只覆盖了一处。
- 影响：帖子标题含 `<img src=x onerror=...>` 即可在看板用户浏览器执行任意脚本（可窃取侧边栏输入的 API Key）。
- 建议：所有外部文本统一 `html.escape()` 后再拼模板，或改用不开 unsafe 的原生组件渲染。

**P1-2 仅配置 OPENAI_API_KEY 时 LLM 客户端永不初始化**
- 位置：`src/core/llm.py:50`（`if api_key and base_url:` 双条件）；`src/core/config.py:12`（`openai_base_url` 默认 None）。
- 影响：用户只设 `OPENAI_API_KEY`（最常见配置）时 `is_available` 恒为 False，`chat()` 抛"未就绪"，报错文案还误导用户检查 API Key。README:162 声称 `OPENAI_BASE_URL` 默认值为官方端点，与实现（默认 None）也不符。
- 建议：改为 `if api_key:`，base_url 为 None 时不传参（SDK 自动走官方端点）；同步修正 README。

**P1-3 配置健壮性：脏环境变量在 import 时崩溃；`max_retries` 是死配置**
- 位置：`src/core/config.py:25-32`（`float(os.getenv(...))` 无防护，且模块级 `global_config = AgentConfig.from_env()`）；`src/core/config.py:15` 定义的 `max_retries` 从未传入 `OpenAI(...)`（llm.py:52-56），`chat()` 也无重试循环。
- 影响：`TEMPERATURE=abc` 导致整个包 import 失败，堆栈指向与业务无关处；对外承诺的"接口自愈重试"完全不生效，瞬时网络抖动直接失败。
- 建议：解析加 try/except 回退默认值并告警（或改用 pydantic-settings）；`OpenAI(..., max_retries=...)` 或自行实现退避重试。

### 核心业务正确性

**P1-4 `DivergenceType._missing_` 空串/子串误判为 BULL_TRAP（高风险结论）**
- 位置：`src/agent/state.py:14-21`。`"" in member.value.upper()` 恒为 True——空字符串或脏数据第一轮迭代即命中 BULL_TRAP。
- 影响：上游产出空/脏枚举值时，背离类型被静默判为"多头诱多"，直接污染风控结论——金融场景的方向性错误。
- 建议：空值返回 None（走默认抛错）；子串匹配要求最小长度或改精确匹配。

**P1-5 FundamentalCatalystNode 兜底逻辑凭空捏造 POSITIVE 催化**
- 位置：`src/workflow/nodes.py:191-200`。无任何新闻命中利好词时，把 `news_list[0]`（可能纯中性/偏空）包装成 POSITIVE 催化注入辩论输入，BullAnalyst 将以人造"利好"为论据（nodes.py:247-249）。另 `nodes.py:118-119` 的 `llm` 参数是死参数，docstring 宣称"深度解析"实为关键词匹配。
- 建议：删除兜底或改为 NEUTRAL 且不进 bull 论据；要么真正接入 LLM。

**P1-6 行情缺失被当作"盘跌"参与置信度；多空置信度公式系统性偏空**
- 位置：`src/workflow/nodes.py:238, 260, 287`。`chg=0.0`（抓取失败）与真实平盘混同：多头被固定扣 0.1，空头保底 0.6+，`consensus_bias` 以 0.15 差值判定，"空方占优"成为系统性高频结论，辩论形同虚设。
- 建议：`market_valid=False` 时走独立"无盘面证据"分支，双侧置信度公式对称化。

**P1-7 消歧结果与帖子索引错配风险**
- 位置：`src/workflow/nodes.py:109`（返回 `[r for r in results if r is not None]`，结果可能变短）+ `src/workflow/pipeline.py:127-136`（按 idx 配对 `posts[idx]`）。
- 影响：一旦出现 None 空洞，帖与分析结果张冠李戴。且 `nodes.py:91` 的 None 过滤本身是死代码（异常路径直接整体失败）。
- 建议：失败位填 mock 结果保证等长并断言，或返回携带原始索引的元组。

**P1-8 市场前缀映射错误且三处规则互相矛盾**
- 位置：`src/tools/market.py:28-34`（'5' 开头误判 sz、'2' 开头落入默认 sh）、`src/tools/scraper.py:69-75`、`src/tools/stock_resolver.py:58`（不支持北交所）。
- 影响：同一股票代码经不同路径得到不同市场前缀，抓取/行情可能查错市场。
- 建议：抽取唯一的 `normalize_secid()` 公共模块（含北交所段），加单测。

**P1-9 停牌股被计算为 -100% 涨跌幅，`is_trading` 恒为 True**
- 位置：`src/tools/market.py:64-75`。停牌时现价 0.00 → `chg_pct=-100.0`；`is_trading=True` 无条件硬编码。下游靠 `current_price > 0` 间接挡住，但快照携带错误语义字段。
- 建议：`curr_p <= 0` 时 `is_trading=False`、`change_percent=0`。

### 可靠性与资源

**P1-10 Phase 1 部分失败无隔离 + 流水线全程无异常边界**
- 位置：`src/workflow/nodes.py:47-50`（4 路 future 直接 `future.result()`，单源异常丢弃全部已采集数据）；`src/workflow/pipeline.py:57-209`（`run()` 无一个 try/except，单条语料异常中断整个 5 阶段流程）。
- 建议：IngestionNode 每路单独 try/except 降级；DisambiguationNode 单条失败填 mock；pipeline 外层包裹阶段级异常边界并写入失败终态。

**P1-11 长期记忆无界增长；工作记忆淘汰策略与注释不符**
- 位置：`src/memory/manager.py:74, 87, 121`（`long_term_memory` 只增不减，search/consolidate 随时间线性变慢）；`manager.py:39-41`（注释"淘汰低重要性条目"，实际纯 FIFO 不看 importance，capacity 跨用户共享，多租户隔离被击穿）。
- 建议：长期记忆加容量上限 + `(importance, created_at)` 加权淘汰或落盘分页；工作记忆按 user_id 分桶、按重要性选牺牲者。

**P1-12 RAG 分块器对超长单段落不切分 + 向量入库未走批量接口**
- 位置：`src/knowledge/chunker.py:48-78`（仅按 `"\n\n"` 切段，5000 字无空行段落原样成为一个 chunk，绕过 chunk_size 上限）；`src/knowledge/vector_store.py:54-57`（逐 chunk 调 `embed_query`，接入真实远程 embedding 后即 N 次网络往返——`BaseEmbedding.embed_documents` 定义了却没用）。
- 建议：段落超限时按 chunk_size 硬切保留 overlap；入库收集后单次调用 `embed_documents`。

**P1-13 eastmoney 按 f3（涨跌幅）排序分页，盘中静默丢票**
- 位置：`src/market_data/eastmoney.py:69, 104-124`。盘中 f3 实时变化导致股票翻页间位移，"挤出/顶替"（无重复、总数不变）场景完全检测不到。
- 建议：改用稳定键 `fid=f12`（按代码排序），或将"仅收盘后同步"约束前移到采集层。

**P1-14 chain.py 的 TypeError 兜底重试掩盖真实错误、可能重复副作用**
- 位置：`src/tools/chain.py:74-78`。工具**内部逻辑**抛出的 TypeError 也被当成"签名不匹配"重试；若抛错前已产生副作用则执行两次；第二次调用大概率再失败并以误导形态传播。
- 建议：删除该兜底，用 `inspect.signature` 前置校验，缺参抛带步骤号的 `ToolException`。

**P1-15 A2A 协议错误结果与正常结果无法区分**
- 位置：`src/protocols/a2a/implementation.py:49-72`。任务失败把 `str(e)` 当普通结果返回，`request_skill` 不检查 `task.status`，错误沿调用链静默传播。
- 建议：检查 FAILED 状态时抛异常或返回结构化错误结果。

**P1-16 评测可信度：数据泄漏 + 静默降级（详见第四节）**
- 黄金基准语料与规则关键词逐字重合（`evals/dataset.py:13-31` vs `src/tools/analyzer.py:32-37`），README "100.0%" 为循环验证；`evals/benchmark.py:44` 无 Key 时"LLM 判断"列实际跑 mock；`evals/public_benchmark.py:55` 标注 JEV 引擎但无 Key 时静默跑 mock；`:183` 的"Schema 解析故障率 0.0%"是硬编码文案。

---

## 三、P2 一般问题（约 40 项，按主题归类）

### 3.1 架构与模块划分（系统性冗余）

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| 1 | `src/agent/` 与 `src/agents/` 两包职责重叠：后者是通用范式（Simple/ReAct/Reflection/PlanSolve/FunctionCall），前者是金融业务实现却又重导出全部范式，`base_reflection.py` 是纯转发 shim；双向重导出让调用方无法判断正典入口 | `src/agent/__init__.py:5-9` | 金融代码并入 `agents/finance/` 或停止重导出，shim 挂 DeprecationWarning |
| 2 | 两套知识检索并存：`src/memory/knowledge.py`（子串匹配、无排序）vs `src/knowledge/hybrid_engine.py`（RRF 混合检索），两个工具同时注册进全局 registry；且 `knowledge/tools.py:9` 反向依赖 memory 层——层次倒置 | memory/ vs knowledge/ | 废弃子串版检索职能，统一走混合检索 |
| 3 | 三套 HTTP 栈并存：market.py 用 `urllib`、scraper 用 `httpx`、analyzer 用 `requests`，超时/代理/连接池策略各不相同 | src/tools/ | 统一到 httpx 并集中配置 |
| 4 | 两套 LLM 客户端：`ConversationalArbitrageAgent` 绕过 `HelloAgentsLLM` 自建 OpenAI 客户端——无超时（`conversational.py:45`，网络挂起 UI 卡死）、模型默认值不一致（`gpt-4o` vs 配置的 `gpt-4o-mini`）、content 可能返回 None（`:202,327`） | conversational.py | 复用 HelloAgentsLLM |
| 5 | `engine.py:46-51` 与 `pipeline.py:44-47` 三行工具解析逻辑逐字重复（且各含一个变量用错的 bug：`engine.py:50` 查入参 `tools` 而非 `self.tools`，`tools=None` 时依赖注入静默失效） | engine/pipeline | 抽公共函数并统一修复 |
| 6 | 根 `index.html` 与 `frontend/index.html` 963 行完全重复（仅差 19 行导航条），双份维护必然漂移 | index.html:100-118 | 保留单一文件，导航条 JS 注入或部署时拼接 |
| 7 | import 即副作用：`src/tools/__init__.py:8-10` import 即实例化 analyzer/LLM 客户端并注册全局工具；`src/memory/tools.py:117-121`、`analyzer.py:12`（模块级 `load_dotenv()`）同样 | tools/、memory/tools.py | 注册表存工厂惰性构造；注册入口改为显式函数 |
| 8 | scraper 的 `execute()` 与 IngestionNode 是同一采集需求的串行/并发两套重复实现 | scraper.py:53-64 | 抽共享并发采集函数 |
| 9 | `engine.py:74-79` 非 workflow 模式日志宣称"并发采集"实为三次顺序 requests | engine.py | 修正文案或统一走 pipeline |

### 3.2 工作流与业务逻辑

| # | 问题 | 位置 |
|---|------|------|
| 10 | `nodes.py:78-96` `engine_mode` 与 `use_llm` 组合矛盾：传 `use_llm=False, engine_mode="llm"` 仍会调 LLM | nodes.py:78 |
| 11 | 无效盘面快照（全 0）被当作"客观事实"写入执行日志（"现价 0.00 元 涨跌 +0.00%"） | pipeline.py:103-106 |
| 12 | 后续阶段日志复用 Phase 1 的时间戳；`:132` 截断阈值 40/42 不一致 | pipeline.py:81 等 |
| 13 | `consensus_bias` 为自由 str 写入 5 种魔法字符串，`source_type` 契约描述与实际值（"macro"）不符 | workflow/state.py:16,45 |

### 3.3 工具层

| # | 问题 | 位置 |
|---|------|------|
| 14 | scraper：`fetch_financial_news` 的 stock_code 未清洗直接拼 URL（路径注入面），三方法校验强度不一（对比 `fetch_guba_posts:81` 有 `\D` 清洗） | scraper.py:66-75,136 |
| 15 | scraper：`max_posts=int(kwargs.get(...))` 对 LLM 传入"30篇"裸崩；`soup.select` 在 try 块外（畸形 HTML 逃逸，即拖垮流水线路径之一）；"1.2万"类阅读数静默丢帖；href 未校验协议 | scraper.py:53-64,92,102,120 |
| 16 | registry：同名工具注册静默覆盖无告警 | registry.py:33-36 |
| 17 | async_executor：工具执行无超时，第三方工具无超时网络调用可耗尽 5 个线程致执行器假死；名为 Async 实为线程池；每次调用新建池；结果 dict 键集不一致 | async_executor.py:39,52,28 |
| 18 | stock_resolver：`_RUNTIME_CACHE` 无界增长且失败结果**永久负缓存**（一次网络故障→该 token 永远解析失败直到重启）；`_fetch_suggest_value` 裸 `except: pass` 无日志；明文 HTTP（`http://suggest3.sinajs.cn`，可被中间人篡改污染解析结果）；纯数字 token 也触发在线请求 | stock_resolver.py:37,89,100,110 |
| 19 | analyzer：LLM 全量失败静默降级 mock，调用方无感知；Jev 响应 `float()` 强转无类型防御；并发共享 llm client 线程安全依赖隐性假设 | analyzer.py:225-228,127-138,45 |
| 20 | chain.py:70-71 `input_key` 缺失时静默跳参，错误延后暴露 | chain.py |
| 21 | base.py:29 类级可变默认值 `parameters: Any = []`，所有子类共享同一 list（当前侥幸无恙的定时炸弹） | tools/base.py |
| 22 | llm.py:28-31 端口子串误判服务商（`"8000" in url`）；`parser.py:28` 贪婪正则跨 JSON 对象且不支持顶层数组 | llm.py, parser.py |

### 3.4 协议层

| # | 问题 | 位置 |
|---|------|------|
| 23 | a2a：task_id 毫秒时间戳碰撞互相覆盖；"异步派发"实为同步阻塞执行；`_tasks` 字典无界增长 | implementation.py:39,43-51,33 |
| 24 | mcp client：docstring 虚标 Stdio/HTTP/SSE 能力（实际仅 in-process）；参数不匹配 TypeError 裸抛；MCPTool 在 `super().__init__()` 前设置实例属性 | mcp/client.py:45,50 |

### 3.5 记忆与知识库

| # | 问题 | 位置 |
|---|------|------|
| 25 | 全部记忆结构（buffer/manager/knowledge）无线程安全保护，且 MemoryTool/RAGTool 是全局单例多线程共享 | memory/ 全模块 |
| 26 | `buffer.py:20` 边界 bug：`max_messages=1` 时 `[-0:]` 等于全量，截断失效；按条数（非 token）截断可切裂 tool 调用配对（OpenAI 400） | memory/buffer.py:17-22 |
| 27 | `memory/knowledge.py:38-44` 检索无相关性排序（先注册先返回），`query in item.term` 单字误匹配 | memory/knowledge.py |
| 28 | chunker：`publish_time` 用本地时区解析 + 静默 fallback created_at（时间衰减基准失真）；chunk_size/overlap 参数无校验 | chunker.py:27-30,14-16 |
| 29 | hybrid_engine：静态术语（TERM）也被 30 天半衰期衰减（录入两月的术语权重减半）；重复 doc_id 无去重/删除路径，chunk 翻倍污染 BM25 统计 | hybrid_engine.py:52-57,156-166 |
| 30 | `RetrievalResult.score` 注释标称 0~1，实际 RRF 得分上限约 0.033（下游按 0~1 阈值过滤将永远为空） | knowledge/schema.py:45 |

### 3.6 入口与前端

| # | 问题 | 位置 |
|---|------|------|
| 31 | app.py 同步阻塞长任务：一次研判最多 60 次串行 LLM 调用在 Streamlit 脚本线程内执行，无缓存、不可取消、rerun 重复计算 | app.py:537-544,634-641 |
| 32 | app.py 错误处理不一致：侧边栏预设/hero 按钮无捕获（chat_input 有），异常时向用户抛完整 traceback | app.py:691-695,821-840 |
| 33 | eastmoney：UA 为自报家门型机器人标识易被风控；允许 `interval=0` 关闭全部频率控制 | eastmoney.py:49,40-41 |
| 34 | storage：未开 WAL（写事务阻塞全部读）；`DEFAULT_DB` 相对路径依赖 CWD（不同目录运行各建一份数据库） | storage.py:82-86,12 |

### 3.7 工程一致性

| # | 问题 | 位置 |
|---|------|------|
| 35 | README:123 引用不存在的 `requirements.txt`（git ls-files 已核实） | README.md |
| 36 | README:202 `pytest --cov=src` 缺 pytest-cov（dev 依赖未声明且未安装，命令必然失败） | README/pyproject |
| 37 | `langfuse` 声明为必装依赖但全项目零 import（tracer.py:25 仅注释提及），`LANGFUSE_PUBLIC_KEY` 环境变量无消费者 | pyproject.toml:16 |
| 38 | README 声称 MIT 许可证但仓库无 LICENSE 文件（法律上未授予许可） | README.md:213 |
| 39 | README "100.0%" 营销口径与 `docs/mcp-project-overview.md:35` "不能据此推断泛化" 自我矛盾 | 文档 |
| 40 | 测试封闭性：`test_conversational.py:35-66` 依赖真实外网且断言弱到"网络失败也通过"（未验证行为）；StockResolver 类级缓存跨测试污染；`test_parser_demo.py` 是零断言 print 脚本却被 pytest 收集 | tests/ |

---

## 四、评测与测试专项（可信度问题）

### 4.1 评测（evals/）

1. **【P1】数据泄漏/循环验证**：黄金基准 15 条语料照着 `analyzer.py:32-37` 的规则关键词手工构造（"好耶+送钱"、"吸筹+主升浪+起飞"等逐字重合），规则基线 100% 是构造产物而非泛化能力。唯一字典外样本（"送温暖"）mock 引擎实际判错，反证基准并非全对。README 的评测表格应注明"n=15 手工构造样本"。
2. **【P2】静默降级**：`benchmark.py:44` 无 Key 时"真实 LLM 引擎"列实际跑关键词规则；`public_benchmark.py:55` 标注 JEV 引擎实际跑 mock——报告的 Precision/Recall/F1 全部失真。建议入口检查 `is_available` fail-fast，或用结果自带的 `engine_used` 字段校验标注。
3. **【P2】硬编码假指标**：`public_benchmark.py:183` 的"Schema 解析故障率 0.0%"是写死的文案，与真实测量值并列输出。
4. **【P3】`benchmark.py:69-70` 潜在除零；小样本（n=15/35）输出 Delta 百分比无显著性说明。

### 4.2 测试（tests/）

**正面评价**：整体质量高于常见个人项目——`test_market_data.py` 用 `httpx.MockTransport` 完全离线且断言严格（分页一致性、事务回滚、幂等性），是全仓库范例；`test_framework_alignment.py` 覆盖了真实回归语义（"零值行情不得变成 PANIC_BOTTOM"）。

主要问题：
1. **【P1】test_conversational.py**：真实调用东财/新浪约 3-4 个外部接口（约 8s 超时×3），关键断言 `"成交额" in reply_text` 在"数据不足"分支同样成立——网络完全失败测试照样绿，通过≠逻辑对。
2. **【P2】StockResolver 测试路径**触发明文 HTTP 外部 API + 类级可变缓存使单测间隐式耦合（执行顺序敏感）。
3. **【P3】** `test_reflection_engine.py` docstring 阈值（0.25）与实现（0.20）脱节且边界值（0.20/0.21/-0.20）从未被测试；直接测试私有方法（`_reflect_on_divergence` 等）；`sys.path.insert` 补丁散落多个文件但项目已可 `pip install -e .`（冗余且风格割裂）。

---

## 五、P3 轻微问题（合并归类，共约 60 项）

- **死代码/死参数**：`plan_solve_agent.py:45` tools 形参从未使用；`knowledge/tools.py:81` `kwargs.get("top_k")` 恒为默认值；`engine.py:70` `iteration_count` 死赋值；`models.py:29` `written_stocks` 冗余字段。
- **吞异常/无日志**：`plan_solve_agent.py:63`（`except: pass`）、`function_call_agent.py:73-76`（非法 JSON 静默变空 dict）、`stock_resolver.py:110`、`knowledge/tools.py:91`；`llm.py` 把所有异常一律包成 LLMException 丢失类型语义。
- **解析健壮性**：`plan_solve_agent.py:67` `strip("- 0123456789.、")` 把 "2024年财报分析" 剥成 "年财报分析"；ReAct 工具参数名硬编码 `query=`（参数名不符的工具全部 TypeError）；`conversational.py:73` 身份关键词 `'架构'` 过宽（"筹码架构"被误判为 SYSTEM_IDENTITY 意图）。
- **命名与风格**：`FunctionCallAgent` 无 `tool_calls` 字段（见 P0-2）；`RoleType.FUNCTION` 是 OpenAI 已废弃角色；`BaseAgent` 别名与 `AgentException` 命名体系不统一；`Tool`/`BaseTool` 双名并存；工具 schema 两种声明风格（ToolParameter 列表 vs 裸 dict）混用；`TaskStatus` 应为 Enum；A2ATool 用字符串 `replace` 反推技能名。
- **性能小项**：vector_store 纯 Python 暴力全扫 + 全排序（应用 `heapq.nlargest`，范数可缓存）；BM25 查询词元未去重；sparse_retriever 中文单字分词精度有限（IDF/长度归一化公式本身正确）。
- **UI/入口小项**：`app.py:742` 非法输入直接当股票代码发起 4 路网络请求；`app.py:877` `stock_name` 为 None 时页面渲染字面 "None"（demo.py:97 有正确兜底，app.py 没有）；app.py 单文件 1190 行含 480 行内嵌 CSS；demo.py 函数默认 20 vs CLI 默认 15 不一致；server.py 绑 `0.0.0.0`/单线程/端口硬编码（路径穿越已实测排除）。
- **其他**：`conversational.py:33` 会话历史无界增长；`a2a` 同步阻塞；`mcp/tool.py` 初始化顺序依赖基类实现细节；`AgentState` 可变 BaseModel 未开 `validate_assignment`；`sync.py:260` 注入 now 时审计耗时失真。

---

## 六、已核实无问题的事项（排除项）

为避免误报，以下预设怀疑经实测/逐行核实**不成立**：

1. `server.py` 无路径穿越/任意文件读取（`SimpleHTTPRequestHandler(directory=...)` 内建防护跳过 `..`）。
2. `data/*.sqlite3`、`__pycache__/*.pyc`、`.coverage`、`.env` 均**未**被 git 跟踪且历史从未提交，`.gitignore` 覆盖完整。
3. `ruff check .` 实测通过（E/F/W，line-length 120）。
4. `src/market_data/storage.py` 无 SQL 注入（全参数化 + code 格式校验）、连接均正确关闭、事务回滚完整。
5. eastmoney 接口（push2 JSON API）当前仍有效；重试退避、rc/total/跨页去重校验实现正确；sync.py 的 OHLC 一致性校验正确。
6. BM25 的 IDF 与长度归一化公式正确；RRF 融合实现正确。
7. 前端五个文件无硬编码密钥。
8. 未发现 API 密钥写入日志（异常日志只记 message）。

---

## 七、修复优先级路线图

| 阶段 | 内容 | 对应问题 |
|------|------|----------|
| **立即（1-2 天）** | calculator 改 AST 白名单求值；app.py 全量 `html.escape()`；`Message` 增加 tool_calls/tool_call_id 字段 | P0-1、P0-2、P1-1 |
| **短期（本周）** | llm.py 双条件修复 + max_retries 接入；`_missing_` 空值防护；删除捏造催化兜底；置信度公式对称化；IngestionNode/DisambiguationNode 单点降级 + pipeline 异常边界 | P1-2 ~ P1-10 |
| **中期（1-2 周）** | 评测 fail-fast 与标注修正、README 指标口径更正；统一 `normalize_secid`；记忆容量上限与淘汰策略；chunker 硬切 + embed_documents 批量；chain.py TypeError 兜底删除；A2A 错误语义结构化 | P1-11 ~ P1-16 |
| **重构排期（单独 milestone）** | `src/agent` 与 `src/agents` 合并；两套知识检索合一；三套 HTTP 栈统一到 httpx；index.html 去重；注册表工厂化消除 import 副作用；app.py 拆分 | P2 架构类 |

**核心结论**：项目工程化基础（类型契约、测试意识、数据层质量）较好，但存在 2 个 P0 安全/功能性硬伤、多个金融结论正确性问题，以及评测可信度问题——README 对外宣称的核心指标当前不可信，建议在修复评测闭环前不要引用 "100.0%" 数据。
