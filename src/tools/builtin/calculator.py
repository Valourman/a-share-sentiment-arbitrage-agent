import ast
import math
import operator
from typing import Any
from src.tools.base import Tool, ToolParameter


class CalculatorTool(Tool):
    """
    Hello Agents 内置安全数学计算器工具
    支持基础四则运算、幂运算以及常用数学函数（sqrt, sin, cos, log 等）

    安全实现：基于 ast.parse 的节点类型白名单求值，禁止属性访问与下标等
    任意代码执行路径，并对幂运算施加幅值上限以防御天文数字 DoS。
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

    # 幂运算幅值上限：底数绝对值与指数均不得超过该值，防御 CPU/内存 DoS
    _MAX_POW_BASE = 1e6
    _MAX_POW_EXP = 1e4

    # 二元运算符白名单
    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    # 一元运算符白名单
    _UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def _eval_node(self, node: ast.AST) -> Any:
        """在 AST 节点白名单内递归求值，任何越界节点立即拒绝"""
        if isinstance(node, ast.Expression):
            return self._eval_node(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise ValueError("仅支持数字常量")
        if isinstance(node, ast.Name):
            if node.id in self.SAFE_NAMES:
                return self.SAFE_NAMES[node.id]
            raise ValueError(f"未知标识符: {node.id}")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self._BIN_OPS:
                raise ValueError("不支持的运算符")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if op_type is ast.Pow:
                # 幂运算幅值防护，避免天文数字幂导致的 CPU/内存 DoS
                if abs(left) > self._MAX_POW_BASE or abs(right) > self._MAX_POW_EXP:
                    raise ValueError("幂运算底数或指数超出安全上限")
            return self._BIN_OPS[op_type](left, right)
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self._UNARY_OPS:
                raise ValueError("不支持的一元运算符")
            return self._UNARY_OPS[op_type](self._eval_node(node.operand))
        if isinstance(node, ast.Call):
            # 仅允许调用白名单内的具名函数，禁止任何属性/下标访问
            if not isinstance(node.func, ast.Name):
                raise ValueError("仅支持直接调用白名单函数")
            if node.func.id not in self.SAFE_NAMES or not callable(self.SAFE_NAMES[node.func.id]):
                raise ValueError(f"未知函数: {node.func.id}")
            if node.keywords:
                raise ValueError("不支持关键字参数")
            args = [self._eval_node(arg) for arg in node.args]
            return self.SAFE_NAMES[node.func.id](*args)
        # Attribute / Subscript / Tuple / List 等一切其他节点均拒绝
        raise ValueError("表达式包含不支持的结构")

    def execute(self, expression: str = "", **kwargs: Any) -> Any:
        # 兼容关键字参数与普通入参
        expr = expression or kwargs.get("input", "") or kwargs.get("query", "")
        if not expr and kwargs:
            # 取 kwargs 中的第一个有效值作为表达式
            expr = next(iter(kwargs.values()), "")

        if not expr:
            return "错误: 缺少待计算的表达式"

        expr = str(expr).strip()
        # 语法替换 ^ 为 **（幂运算）
        python_expr = expr.replace("^", "**")

        try:
            tree = ast.parse(python_expr, mode="eval")
        except SyntaxError:
            return "错误: 表达式语法不合法"

        try:
            result = self._eval_node(tree)
            if isinstance(result, float):
                # 浮点结果做合理性检查并保留 4 位精度
                if math.isinf(result) or math.isnan(result):
                    return "错误: 计算结果溢出或未定义"
                return str(round(result, 4))
            return str(result)
        except ZeroDivisionError:
            return "错误: 除数不能为零"
        except (ValueError, TypeError, OverflowError) as e:
            # 不回显原始表达式，避免辅助攻击者探测
            return f"错误: {e}"
        except Exception:
            return "错误: 表达式无法求值"
