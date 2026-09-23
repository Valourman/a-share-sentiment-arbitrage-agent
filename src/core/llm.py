import logging
import os
from typing import Any, Dict, Generator, List, Optional, Union
from openai import OpenAI
from src.core.config import AgentConfig, global_config
from src.core.exceptions import LLMException
from src.core.message import Message

logger = logging.getLogger(__name__)


class HelloAgentsLLM:
    """
    Hello Agents 统一大模型中枢网关
    具备多服务商智能兼容能力 (OpenAI, DeepSeek, Zhipu, ModelScope, Ollama, VLLM)
    提供标准化消息转换、参数推断、流式输出与异常兜底
    """
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or global_config
        self.client: Optional[OpenAI] = None
        self.provider: str = "unknown"
        self._init_client()

    def _auto_detect_provider(self, base_url: Optional[str], api_key: Optional[str]) -> str:
        """根据 Base URL 与 API Key 智能推断服务商类型"""
        if not base_url:
            return "openai"
        url_lower = base_url.lower()
        if "11434" in url_lower or "ollama" in url_lower:
            return "ollama"
        if "8000" in url_lower or "vllm" in url_lower:
            return "vllm"
        if "deepseek" in url_lower:
            return "deepseek"
        if "bigmodel.cn" in url_lower or "zhipu" in url_lower:
            return "zhipu"
        if "modelscope" in url_lower:
            return "modelscope"
        return "openai_compatible"

    def _init_client(self) -> None:
        api_key = self.config.openai_api_key
        base_url = self.config.openai_base_url

        self.provider = self._auto_detect_provider(base_url, api_key)

        # 针对本地推理引擎 (Ollama/VLLM) 自动填充伪密钥
        if not api_key and self.provider in ["ollama", "vllm"] and base_url:
            api_key = "local_no_key_required"

        if api_key and base_url:
            try:
                self.client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=self.config.timeout_seconds,
                )
            except Exception as e:
                logger.warning(f"HelloAgentsLLM 客户端初始化失败: {e}")

    @property
    def is_available(self) -> bool:
        """检查底层 LLM 客户端与凭证是否就绪"""
        return self.client is not None

    def _format_messages(
        self, messages: List[Union[Message, Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """标准化格式化消息列表为 OpenAI API 契约"""
        formatted = []
        for msg in messages:
            if isinstance(msg, Message):
                formatted.append(msg.to_openai_dict())
            elif isinstance(msg, dict):
                formatted.append(msg)
            else:
                formatted.append({"role": "user", "content": str(msg)})
        return formatted

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
        支持标准 Message 对象列表或原始字典列表
        """
        if not self.is_available:
            raise LLMException(
                "HelloAgentsLLM 未就绪：缺少 OPENAI_API_KEY 或可解析的模型服务端点配置。"
            )

        formatted_messages = self._format_messages(messages)
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
            raise LLMException(f"LLM 接口调用失败: {str(e)}") from e

    def stream_chat(
        self,
        messages: List[Union[Message, Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """流式输出生成接口"""
        if not self.is_available:
            raise LLMException("HelloAgentsLLM 未就绪。")

        formatted_messages = self._format_messages(messages)
        request_kwargs: Dict[str, Any] = {
            "model": model or self.config.default_model,
            "messages": formatted_messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "stream": True,
            **kwargs,
        }
        try:
            stream = self.client.chat.completions.create(**request_kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as e:
            raise LLMException(f"流式生成异常: {str(e)}") from e
