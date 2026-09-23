from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具自描述参数元数据"""
    name: str = Field(description="参数名称")
    type: str = Field(default="string", description="参数 JSON Schema 类型: string, integer, number, boolean, array, object")
    description: str = Field(description="参数业务含义解释")
    required: bool = Field(default=True, description="是否必填")
    default: Optional[Any] = Field(default=None, description="默认值")


class ToolResult(BaseModel):
    """标准工具执行结果对象"""
    success: bool = True
    output: Any = ""
    error: Optional[str] = None


class Tool(ABC):
    """
    Hello Agents 规范标准工具抽象基类
    要求所有外部感知、API采集、量化计算与存储均封装为具象化 Tool，并提供统一的 OpenAI Tools 契约
    """
    name: str = ""
    description: str = ""
    parameters: Any = []

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """具体工具逻辑执行入口"""
        pass

    def to_openai_schema(self) -> Dict[str, Any]:
        """将当前工具参数转换为标准 OpenAI Function Calling 的 JSON Schema 字典"""
        if isinstance(self.parameters, dict):
            params_dict = self.parameters
            if "type" not in params_dict:
                params_dict = {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [k for k, v in self.parameters.items() if isinstance(v, dict) and v.get("required", False)],
                }
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": params_dict,
                },
            }

        properties: Dict[str, Any] = {}
        required_list: List[str] = []

        for p in self.parameters:
            field_def: Dict[str, Any] = {
                "type": p.type,
                "description": p.description,
            }
            if p.default is not None:
                field_def["default"] = p.default
            properties[p.name] = field_def
            if p.required:
                required_list.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required_list,
                },
            },
        }


BaseTool = Tool

