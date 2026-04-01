"""
@FileName: memory_manager.py
@Description: 统一记忆管理器 - 支持任务级隔离
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/3/30 13:10
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict

from penshot.neopen.tools.memory.medium_term_memory import MediumTermMemory
from penshot.neopen.tools.memory.short_term_memory import ShortTermMemory


class MemoryType(str, Enum):
    """记忆类型枚举"""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    AUTO = "auto"  # 自动选择


@dataclass
class MemoryEntry:
    """记忆条目"""
    key: str
    value: Any
    memory_type: MemoryType
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_access: float = field(default_factory=time.time)


class TaskMemory:
    """单个任务的记忆空间"""

    def __init__(self, task_id: str, short_term_size: int = 20, short_term_ttl: int = 3600,
                 medium_term_max: int = 50, llm=None, embeddings=None):
        """
        初始化任务级记忆

        Args:
            task_id: 任务ID
            short_term_size: 短期记忆容量
            short_term_ttl: 短期记忆TTL
            medium_term_max: 中期记忆最大阶段数
            llm: 语言模型
            embeddings: 嵌入模型
        """
        self.task_id = task_id
        self.short_term = ShortTermMemory(max_size=short_term_size, ttl_seconds=short_term_ttl)
        self.medium_term = MediumTermMemory(llm=llm, max_stages=medium_term_max) if llm else None
        self._access_stats: Dict[str, MemoryEntry] = {}

    def remember(self, key: str, value: Any, memory_type: MemoryType = MemoryType.SHORT,
                 metadata: Optional[Dict] = None) -> None:
        """存储记忆"""
        metadata = metadata or {}
        entry = MemoryEntry(
            key=key,
            value=value,
            memory_type=memory_type,
            metadata=metadata
        )
        self._access_stats[key] = entry

        if memory_type == MemoryType.MEDIUM and self.medium_term:
            self.medium_term.summarize_stage(key, str(value), metadata)
        else:
            self.short_term.add(key, value, metadata)

    def recall(self, key: str, memory_type: Optional[MemoryType] = None, default: Any = None) -> Optional[Any]:
        """回忆记忆"""
        if key in self._access_stats:
            self._access_stats[key].access_count += 1
            self._access_stats[key].last_access = time.time()

        if memory_type:
            if memory_type == MemoryType.MEDIUM and self.medium_term:
                return self.medium_term.get_stage_summary(key) or default
            else:
                return self.short_term.get(key) or default

        # 自动降级查找
        value = self.short_term.get(key)
        if value is not None:
            return value

        if self.medium_term:
            value = self.medium_term.get_stage_summary(key)
            if value is not None:
                return value

        return default

    def clear(self) -> None:
        """清空任务记忆"""
        self.short_term.clear()
        if self.medium_term:
            self.medium_term.clear_all()
        self._access_stats.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "short_term": self.short_term.get_stats(),
            "medium_term": self.medium_term.get_stats() if self.medium_term else {"enabled": False, "stage_count": 0},
            "access_stats": {
                "total_keys": len(self._access_stats),
                "most_accessed": sorted(
                    self._access_stats.values(),
                    key=lambda x: x.access_count,
                    reverse=True
                )[:5]
            }
        }
