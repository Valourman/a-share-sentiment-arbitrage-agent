# Autonomous Agent Practice (工业级 Agent 实战)

本项目旨在构建一个具备**确定性验证、自愈反思能力、状态可溯源与全链路可观测**的生产级 Agent，聚焦于可写进简历的核心技术亮点。

## 目录结构
```text
.
├── src/
│   ├── core/          # 核心基础设施 (LLM 客户端、配置校验、全局状态定义)
│   ├── tools/         # 工具注册中心、Pydantic 参数校验与执行沙箱
│   └── agent/         # 状态机编排引擎 (Planner, Executor, Self-healing loop)
├── tests/             # 单元测试与确定性验证套件
├── evals/             # 自动化基准测试与 Pass@k 评测集
├── .env.example       # 环境变量配置模版
├── pyproject.toml     # 项目依赖与打包配置
└── README.md
```

## 核心设计指标
- **状态流转**：显式状态图 (State Graph)，拒绝黑盒隐式循环。
- **错误自愈**：工具异常时堆栈反哺机制 (Self-healing on Exception)。
- **可观测性**：全链路接入 Langfuse，涵盖 Token 开销、延迟、轨迹追踪。
- **验证体系**：包含自动化 Eval 集，量化 Pass@1 成功率。
