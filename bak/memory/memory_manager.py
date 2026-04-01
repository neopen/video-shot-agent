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
from typing import Optional, Any, Dict, List

from penshot.logger import error, info
from penshot.neopen.tools.memory.long_term_memory import LongTermMemory
from penshot.neopen.tools.memory.script_memory import TaskMemory


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


class MemoryManager:
    """统一记忆管理器 - 支持任务级隔离"""

    # 全局长期记忆（按任务ID隔离）
    _global_long_term: Dict[str, LongTermMemory] = {}
    _long_term_lock = None

    def __init__(
            self,
            llm,
            embeddings,
            enable_long_term: bool = False,
            short_term_size: int = 20,
            short_term_ttl: int = 3600,
            medium_term_max: int = 50,
            long_term_collection: str = "penshot_memory"
    ):
        """
        初始化记忆管理器

        Args:
            llm: 语言模型实例
            embeddings: 嵌入模型
            enable_long_term: 是否启用长期记忆
            short_term_size: 短期记忆容量
            short_term_ttl: 短期记忆TTL（秒）
            medium_term_max: 中期记忆最大阶段数
            long_term_collection: 长期记忆集合名
        """
        self.llm = llm
        self.embeddings = embeddings
        self.enable_long_term = enable_long_term
        self.long_term_collection = long_term_collection

        # 任务级记忆存储
        self._task_memories: Dict[str, TaskMemory] = {}

        # 全局长期记忆工厂
        self._long_term_memories: Dict[str, LongTermMemory] = {}

        # 配置参数
        self.short_term_size = short_term_size
        self.short_term_ttl = short_term_ttl
        self.medium_term_max = medium_term_max

    def _get_or_create_task_memory(self, task_id: str) -> TaskMemory:
        """获取或创建任务记忆"""
        if task_id not in self._task_memories:
            self._task_memories[task_id] = TaskMemory(
                task_id=task_id,
                short_term_size=self.short_term_size,
                short_term_ttl=self.short_term_ttl,
                medium_term_max=self.medium_term_max,
                llm=self.llm,
                embeddings=self.embeddings
            )
        return self._task_memories[task_id]

    def _get_long_term_memory(self, task_id: str) -> Optional[LongTermMemory]:
        """获取长期记忆（按任务隔离）"""
        if not self.enable_long_term:
            return None

        if task_id not in self._long_term_memories:
            # 为每个任务创建独立的长期记忆集合
            collection_name = f"{self.long_term_collection}_{task_id}"
            self._long_term_memories[task_id] = LongTermMemory(
                embeddings=self.embeddings,
                collection_name=collection_name,
                persist_directory=f"data/output/memory/{task_id}"
            )
        return self._long_term_memories[task_id]

    def set_task_id(self, task_id: str) -> None:
        """
        设置当前任务ID（用于工作流节点）

        Args:
            task_id: 任务ID
        """
        self._current_task_id = task_id

    def remember(
            self,
            key: str,
            value: Any,
            memory_type: MemoryType = MemoryType.SHORT,
            metadata: Optional[Dict] = None,
            tags: Optional[List[str]] = None,
            task_id: Optional[str] = None
    ) -> None:
        """
        存储记忆

        Args:
            key: 记忆键
            value: 记忆值
            memory_type: 记忆类型
            metadata: 元数据
            tags: 标签
            task_id: 任务ID（可选，默认使用当前任务）
        """
        # 获取任务ID
        tid = task_id or getattr(self, '_current_task_id', None)
        if not tid:
            error(f"未设置任务ID，无法存储记忆: {key}")
            return

        metadata = metadata or {}
        if tags:
            metadata["tags"] = tags

        task_memory = self._get_or_create_task_memory(tid)

        if memory_type == MemoryType.LONG:
            # 长期记忆
            long_term = self._get_long_term_memory(tid)
            if long_term:
                long_term.store(str(value), {"key": key, **metadata})
        elif memory_type == MemoryType.MEDIUM:
            # 中期记忆
            task_memory.remember(key, value, memory_type, metadata)
        else:
            # 短期记忆
            task_memory.remember(key, value, MemoryType.SHORT, metadata)


    def recall(
            self,
            key: str,
            memory_type: Optional[MemoryType] = None,
            default: Any = None,
            task_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        回忆记忆

        Args:
            key: 记忆键
            memory_type: 指定记忆类型，None时自动降级查找
            default: 默认返回值
            task_id: 任务ID（可选，默认使用当前任务）
        """
        # 获取任务ID
        tid = task_id or getattr(self, '_current_task_id', None)
        if not tid:
            # 如果没有设置任务ID，返回默认值，不报错
            info(f"未设置任务ID，无法回忆记忆: {key}")
            return default

        task_memory = self._get_or_create_task_memory(tid)

        try:
            # 指定类型查找
            if memory_type:
                if memory_type == MemoryType.LONG:
                    long_term = self._get_long_term_memory(tid)
                    if long_term:
                        results = long_term.retrieve(key, k=1)
                        if results:
                            return results[0]["content"]
                    return default
                else:
                    return task_memory.recall(key, memory_type, default)

            # 自动降级查找
            # 1. 短期记忆
            value = task_memory.recall(key, MemoryType.SHORT)
            if value is not None:
                return value

            # 2. 中期记忆
            value = task_memory.recall(key, MemoryType.MEDIUM)
            if value is not None:
                return value

            # 3. 长期记忆
            long_term = self._get_long_term_memory(tid)
            if long_term:
                results = long_term.retrieve(key, k=1)
                if results:
                    return results[0]["content"]

        except Exception as e:
            error(f"记忆检索异常: {e}")

        return default


    def get_context(self, query: str, max_tokens: int = 2000, task_id: Optional[str] = None) -> str:
        """获取融合上下文（按任务隔离）"""
        tid = task_id or getattr(self, '_current_task_id', None)
        if not tid:
            return ""

        task_memory = self._get_or_create_task_memory(tid)
        contexts = []
        current_tokens = 0

        # 短期上下文（最高优先级）
        recent = task_memory.short_term.get_recent(5)
        for item in recent:
            ctx = f"[当前] {item['key']}: {str(item['value'])[:200]}"
            contexts.append(ctx)
            current_tokens += len(ctx) // 2

        # 中期上下文
        if task_memory.medium_term:
            stages = task_memory.medium_term.get_recent_stages(3)
            for stage in stages:
                ctx = f"[阶段] {stage['stage_name']}: {stage['summary'][:200]}"
                if current_tokens + len(ctx) // 2 <= max_tokens:
                    contexts.append(ctx)
                    current_tokens += len(ctx) // 2

        # 长期上下文（相关性检索）
        if self.enable_long_term and current_tokens < max_tokens:
            long_term = self._get_long_term_memory(tid)
            if long_term:
                long_results = long_term.retrieve(query, k=2)
                for r in long_results:
                    ctx = f"[历史] {r['content'][:200]}"
                    if current_tokens + len(ctx) // 2 <= max_tokens:
                        contexts.append(ctx)
                        current_tokens += len(ctx) // 2

        return "\n".join(contexts)

    def get_stats(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            task_id: 任务ID（可选，默认使用当前任务）

        Returns:
            统计信息字典
        """
        tid = task_id or getattr(self, '_current_task_id', None)
        if not tid:
            return {
                "error": "未设置任务ID",
                "total_tasks": len(self._task_memories),
                "tasks": list(self._task_memories.keys())
            }

        if tid in self._task_memories:
            return self._task_memories[tid].get_stats()

        return {
            "task_id": tid,
            "short_term": {"current_size": 0, "buffer_size": 0, "max_size": self.short_term_size},
            "medium_term": {"stage_count": 0, "max_stages": self.medium_term_max},
            "long_term": {"enabled": self.enable_long_term, "total_stored": 0},
            "access_stats": {"total_keys": 0, "most_accessed": []}
        }

    def get_most_accessed(self, n: int = 5, task_id: Optional[str] = None) -> List[Dict]:
        """
        获取最常访问的记忆

        Args:
            n: 返回数量
            task_id: 任务ID（可选，默认使用当前任务）

        Returns:
            最常访问的记忆列表
        """
        tid = task_id or getattr(self, '_current_task_id', None)
        if not tid:
            return []

        if tid not in self._task_memories:
            return []

        task_memory = self._task_memories[tid]
        sorted_entries = sorted(
            task_memory._access_stats.values(),
            key=lambda x: x.access_count,
            reverse=True
        )[:n]

        return [
            {
                "key": e.key,
                "access_count": e.access_count,
                "last_access": e.last_access,
                "memory_type": e.memory_type
            }
            for e in sorted_entries
        ]

    def get_all_task_stats(self) -> Dict[str, Any]:
        """
        获取所有任务的统计信息

        Returns:
            所有任务的统计信息
        """
        return {
            "total_tasks": len(self._task_memories),
            "tasks": [
                {
                    "task_id": task_id,
                    "stats": memory.get_stats()
                }
                for task_id, memory in self._task_memories.items()
            ]
        }

    def clear_task_memory(self, task_id: str) -> None:
        """清空指定任务的所有记忆"""
        if task_id in self._task_memories:
            self._task_memories[task_id].clear()
            del self._task_memories[task_id]

        # 清理长期记忆
        if task_id in self._long_term_memories:
            try:
                self._long_term_memories[task_id].clear_all()
            except Exception as e:
                error(f"清理长期记忆失败: {e}")
            finally:
                del self._long_term_memories[task_id]

    def get_task_stats(self, task_id: str) -> Dict[str, Any]:
        """获取任务记忆统计"""
        stats = {"task_id": task_id}

        if task_id in self._task_memories:
            stats.update(self._task_memories[task_id].get_stats())

        if task_id in self._long_term_memories:
            stats["long_term"] = self._long_term_memories[task_id].get_stats()
        else:
            stats["long_term"] = {"enabled": self.enable_long_term}

        return stats

    def get_all_tasks(self) -> List[str]:
        """获取所有任务ID"""
        return list(self._task_memories.keys())

    # ========== 兼容旧接口 ==========

    def remember_short(self, key: str, value: Any, metadata: Optional[Dict] = None):
        """存储短期记忆（兼容）"""
        self.remember(key, value, MemoryType.SHORT, metadata)

    def recall_short(self, key: str, default: Any = None) -> Optional[Any]:
        """回忆短期记忆（兼容）"""
        return self.recall(key, MemoryType.SHORT, default)

    def remember_medium(self, key: str, value: Any, metadata: Optional[Dict] = None):
        """存储中期记忆（兼容）"""
        self.remember(key, value, MemoryType.MEDIUM, metadata)

    def recall_medium(self, key: str, default: Any = None) -> Optional[Any]:
        """回忆中期记忆（兼容）"""
        return self.recall(key, MemoryType.MEDIUM, default)
