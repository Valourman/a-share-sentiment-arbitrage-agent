import logging
from typing import Any, Dict, List, Optional, Union
from openai import OpenAI
from src.core.config import AgentConfig, global_config
from src.core.message import Message, RoleType

logger = logging.getLogger(__name__)


class HelloAgentsLLM:
    """
    Hello Agents 统一大模型中枢网关
    具备多服务商兼容能力，标准化消息处理与错误兜底
    """
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or global_config
        self.client: Optional[OpenAI] = None
        self._init_client()

    def _init_client(self):
        if self.config.openai_api_key and self.config.openai_base_url:
            try:
                self.client = OpenAI(
                    api_key=self.config.openai_api_key,
                    base_url=self.config.openai_base_url,
                    timeout=self.config.timeout_seconds,
                )
            except Exception as e:
                logger.warning(f"HelloAgentsLLM 客户端初始化失败: {e}")

    @property
    def is_available(self) -> bool:
        """检查底层 LLM 客户端与凭证是否就绪"""
        return self.client is not None

    def chat(
        self,
        messages: List[Union[Message, Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> str:
        """
        统一对话生成接口
        支持传入标准 Message 对象列表或原始字典列表
        """
        if not self.is_available:
            raise RuntimeError(
                "HelloAgentsLLM 未就绪：缺少 OPENAI_API_KEY 或 OPENAI_BASE_URL 配置。"
            )

        formatted_messages = []
        for msg in messages:
            if isinstance(msg, Message):
                formatted_messages.append(msg.to_openai_dict())
            elif isinstance(msg, dict):
                formatted_messages.append(msg)
            else:
                formatted_messages.append({"role": "user", "content": str(msg)})

        request_kwargs: Dict[str, Any] = {
            "model": model or self.config.default_model,
            "messages": formatted_messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            **kwargs,
        }
        if tools:
            request_kwargs["tools"] = tools

        try:
            response = self.client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"HelloAgentsLLM 调用异常: {e}")
            raise e
