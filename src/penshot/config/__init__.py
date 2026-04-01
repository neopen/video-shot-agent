"""
@FileName: __init__.py.py
@Description: 
@Author: HiPeng
@Time: 2026/3/6 22:34
"""
from penshot import ShotConfig
from penshot.config.config_models import EmbeddingBaseConfig, LLMBaseConfig

__all__ = [
    "EmbeddingBaseConfig",
    "LLMBaseConfig",
    "ShotConfig"
]
