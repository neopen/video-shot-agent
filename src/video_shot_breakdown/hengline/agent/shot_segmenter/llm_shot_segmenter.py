"""
@FileName: llm_shot_generator.py
@Description: 基于LLM的镜头生成器
@Author: HengLine
@Github: https://github.com/HengLine/video-shot-agent
@Time: 2026/1/26 17:35
"""
import json
import re
from typing import Optional, List

from video_shot_breakdown.hengline.agent.base_agent import BaseAgent
from video_shot_breakdown.hengline.agent.script_parser.script_parser_models import ParsedScript, SceneInfo, GlobalMetadata
from video_shot_breakdown.hengline.agent.shot_segmenter.base_shot_segmenter import BaseShotSegmenter
from video_shot_breakdown.hengline.agent.shot_segmenter.rule_shot_segmenter import RuleShotSegmenter
from video_shot_breakdown.hengline.agent.shot_segmenter.shot_segmenter_models import ShotSequence, ShotInfo, ShotType
from video_shot_breakdown.hengline.hengline_config import HengLineConfig
from video_shot_breakdown.logger import info, error


class LLMShotSegmenter(BaseShotSegmenter, BaseAgent):
    """基于LLM的分镜拆分器"""

    def __init__(self, llm_client, config: Optional[HengLineConfig]):
        super().__init__(config)
        self.llm_client = llm_client
        self.prop_registry = {}  # 通用道具注册表 {prop_key: {name, first_shot, occurrences}}

    def split(self, parsed_script: ParsedScript, global_metadata: GlobalMetadata) -> ShotSequence:
        """使用LLM拆分剧本"""
        info(f"使用LLM拆分分镜，剧本: {parsed_script.title}")

        all_shots = []
        current_time = 0.0
        # 每个新剧本重置道具追踪器
        self.prop_registry = {}

        # 设置剧本引用
        script_ref = {
            "title": parsed_script.title or "未命名剧本",
            "total_elements": parsed_script.stats.get("total_elements", 0),
            "original_duration": parsed_script.stats.get("total_duration", 0.0)
        }

        # 为每个场景调用LLM
        for scene_idx, scene in enumerate(parsed_script.scenes):
            try:
                scene_shots = self._split_scene_with_llm(scene, current_time, len(all_shots))
                all_shots.extend(scene_shots)

                # 更新当前时间
                if scene_shots:
                    current_time = scene_shots[-1].start_time + scene_shots[-1].duration

            except Exception as e:
                error(f"场景{scene.id}分镜失败: {str(e)}")
                # 降级到规则拆分
                rule_splitter = RuleShotSegmenter(self.config)
                fallback_shots = rule_splitter.split_scene(scene, current_time, len(all_shots))
                all_shots.extend(fallback_shots)

        # 构建序列
        shot_sequence = ShotSequence(
            script_reference=script_ref,
            shots=all_shots
        )

        # 后处理
        return self._post_process(shot_sequence)


    def _register_prop(self, prop_name: str, prop_value: str, shot_id: str):
        """注册或验证道具一致性"""
        prop_key = f"{prop_name}:{prop_value}"  # 用名称+值作为key

        if prop_key not in self.prop_registry:
            # 首次出现，注册
            self.prop_registry[prop_key] = {
                "name": prop_name,
                "value": prop_value,
                "first_shot": shot_id,
                "occurrences": [shot_id]
            }
            return prop_value
        else:
            # 已存在，记录出现
            self.prop_registry[prop_key]["occurrences"].append(shot_id)
            return self.prop_registry[prop_key]["value"]  # 返回已注册的值

    def _extract_props_from_description(self, description: str, shot_id: str) -> str:
        """从描述中提取所有可能的道具并验证一致性"""
        # 1. 提取书名号内的内容（《》）
        book_pattern = r'《([^》]+)》'
        book_matches = re.findall(book_pattern, description)
        for book_title in book_matches:
            consistent_title = self._register_prop("book_title", book_title, shot_id)
            if consistent_title != book_title:
                description = description.replace(f"《{book_title}》", f"《{consistent_title}》")

        # 2. 提取引号内的关键文字（" "或' '）
        quote_pattern = r'["\']([ ^ "\']+)["\']'
        quote_matches = re.findall(quote_pattern, description)
        for quote_text in quote_matches:
            if len(quote_text) > 10:  # 较长文本可能是台词
                consistent_quote = self._register_prop("dialogue", quote_text, shot_id)
                if consistent_quote != quote_text:
                    description = description.replace(f'"{quote_text}"', f'"{consistent_quote}"')
                    description = description.replace(f"'{quote_text}'", f"'{consistent_quote}'")

        # 3. 提取可能的道具名称（基于上下文）
        prop_indicators = ["拿着", "捧着", "抱着", "翻开", "合上", "递", "放", "holding", "carrying", "with a"]
        words = description.split()
        for i, word in enumerate(words):
            if any(indicator in word for indicator in prop_indicators) and i + 1 < len(words):
                potential_prop = words[i + 1].strip('，。,.!?；')
                if len(potential_prop) > 1 and potential_prop not in ["他", "她", "它", "the", "a", "an"]:
                    # 注册道具
                    consistent_prop = self._register_prop("prop_name", potential_prop, shot_id)
                    if consistent_prop != potential_prop:
                        description = description.replace(potential_prop, consistent_prop)

        # 4. 提取数字日期（如"下周三"）
        date_pattern = r'(下周[一二三四五六日]|next\s+\w+)'
        date_matches = re.findall(date_pattern, description)
        for date_text in date_matches:
            consistent_date = self._register_prop("date", date_text, shot_id)
            if consistent_date != date_text:
                description = description.replace(date_text, consistent_date)

        return description

    def _split_scene_with_llm(self, scene: SceneInfo, start_time: float, shot_offset: int) -> List[ShotInfo]:
        """使用LLM拆分单个场景"""
        # 准备元素列表文本
        elements_list = "\n".join([
            f"{i + 1}. [{elem.type}] {elem.character or '场景'}: {elem.content[:50]}... (时长: {elem.duration}秒)"
            for i, elem in enumerate(scene.elements)
        ])

        # 准备提示词
        user_prompt = self._get_prompt_template("shot_segmenter_user").format(
            location=scene.location,
            time_of_day=scene.time_of_day or "未指定",
            description=scene.description or "无描述",
            elements_list=elements_list
        )

        system_prompt = self._get_prompt_template("shot_segmenter_system")

        # 调用LLM
        response = self._call_llm_chat_with_retry(self.llm_client, system_prompt, user_prompt)

        # 解析响应
        shots_data = self._parse_ai_response(response, scene.id, start_time, shot_offset)

        return shots_data

    def _parse_ai_response(self, response: str, scene_id: str, start_time: float, shot_offset: int) -> List[ShotInfo]:
        """解析LLM响应并验证道具一致性"""
        shots_data = json.loads(response)

        shots = []
        current_time = start_time

        for i, shot_data in enumerate(shots_data):
            shot_id = self._generate_shot_id(shot_offset + i)

            # 提取并验证道具一致性
            original_desc = shot_data.get("description", "")
            validated_desc = self._extract_props_from_description(original_desc, shot_id)

            if original_desc != validated_desc:
                info(f"道具一致性修正：shot {shot_id} 描述已统一")

            shot = ShotInfo(
                id=shot_id,
                scene_id=scene_id,
                description=validated_desc,  # 使用验证后的描述
                start_time=round(current_time, 2),
                duration=shot_data.get("duration", 3.0),
                shot_type=ShotType(shot_data.get("shot_type", "medium_shot")),
                main_character=shot_data.get("main_character"),
                element_ids=shot_data.get("element_ids", []),
                confidence=0.8  # LLM结果默认置信度
            )

            shots.append(shot)
            current_time += shot.duration

        return shots
