import json
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

class RobustAgentParser:
    """
    演示面试核心话术:
    1. 前置 JSON 提取与修复
    2. Pydantic 强类型与字段级校验
    3. 捕获精确错误构建自愈 Prompt (Self-Correction)
    """

    @classmethod
    def parse_or_build_feedback(cls, raw_llm_output: str, model_cls: Type[T]) -> tuple[T | None, str | None]:
        # 步骤 1: 容错清理 (去除大模型常带的 ```json ... ``` 标记)
        cleaned = raw_llm_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        # 步骤 2: 基础语法检查
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            return None, f"JSON 语法解析失败: {str(e)}。请确保返回严格合法的纯 JSON 字符串，不要携带多余解释。"

        # 步骤 3: Pydantic 语义与字段约束校验
        try:
            instance = model_cls.model_validate(data)
            return instance, None
        except ValidationError as e:
            # 步骤 4: 提取结构化错误，形成下一次反思自愈的精确输入
            error_details = []
            for err in e.errors():
                loc = " -> ".join(str(p) for p in err.get("loc", []))
                msg = err.get("msg", "")
                error_details.append(f"字段 [{loc}] 校验不通过: {msg}")
            
            feedback = (
                "你上一轮返回的 JSON 不符合预定义的结构要求，请根据以下具体错误进行修正后重新输出：\n"
                + "\n".join(f"- {item}" for item in error_details)
            )
            return None, feedback
