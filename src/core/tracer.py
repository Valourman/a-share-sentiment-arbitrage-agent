import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceSpan:
    """单次操作或生命周期阶段的追踪跨度 (Span)"""
    name: str
    span_type: str  # tool / llm / loop_step / reflect
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: float = 0.0
    status: str = "running"
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Any = None
    tokens_used: int = 0
    error: Optional[str] = None


class AgentTracer:
    """
    智能体执行链路追踪器：
    捕获每个 Agent Step、工具调用、LLM 推理的耗时、入参出参及异常，并保留可接入 Langfuse 等 APM 平台的拓展能力
    """
    def __init__(self):
        self.spans: List[TraceSpan] = []

    @contextmanager
    def span(self, name: str, span_type: str, inputs: Optional[Dict[str, Any]] = None):
        """上下文管理器，安全追踪一段操作的执行与耗时"""
        s = TraceSpan(name=name, span_type=span_type, inputs=inputs or {})
        self.spans.append(s)
        try:
            yield s
            s.status = "success"
        except Exception as e:
            s.status = "failed"
            s.error = str(e)
            raise
        finally:
            s.end_time = time.time()
            s.duration = round(s.end_time - s.start_time, 3)

    def get_total_latency(self) -> float:
        """获取所有 Span 累计耗时（秒）"""
        return round(sum(s.duration for s in self.spans), 3)

    def get_total_tokens(self) -> int:
        """获取所有 Span 消耗的 Token 总量"""
        return sum(s.tokens_used for s in self.spans)

    def get_summary(self) -> Dict[str, Any]:
        """输出链路追踪汇总指标"""
        return {
            "total_spans": len(self.spans),
            "total_latency_seconds": self.get_total_latency(),
            "total_tokens": self.get_total_tokens(),
            "has_error": any(s.status == "failed" for s in self.spans),
            "failed_spans": [s.name for s in self.spans if s.status == "failed"],
        }
