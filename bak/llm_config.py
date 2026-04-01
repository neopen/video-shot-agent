"""
@FileName: llm_config.py
@Description: 
@Author: HiPeng
@Time: 2026/3/31 12:32
"""
from pydantic import Field, SecretStr

from bak.base_config import ProviderSettings


class LLMProviderConfig(ProviderSettings):
    """LLM 提供商配置

    环境变量示例 (.env):
        LLM_BASE_URL=https://api.openai.com/v1
        LLM_API_KEY=sk-xxx
        LLM_MODEL_NAME=gpt-4o
    """

    base_url: str = Field(default="", description="API 基础地址")
    api_key: SecretStr = Field(default=SecretStr(""), description="API 密钥")
    model_name: str = Field(default="gpt-4o", description="模型名称")

    timeout: int = Field(default=60, ge=1, description="请求超时(秒)")
    response_format: str = Field(default="json_object", description="响应格式")

    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="温度参数")
    max_tokens: int = Field(default=2000, ge=1, description="最大 token 数")

    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_delay: int = Field(default=1, ge=0, le=60, description="重试间隔(秒)")

    # 关键字段：指定环境变量前缀
    model_config = ProviderSettings.model_config.model_copy(
        update={"env_prefix": "LLM_"}
    )