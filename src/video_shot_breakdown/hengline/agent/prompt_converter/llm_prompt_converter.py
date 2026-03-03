"""
@FileName: llm_prompt_converter.py
@Description: 
@Author: HengLine
@Github: https://github.com/HengLine/video-shot-agent
@Time: 2026/1/26 23:36
"""
from typing import Optional, Dict

from video_shot_breakdown.hengline.agent.base_agent import BaseAgent
from video_shot_breakdown.hengline.agent.prompt_converter.base_prompt_converter import BasePromptConverter
from video_shot_breakdown.hengline.agent.prompt_converter.prompt_converter_models import AIVideoPrompt, AIVideoInstructions
from video_shot_breakdown.hengline.agent.prompt_converter.template_prompt_converter import TemplatePromptConverter
from video_shot_breakdown.hengline.agent.script_parser.script_parser_models import GlobalMetadata
from video_shot_breakdown.hengline.agent.video_splitter.video_splitter_models import FragmentSequence, VideoFragment
from video_shot_breakdown.hengline.hengline_config import HengLineConfig
from video_shot_breakdown.hengline.language_manage import get_language
from video_shot_breakdown.logger import info, error


class LLMPromptConverter(BasePromptConverter, BaseAgent):
    """基于LLM的提示词转换器"""

    def __init__(self, llm_client, config: Optional[HengLineConfig]):
        super().__init__(config)
        self.llm_client = llm_client

    def convert(self, fragment_sequence: FragmentSequence, global_metadata: GlobalMetadata) -> AIVideoInstructions:
        """使用LLM转换提示词"""
        info(f"使用LLM转换提示词，片段数: {len(fragment_sequence.fragments)}")

        prompts = []
        project_info = {
            "title": fragment_sequence.source_info.get("title", "AI视频项目"),
            "total_fragments": fragment_sequence.stats.get("fragment_count", 0),
            "total_duration": fragment_sequence.stats.get("total_duration", 0.0)
        }

        for fragment in fragment_sequence.fragments:
            try:
                prompt = self._convert_fragment_with_llm(fragment, fragment_sequence.source_info, global_metadata)
                prompts.append(prompt)
            except Exception as e:
                error(f"片段{fragment.id}转换失败: {str(e)}")
                # 降级到模板转换
                template_converter = TemplatePromptConverter(self.config)
                fallback_prompt = template_converter.convert_fragment(fragment)
                prompts.append(fallback_prompt)

        instructions = AIVideoInstructions(
            project_info=project_info,
            fragments=prompts
        )
        return self.post_process(instructions)

    def _convert_fragment_with_llm(self, fragment: VideoFragment, source_info: Dict, global_metadata: GlobalMetadata) -> AIVideoPrompt:
        """使用LLM转换单个片段 - 生成双语提示词（英文+原始语言）"""

        # 检测原始剧本语言
        original_language = self._detect_original_language(fragment)

        scene_context = source_info.get("scene_context", {})

        # 格式化全局信息
        global_context = self._format_global_context(global_metadata, scene_context)

        # 准备提示词
        user_prompt = self._get_prompt_template("prompt_converter_user")

        prompt_template = user_prompt.format(
            fragment_id=fragment.id,
            description=fragment.description,
            duration=fragment.duration,
            character=fragment.continuity_notes.get("main_character", ""),
            location=fragment.continuity_notes.get("location", ""),
            original_language=original_language,
            overall_weather=source_info.get("overall_weather", ""),
            dm_model=self.config.target_model.value,
            video_style=self.config.default_style.value,
            max_length=self.config.max_prompt_length,
            min_length=self.config.min_prompt_length,
            global_context=global_context
        )

        # 调用LLM
        system_prompt = self._get_prompt_template("prompt_converter_system")
        result = self._call_llm_parse_with_retry(self.llm_client, system_prompt, prompt_template)

        # 获取生成的提示词
        english_prompt = result.get("prompt", "")
        original_prompt = result.get("original_prompt", "")

        # 合并双语提示词：英文在前，原始语言在后
        combined_prompt = f"{english_prompt}\n\n{original_prompt}"

        return AIVideoPrompt(
            fragment_id=fragment.id,
            prompt=combined_prompt,
            negative_prompt=result.get("negative_prompt", self.config.default_negative_prompt),
            duration=fragment.duration,
            model=self.config.target_model.value,
            style=result.get("style_hint")
        )

    def _detect_original_language(self, fragment: VideoFragment) -> str:
        """检测原始剧本语言"""
        # 可以从fragment的metadata中获取
        if hasattr(fragment, 'metadata') and fragment.metadata:
            return fragment.metadata.get("original_language", "zh")

        # 默认中文
        return get_language().value
