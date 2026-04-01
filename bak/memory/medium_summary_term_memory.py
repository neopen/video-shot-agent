"""
@FileName: medium_term_memory.py
@Description: 中期记忆 - 摘要记忆 + 阶段缓存
@Author: HiPeng
@Time: 2026/3/30 13:07
"""
import time
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Optional, List, Any

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate


class MediumTermMemory:
    """中期记忆 - 基于摘要，支持阶段缓存"""

    # 默认摘要提示词模板
    DEFAULT_SUMMARY_PROMPT = PromptTemplate(
        input_variables=["summary", "new_lines"],
        template="""逐步总结以下对话内容，将之前的总结和新的对话整合成新的总结。

            当前总结:
            {summary}
            
            新内容:
            {new_lines}
            
            新的总结:"""
    )

    def __init__(self, llm, max_stages: int = 50, summary_max_tokens: int = 1000):
        """
        初始化中期记忆

        Args:
            llm: 语言模型实例
            max_stages: 最大阶段数
            summary_max_tokens: 摘要最大token数（用于截断）
        """
        self.llm = llm
        self.max_stages = max_stages
        self.summary_max_tokens = summary_max_tokens

        # ConversationSummaryMemory 不支持 max_token_limit 参数
        # 使用自定义的摘要链
        self.summary_chain = LLMChain(
            llm=llm,
            prompt=self.DEFAULT_SUMMARY_PROMPT
        )
        self._current_summary = ""

        # 阶段记忆缓存
        self.stage_memories: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # 全局摘要
        self.global_summary: Optional[str] = None
        self.global_summary_updated_at: Optional[float] = None

    def _truncate_by_tokens(self, text: str, max_tokens: int) -> str:
        """根据token数截断文本（粗略估算）"""
        if max_tokens <= 0:
            return ""
        # 粗略估算：中文约1.5字符/token，英文约0.75词/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len(text.split())
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 0.75)

        if estimated_tokens <= max_tokens:
            return text

        # 按比例截断
        ratio = max_tokens / estimated_tokens
        cut_length = int(len(text) * ratio)
        return text[:cut_length] + "..."

    def _update_summary(self, new_content: str) -> str:
        """更新摘要"""
        if not self._current_summary:
            # 首次摘要
            self._current_summary = new_content
        else:
            # 生成新摘要
            try:
                result = self.summary_chain.predict(
                    summary=self._current_summary,
                    new_lines=new_content
                )
                self._current_summary = result
            except Exception:
                # 降级：简单拼接
                self._current_summary = f"{self._current_summary}\n{new_content}"

        # 截断过长的摘要
        if self.summary_max_tokens > 0:
            self._current_summary = self._truncate_by_tokens(
                self._current_summary,
                self.summary_max_tokens
            )

        return self._current_summary

    def summarize_stage(self, stage_name: str, content: str, metadata: Optional[Dict] = None) -> str:
        """生成阶段摘要"""
        # 生成摘要
        summary = self._update_summary(content)

        # 存储阶段摘要（截断）
        truncated_content = self._truncate_by_tokens(content, self.summary_max_tokens)

        self.stage_memories[stage_name] = {
            "summary": truncated_content,
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

        # 使用摘要链生成新的全局摘要
        try:
            result = self.summary_chain.predict(
                summary=self.global_summary or "",
                new_lines=new_content
            )
            self.global_summary = result
        except Exception:
            self.global_summary = combined

        # 截断
        if self.summary_max_tokens > 0:
            self.global_summary = self._truncate_by_tokens(
                self.global_summary,
                self.summary_max_tokens
            )

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
        self._current_summary = ""
        self.global_summary = None
        self.global_summary_updated_at = None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "stage_count": len(self.stage_memories),
            "max_stages": self.max_stages,
            "summary_max_tokens": self.summary_max_tokens,
            "current_summary_length": len(self._current_summary),
            "global_summary_exists": self.global_summary is not None,
            "global_summary_age": time.time() - self.global_summary_updated_at if self.global_summary_updated_at else None,
            "stages": list(self.stage_memories.keys())
        }

    @property
    def buffer(self) -> str:
        """兼容属性，返回当前摘要"""
        return self._current_summary
