import logging
import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

load_dotenv()


def _env_float(key: str, default: float) -> float:
    """安全解析浮点型环境变量，脏值回退默认值并告警"""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(f"环境变量 {key}={raw!r} 不是合法浮点数，回退默认值 {default}")
        return default


def _env_int(key: str, default: int) -> int:
    """安全解析整型环境变量，脏值回退默认值并告警"""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"环境变量 {key}={raw!r} 不是合法整数，回退默认值 {default}")
        return default


class AgentConfig(BaseModel):
    """集中式智能体运行时配置中心，支持环境变量自适应注入"""
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI 或兼容服务端点 API 密钥")
    openai_base_url: Optional[str] = Field(default=None, description="模型服务端点 Base URL")
    default_model: str = Field(default="gpt-4o-mini", description="默认大模型名称")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="采样温度")
    max_retries: int = Field(default=2, ge=0, description="接口自愈重试最大次数")
    timeout_seconds: float = Field(default=30.0, gt=0, description="请求超时阈值 (秒)")

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从当前环境变量自动加载配置（脏值自动回退默认值）"""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            default_model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=_env_float("TEMPERATURE", 0.1),
            max_retries=_env_int("MAX_RETRIES", 2),
            timeout_seconds=_env_float("TIMEOUT_SECONDS", 30.0),
        )


# 全局默认单例配置
global_config = AgentConfig.from_env()
