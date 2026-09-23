from typing import Any, Dict, List, Optional
from src.core.exceptions import ToolException
from src.tools.base import Tool
from src.tools.registry import ToolRegistry, global_tool_registry


class ToolStep:
    """工具链单步配置定义"""
    def __init__(
        self,
        tool_name: str,
        input_key: str = "input",
        output_key: str = "output",
        fixed_params: Optional[Dict[str, Any]] = None,
    ):
        self.tool_name = tool_name
        self.input_key = input_key
        self.output_key = output_key
        self.fixed_params = fixed_params or {}


class ToolChain(Tool):
    """
    Hello Agents 工具链模式 (Pipeline / Chain of Responsibility)
    按顺序执行工具序列，将上一步输出作为上下文变量流入下一步
    """
    name: str = "ToolChain"
    description: str = "按拓扑或顺序管道式串联执行一系列预设工具"

    def __init__(
        self,
        name: str = "ToolChain",
        steps: Optional[List[ToolStep]] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        super().__init__()
        self.name = name
        self.steps: List[ToolStep] = steps or []
        self.registry = registry or global_tool_registry

    def add_step(
        self,
        tool_name: str,
        input_key: str = "input",
        output_key: str = "output",
        fixed_params: Optional[Dict[str, Any]] = None,
    ) -> "ToolChain":
        """追加管道执行节点"""
        self.steps.append(
            ToolStep(
                tool_name=tool_name,
                input_key=input_key,
                output_key=output_key,
                fixed_params=fixed_params,
            )
        )
        return self

    def execute(self, **initial_context: Any) -> Dict[str, Any]:
        """按序流动执行工具链"""
        context = dict(initial_context)

        for i, step in enumerate(self.steps):
            tool = self.registry.get(step.tool_name)
            if not tool:
                raise ToolException(f"工具链执行中断: 未在注册表中找到工具 '{step.tool_name}' (步骤 {i+1})")

            # 组装本步骤参数：固定参数 + 上下文注入
            call_params = dict(step.fixed_params)
            if step.input_key in context:
                call_params[step.input_key] = context[step.input_key]

            # 执行工具
            try:
                result = tool.execute(**call_params)
            except TypeError:
                # 兼容单一参数传递
                result = tool.execute(context.get(step.input_key))

            # 更新上下文
            context[step.output_key] = result

        return context
