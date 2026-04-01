"""
@FileName: embedding_config.py
@Description: 
@Author: HiPeng
@Time: 2026/3/31 12:32
"""
from pydantic import Field, SecretStr
from bak.base_config import ProviderSettings

class EmbeddingProviderConfig(ProviderSettings):
    """嵌入模型配置

    环境变量示例 (.env):
        EMBED_BASE_URL=https://api.openai.com/v1
        EMBED_API_KEY=sk-xxx
        EMBED_MODEL_NAME=text-embedding-3-small
    """

    base_url: str = Field(default="")
    api_key: SecretStr = Field(default=SecretStr(""))
    model_name: str = Field(default="text-embedding-3-small")

    device: str = Field(default="gpu", description="推理设备: cpu/gpu/cuda")
    normalize_embeddings: bool = Field(default=True)
    dimensions: int = Field(default=1536, ge=1)

    timeout: int = Field(default=60, ge=1)
    max_retries: int = Field(default=3, ge=0, le=10)

    model_config = ProviderSettings.model_config.model_copy(
        update={"env_prefix": "EMBED_"}
    )