import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


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
        """从当前环境变量自动加载配置"""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            default_model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=float(os.getenv("TEMPERATURE", "0.1")),
            max_retries=int(os.getenv("MAX_RETRIES", "2")),
            timeout_seconds=float(os.getenv("TIMEOUT_SECONDS", "30.0")),
        )


# 全局默认单例配置
global_config = AgentConfig.from_env()
