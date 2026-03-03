"""
@FileName: llm_script_parser.py
@Description: 
@Author: HengLine
@Github: https://github.com/HengLine/video-shot-agent
@Time: 2026/1/9 21:23
"""
import time
from abc import ABC
from typing import Any, Dict

from video_shot_breakdown.hengline.agent.script_parser.script_parser_models import GlobalMetadata
from video_shot_breakdown.hengline.client.client_factory import llm_chat_complete
from video_shot_breakdown.hengline.prompts.prompts_manager import prompt_manager
from video_shot_breakdown.hengline.tools.json_parser_tool import parse_json_response


class BaseAgent(ABC):

    def _get_prompt_template(self, key_name) -> str:
        """创建LLM提示词模板"""
        return prompt_manager.get_name_prompt(key_name)

    def _parse_llm_response(self, ai_response: str) -> Dict[str, Any]:
        """ 转换LLM响应，必要时需要重写该方法 """
        return parse_json_response(ai_response)

    def _call_llm_parse_with_retry(self, llm, system_prompt: str, user_prompt, max_retries: int = 2) -> Dict[str, Any] | None:
        """
            调用LLM，返回转换后的对象（支持重试）
            返回 dict
        """
        return self._parse_llm_response(self._call_llm_chat_with_retry(llm, system_prompt, user_prompt, max_retries))

    def _call_llm_chat_with_retry(self, llm, system_prompt: str, user_prompt, max_retries: int = 2) -> str | None:
        """
            调用LLM，直接返回json字符串（支持重试）
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        for attempt in range(max_retries):
            try:
                return llm_chat_complete(llm, messages)

            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"LLM调用失败: {e}")
                time.sleep(1)

    def _call_llm_with_retry(self, llm, prompt: str, max_retries: int = 2) -> Any | None:
        """调用LLM，支持重试"""
        for attempt in range(max_retries):
            try:
                return llm.invoke(prompt)

            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"LLM调用失败: {e}")
                time.sleep(1)

    def _format_global_metadata(self, global_metadata: GlobalMetadata) -> str:
        """将全局metadata格式化为易读的文本"""
        if not global_metadata:
            return "无特殊关键信息"

        sections = []

        # 关键道具
        if hasattr(global_metadata, 'key_props') and global_metadata.key_props:
            props = [f"{p.name}（{p.description}）" for p in global_metadata.key_props[:5]]
            sections.append(f"核心道具：{', '.join(props)}")

        # 角色服装
        if hasattr(global_metadata, 'character_outfits') and global_metadata.character_outfits:
            outfits = [f"{o.character}：{o.description}" for o in global_metadata.character_outfits]
            sections.append(f"角色服装：{', '.join(outfits)}")

        # 关键台词
        if hasattr(global_metadata, 'key_dialogues') and global_metadata.key_dialogues:
            dialogues = [f"{d.character}：\"{d.content}\"" for d in global_metadata.key_dialogues[:3]]
            sections.append(f"关键台词：{'; '.join(dialogues)}")

        # 重要日期
        if hasattr(global_metadata, 'key_dates') and global_metadata.key_dates:
            dates = [f"{d.date}（{d.context}）" for d in global_metadata.key_dates]
            sections.append(f"重要日期：{', '.join(dates)}")

        # 重要场景
        if hasattr(global_metadata, 'key_locations') and global_metadata.key_locations:
            locations = [l.name for l in global_metadata.key_locations]
            sections.append(f"重要场景：{', '.join(locations)}")

        # 连续性要点
        if hasattr(global_metadata, 'continuity_notes') and global_metadata.continuity_notes:
            sections.append(f"连续性要点：{global_metadata.continuity_notes}")

        return "\n    ".join(sections) if sections else "无特殊关键信息"

    def _format_global_context(self, global_metadata: GlobalMetadata, scene_context: Dict) -> str:
        """格式化全局上下文信息"""
        sections = []

        # 1. 关键道具
        if "key_props" in global_metadata and global_metadata["key_props"]:
            props = []
            for prop in global_metadata["key_props"][:5]:
                if isinstance(prop, dict):
                    props.append(f"{prop.get('name', '')}: {prop.get('description', '')}")
                else:
                    props.append(str(prop))
            if props:
                sections.append(f"关键道具：{'; '.join(props)}")

        # 2. 关键台词
        if "key_dialogues" in global_metadata and global_metadata["key_dialogues"]:
            dialogues = []
            for d in global_metadata["key_dialogues"][:3]:
                if isinstance(d, dict):
                    dialogues.append(f"{d.get('character', '')}: \"{d.get('content', '')}\"")
                else:
                    dialogues.append(str(d))
            if dialogues:
                sections.append(f"关键台词：{'; '.join(dialogues)}")

        # 3. 重要日期
        if "key_dates" in global_metadata and global_metadata["key_dates"]:
            dates = [str(d) for d in global_metadata["key_dates"][:3]]
            if dates:
                sections.append(f"重要日期：{', '.join(dates)}")

        # 4. 场景上下文摘要
        if scene_context and "scenes" in scene_context:
            scene_summary = []
            for scene_id, scene_data in list(scene_context["scenes"].items())[:3]:
                chars = ", ".join(list(scene_data.get("main_characters", [])))
                scene_summary.append(f"{scene_id}: {chars}")
            if scene_summary:
                sections.append(f"场景角色：{'; '.join(scene_summary)}")

        # 5. 连续性要点
        if "continuity_notes" in global_metadata:
            sections.append(f"连续性要点：{global_metadata['continuity_notes']}")

        return "\n    ".join(sections) if sections else "无特殊全局信息"