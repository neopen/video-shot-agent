"""
@FileName: medium_term_memory.py
@Description: 中期记忆 - 基于LangChain的摘要记忆
@Author: HiPeng
@Time: 2026/4/1
"""
import json
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime

from langchain.memory import ConversationSummaryMemory
from langchain.prompts import PromptTemplate
from langchain.llms.base import BaseLLM

from penshot.logger import debug, info, error
from penshot.neopen.tools.memory.memory_models import MemoryConfig
from penshot.neopen.tools.result_storage_tool import create_result_storage


class MediumTermMemory:
    """中期记忆 - 基于LangChain的摘要记忆，支持文件持久化"""

    # 默认摘要提示词
    DEFAULT_SUMMARY_PROMPT = PromptTemplate(
        input_variables=["summary", "new_lines"],
        template="""逐步总结对话内容，将之前的总结与新的对话内容融合。

            当前总结:
            {summary}
            
            新的对话内容:
            {new_lines}
            
            请生成更新后的总结（保持简洁，突出重点）:"""
        )

    def __init__(self, llm: BaseLLM, config: MemoryConfig, script_id: str):
        self.llm = llm
        self.config = config
        self.script_id = script_id

        # 创建摘要记忆（纯内存，不依赖Redis）
        self.memory = ConversationSummaryMemory(
            llm=llm,
            memory_key="summary",
            input_key="input",
            output_key="output"
        )

        # 设置 max_token_limit（通过自定义提示词实现）
        self.max_token_limit = config.medium_term_max_tokens
        self._setup_summary_prompt(config.medium_term_summary_prompt)

        # 阶段摘要缓存
        self._stage_summaries: Dict[str, str] = {}

        # 文件持久化路径
        self.persist_path = None
        if config.medium_term_persist_path:
            self.persist_path = Path(config.medium_term_persist_path) / script_id
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self._load_from_file()  # 启动时加载
            self.storage = create_result_storage(base_output_dir=config.medium_term_persist_path)

        debug(f"初始化中期记忆: script={script_id}, max_tokens={config.medium_term_max_tokens}, "
              f"persist={self.persist_path is not None}")

    def _setup_summary_prompt(self, custom_prompt: Optional[str] = None):
        """设置摘要提示词"""
        if custom_prompt:
            # 使用自定义提示词
            self.memory.prompt = PromptTemplate(
                input_variables=["summary", "new_lines"],
                template=custom_prompt
            )
        else:
            # 使用默认提示词，并加入 token 限制
            template = f"""逐步总结对话内容，将之前的总结与新的对话内容融合。
                注意：总结应保持在 {self.max_token_limit} tokens 以内。
                
                当前总结:
                {{summary}}
                
                新的对话内容:
                {{new_lines}}
                
                请生成更新后的总结:"""

            self.memory.prompt = PromptTemplate(
                input_variables=["summary", "new_lines"],
                template=template
            )

    def add(self, stage_name: str, content: str, metadata: Optional[Dict] = None):
        """添加阶段内容"""
        # 检查内容长度，如果超过限制则先截断
        if len(content) > self.max_token_limit * 4:  # 粗略估算
            content = content[:self.max_token_limit * 4]

        # 保存到摘要记忆
        self.memory.save_context(
            {"input": f"阶段: {stage_name}"},
            {"output": content}
        )

        # 缓存阶段摘要
        if metadata and metadata.get("keep_full"):
            self._stage_summaries[stage_name] = content

        # 持久化到文件
        self._persist_to_file()

        debug(f"添加阶段内容: {stage_name}, 长度={len(content)}")

    def get_summary(self) -> str:
        """获取整体摘要"""
        variables = self.memory.load_memory_variables({})
        summary = variables.get("summary", "")

        # 如果摘要过长，进行截断
        if len(summary) > self.max_token_limit * 2:
            summary = summary[:self.max_token_limit * 2] + "..."

        return summary

    def get_stage_summary(self, stage_name: str) -> Optional[str]:
        """获取特定阶段摘要"""
        return self._stage_summaries.get(stage_name)

    def clear(self):
        """清空摘要"""
        # ConversationSummaryMemory 的 clear 方法
        if hasattr(self.memory, 'clear'):
            self.memory.clear()
        else:
            # 手动清空
            self.memory.buffer = ""
            if hasattr(self.memory, 'chat_memory'):
                self.memory.chat_memory.clear()

        self._stage_summaries.clear()

        # 删除持久化文件
        if self.persist_path:
            summary_file = self.persist_path / "summary.json"
            if summary_file.exists():
                summary_file.unlink()

        debug("清空中期记忆")

    def _persist_to_file(self):
        """持久化到文件"""
        if not self.persist_path:
            return

        try:
            summary = self.get_summary()
            data = {
                "script_id": self.script_id,
                "summary": summary,
                "stage_summaries": self._stage_summaries,
                "updated_at": datetime.now().isoformat(),
                "max_tokens": self.max_token_limit
            }
            self.storage.save_json_result(self.script_id, data, f"summary_{datetime.now().strftime('%Y%m%d%H')}.json")

        except Exception as e:
            error(f"持久化摘要失败: {e}")

    def _load_from_file(self):
        """从文件加载"""
        if not self.persist_path:
            return

        try:
            summary_file = self.persist_path / "summary.json"
            if not summary_file.exists():
                return

            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复摘要内容
            if data.get("summary"):
                # 将摘要添加到记忆（通过模拟对话）
                self.memory.save_context(
                    {"input": "恢复历史摘要"},
                    {"output": data["summary"]}
                )

            # 恢复阶段摘要
            self._stage_summaries = data.get("stage_summaries", {})

            info(f"加载摘要文件: {summary_file}, 阶段数={len(self._stage_summaries)}")
        except Exception as e:
            error(f"加载摘要文件失败: {e}")

    def export_summary(self) -> Dict[str, Any]:
        """导出摘要（用于调试或迁移）"""
        return {
            "script_id": self.script_id,
            "summary": self.get_summary(),
            "stage_summaries": self._stage_summaries,
            "stats": self.get_stats()
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        summary = self.get_summary()
        return {
            "type": "medium_term",
            "summary_length": len(summary),
            "max_tokens": self.max_token_limit,
            "stages_count": len(self._stage_summaries),
            "summary_preview": summary[:100] if summary else "",
            "persisted": self.persist_path is not None,
            "persist_path": str(self.persist_path) if self.persist_path else None
        }