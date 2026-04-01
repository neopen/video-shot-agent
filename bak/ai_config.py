"""
@FileName: ai_config.py
@Description: 
@Author: HiPeng
@Time: 2026/3/31 12:34
"""
from pydantic import BaseModel, Field

from bak.embedding_config import EmbeddingProviderConfig
from bak.llm_config import LLMProviderConfig


class AIConfig(BaseModel):
    """AI 服务总配置（纯数据容器，不负责加载逻辑）"""

    llm_config: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    embed_config: EmbeddingProviderConfig = Field(default_factory=EmbeddingProviderConfig)

    # 业务开关
    cinematic_knowledge: bool = Field(default=True, description="注入影视领域知识")
    pacing_principles: bool = Field(default=True, description="启用节奏控制原则")

    class Config:
        # 序列化时自动展开嵌套（方便 API 返回）
        json_schema_extra = {
            "example": {
                "llm_config": {"model_name": "gpt-4o", "temperature": 0.1},
                "cinematic_knowledge": True
            }
        }
