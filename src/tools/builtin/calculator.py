import math
import re
from typing import Any
from src.tools.base import Tool, ToolParameter


class CalculatorTool(Tool):
    """
    Hello Agents 内置安全数学计算器工具
    支持基础四则运算、幂运算以及常用数学函数（sqrt, sin, cos, log 等）
    """
    name: str = "calculator"
    description: str = "用于执行数学表达式求值的科学计算器。输入合法的数学表达式，例如 '2 * (3 + 4)' 或 'sqrt(16)'。"
    parameters = [
        ToolParameter(
            name="expression",
            type="string",
            description="待求值的数学算式字符串，如 '(120 + 35) / 5'",
            required=True,
        )
    ]

    # 安全命名空间白名单
    SAFE_NAMES = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "pow": math.pow,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "pi": math.pi,
        "e": math.e,
    }

    def execute(self, expression: str = "", **kwargs: Any) -> Any:
        # 兼容关键字参数与普通入参
        expr = expression or kwargs.get("input", "") or kwargs.get("query", "")
        if not expr and kwargs:
            # 取 kwargs 中的第一个有效值作为表达式
            expr = next(iter(kwargs.values()), "")

        if not expr:
            return "错误: 缺少待计算的表达式"

        expr = str(expr).strip()
        # 安全正则过滤：仅允许数字、数学符号、白名单函数名及空白
        if not re.match(r"^[0-9\.\+\-\*\/\(\)\,\s\^a-zA-Z_]+$", expr):
            return f"错误: 表达式包含不安全字符"

        # 语法替换 ^ 为 **
        python_expr = expr.replace("^", "**")

        try:
            result = eval(python_expr, {"__builtins__": {}}, self.SAFE_NAMES)
            return str(round(result, 4) if isinstance(result, float) else result)
        except Exception as e:
            return f"计算错误 ({expr}): {str(e)}"
