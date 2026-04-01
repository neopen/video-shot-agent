"""
@FileName: base.py
@Description: 
@Author: HiPeng
@Time: 2026/3/31 12:31
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    """Provider 配置基类：支持环境变量读取"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略未定义的环境变量
        case_sensitive=False,
    )

    @classmethod
    def with_prefix(cls, prefix: str):
        """动态设置环境变量前缀（用于不同 provider 隔离）"""
        return type(
            f"{cls.__name__}WithPrefix",
            (cls,),
            {"model_config": SettingsConfigDict(
                **cls.model_config.model_dump(),
                env_prefix=prefix
            )}
        )