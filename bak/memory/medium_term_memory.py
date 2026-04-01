"""
@FileName: medium_term_memory.py
@Description: 中期记忆 - 摘要记忆 + 阶段缓存
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/3/30 13:07
"""
import time
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Optional, List, Any

from langchain.memory import ConversationSummaryMemory


class MediumTermMemory:
    """中期记忆 - 基于摘要，支持阶段缓存"""

    def __init__(self, llm, max_stages: int = 50, summary_max_tokens: int = 1000):
        """
        初始化中期记忆

        Args:
            llm: 语言模型实例
            max_stages: 最大阶段数
            summary_max_tokens: 摘要最大token数
        """
        self.llm = llm
        self.max_stages = max_stages
        self.summary_max_tokens = summary_max_tokens

        self.summary_memory = ConversationSummaryMemory(
            llm=llm,
            memory_key="summary"
        )

        # 阶段记忆缓存
        self.stage_memories: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # 全局摘要
        self.global_summary: Optional[str] = None
        self.global_summary_updated_at: Optional[float] = None

    def summarize_stage(self, stage_name: str, content: str, metadata: Optional[Dict] = None) -> str:
        """生成阶段摘要"""
        # 生成摘要
        self.summary_memory.save_context(
            {"input": f"阶段: {stage_name}"},
            {"output": content}
        )

        summary = self.summary_memory.buffer

        # 存储阶段摘要
        self.stage_memories[stage_name] = {
            "summary": content[:self.summary_max_tokens],
            "full_content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "timestamp_epoch": time.time()
        }

        # 限制阶段数量
        while len(self.stage_memories) > self.max_stages:
            oldest_key, _ = self.stage_memories.popitem(last=False)

        # 移动到最后
        self.stage_memories.move_to_end(stage_name)

        return summary

    def get_stage_summary(self, stage_name: str) -> Optional[str]:
        """获取阶段摘要"""
        if stage_name in self.stage_memories:
            # 更新访问时间
            self.stage_memories.move_to_end(stage_name)
            return self.stage_memories[stage_name]["summary"]
        return None

    def get_stage_full(self, stage_name: str) -> Optional[str]:
        """获取阶段完整内容"""
        if stage_name in self.stage_memories:
            return self.stage_memories[stage_name]["full_content"]
        return None

    def get_stage_metadata(self, stage_name: str) -> Optional[Dict]:
        """获取阶段元数据"""
        if stage_name in self.stage_memories:
            return self.stage_memories[stage_name]["metadata"]
        return None

    def get_all_stages(self) -> List[str]:
        """获取所有阶段名称"""
        return list(self.stage_memories.keys())

    def get_recent_stages(self, n: int = 5) -> List[Dict]:
        """获取最近N个阶段"""
        recent = list(self.stage_memories.items())[-n:]
        return [
            {
                "stage_name": name,
                "summary": data["summary"],
                "timestamp": data["timestamp"]
            }
            for name, data in recent
        ]

    def update_global_summary(self, new_content: str) -> str:
        """更新全局摘要"""
        if self.global_summary:
            combined = f"{self.global_summary}\n\n{new_content}"
        else:
            combined = new_content

        self.summary_memory.save_context(
            {"input": "全局摘要更新"},
            {"output": combined}
        )

        self.global_summary = self.summary_memory.buffer
        self.global_summary_updated_at = time.time()

        return self.global_summary

    def get_global_summary(self) -> Optional[str]:
        """获取全局摘要"""
        return self.global_summary

    def clear_stage(self, stage_name: str) -> bool:
        """清除指定阶段"""
        if stage_name in self.stage_memories:
            del self.stage_memories[stage_name]
            return True
        return False

    def clear_all(self) -> None:
        """清空所有阶段记忆"""
        self.stage_memories.clear()
        self.global_summary = None
        self.global_summary_updated_at = None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "stage_count": len(self.stage_memories),
            "max_stages": self.max_stages,
            "global_summary_exists": self.global_summary is not None,
            "global_summary_age": time.time() - self.global_summary_updated_at if self.global_summary_updated_at else None,
            "stages": list(self.stage_memories.keys())
        }
