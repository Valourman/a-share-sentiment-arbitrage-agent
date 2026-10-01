import re
import json
from typing import Type, TypeVar, Optional, Tuple
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

class RobustAgentParser:
    """
    生产级 Agent 自愈解析器:
    1. 多阶段正则剥除 Markdown 代码块及前后置冗余自然语言
    2. Pydantic 强类型与字段级约束校验
    3. 精确捕获字段路径与错误信息，构建高效的自愈 Prompt
    """

    @classmethod
    def _extract_json_candidate(cls, text: str) -> str:
        """从非结构化或半结构化大模型回复中提取最可能的 JSON 字符串"""
        if not text:
            return ""

        stripped = text.strip()
        # 策略 0: 若原始文本本身已完整闭合，直接返回避免多余正则开销
        if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
            return stripped

        # 策略 1: 优先提取 Markdown ```json ... ``` 或 ``` ... ``` 代码块内部文本
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if code_block:
            return code_block.group(1).strip()

        # 策略 2: 提取文本中最外层闭合结构（优先匹配 JSON 顶层对象 {...}，兼顾顶层数组 [...]）
        json_obj = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if json_obj:
            return json_obj.group(1).strip()

        return text.strip()

    @classmethod
    def parse_or_build_feedback(
        cls, raw_llm_output: Optional[str], model_cls: Type[T]
    ) -> Tuple[Optional[T], Optional[str]]:
        if not raw_llm_output or not raw_llm_output.strip():
            return None, "模型输出为空。请严格按照预定义的 JSON Schema 生成合法的 JSON 格式数据。"

        # 步骤 1: 容错清理与正则提取
        cleaned = cls._extract_json_candidate(raw_llm_output)

        # 步骤 2: 基础语法检查（清洗尾随逗号并允许字面量控制字符）
        try:
            cleaned_str = re.sub(r",\s*([\]}])", r"\1", cleaned)
            data = json.loads(cleaned_str, strict=False)
        except json.JSONDecodeError as e:
            return None, (
                f"JSON 语法解析失败: {str(e)}。\n"
                f"待解析内容片段: {cleaned[:120]}...\n"
                "请确保仅返回严格合法的纯 JSON 字符串，不要携带任何多余的自然语言解释或 Markdown 格式以外的杂质。"
            )

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
                + "\n\n请严格按照上述字段规范修正并重新输出合法的 JSON。"
            )
            return None, feedback
