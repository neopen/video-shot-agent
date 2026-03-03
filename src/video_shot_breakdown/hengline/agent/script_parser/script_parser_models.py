"""
@FileName: script_parser_models.py
@Description:  剧本解析相关模型
@Author: HengLine
@Github: https://github.com/HengLine/video-shot-agent
@Time: 2026/1/19 21:44
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal

from pydantic import BaseModel, Field

from video_shot_breakdown.hengline.agent.base_models import ElementType


class CharacterInfo(BaseModel):
    """角色信息模型"""
    name: str = Field(..., description="角色名称")
    gender: str = Field(..., description="角色性别")
    role: str = Field(..., description="角色类型（主角、配角等）")
    # 核心特征（可选）
    description: Optional[str] = Field(
        default=None,
        description="简化的角色描述（如有）"
    )

    # MVP中只保留最关键的特征
    key_traits: List[str] = Field(
        default_factory=list,
        description="关键特征列表，如外貌、性格等"
    )


class BaseElement(BaseModel):
    """剧本元素基类 - 所有类型元素的共同字段"""
    id: str = Field(..., description="元素唯一标识，格式：elem_001")
    type: Literal[ElementType.DIALOGUE, ElementType.ACTION, ElementType.SCENE] = Field(
        ...,
        description="元素类型：对话/动作/场景描述"
    )
    sequence: int = Field(
        ...,
        description="全局顺序编号，从1开始，表示在剧本中的出现顺序"
    )

    # 通用时间信息
    duration: float = Field(
        default=3.0,
        ge=0.5,
        description="预估持续时间（秒），基于简单规则估算"
    )

    # 元数据
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="解析置信度，0-1之间"
    )

    # 核心内容
    content: str = Field(..., description="元素内容文本")

    # 角色信息（可选）
    character: Optional[str] = Field(
        default=None,
        description="关联的角色名（对话必填，动作可选）"
    )
    target_character: Optional[str] = Field(
        default=None,
        description="针对的目标角色（如有）"
    )

    description: str = Field(default=None, description="其他的描述文本")

    intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="动作或语气等的强度等级，0-1之间"
    )
    emotion: str = Field(
        default="neutral",
        description="伴随情绪：neutral/happy/angry/sad/fear"
    )


class SceneInfo(BaseModel):
    """场景信息模型"""
    id: str = Field(..., description="场景唯一ID，格式：scene_001")
    location: str = Field(..., description="场景地点")
    # 简化的描述（可选）
    description: Optional[str] = Field(
        default=None,
        description="场景简要描述（如有）"
    )

    # 时间信息
    time_of_day: Optional[str] = Field(
        default=None,
        description="时间（如有）：day/night/dawn/dusk"
    )

    # 扁平化的元素数组（按sequence排序）
    elements: List[BaseElement] = Field(
        default_factory=list,
        description="所有剧本元素，按出现顺序排列"
    )

########################### 全局元数据模型 - 存储全剧关键信息，供后续阶段使用 ###############################
class KeyProp(BaseModel):
    """关键道具信息"""
    name: str
    description: str
    appears_in: List[str] = []


class CharacterOutfit(BaseModel):
    """角色服装信息"""
    character: str
    description: str
    color: Optional[str] = None


class KeyDialogue(BaseModel):
    """关键台词"""
    character: str
    content: str
    scene_id: str
    importance: str = "medium"  # high/medium/low


class KeyDate(BaseModel):
    """重要日期"""
    date: str
    context: str
    scene_id: str


class KeyLocation(BaseModel):
    """重要地点"""
    name: str
    description: str
    appears_in: List[str] = []


class GlobalMetadata(BaseModel):
    """全局元数据 - 存储全剧关键信息"""
    key_props: List[KeyProp] = []
    character_outfits: List[CharacterOutfit] = []
    key_dialogues: List[KeyDialogue] = []
    key_dates: List[KeyDate] = []
    key_locations: List[KeyLocation] = []
    continuity_notes: str = ""


############################ 剧本解析结果模型 - 包含核心数据和统计信息 ###############################
class ParsedScript(BaseModel):
    """剧本解析结果 - 阶段1输出"""

    # 元数据
    metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "parsed_at": datetime.now().isoformat(),
            "version": "mvp_1.0",
            "source_type": "unknown"
        },
        description="解析元数据"
    )

    # 核心数据
    title: Optional[str] = Field(
        default=None,
        description="剧本标题（如能识别）"
    )

    # 简化的核心数据
    characters: List[CharacterInfo] = Field(
        default_factory=list,
        description="识别到的角色列表"
    )

    scenes: List[SceneInfo] = Field(
        default_factory=list,
        description="场景列表，按出现顺序排列"
    )

    # 统计数据
    stats: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_elements": 0,
            "total_duration": 0.0,
            "dialogue_count": 0,
            "action_count": 0,
            "completeness_score": 0
        },
        description="解析统计数据"
    )

    global_metadata: GlobalMetadata = Field(default_factory=GlobalMetadata)

    def to_dict(self) -> dict:
        """转换为字典表示"""
        return self.model_dump()

    def get_Elements_by_type(self, element_type: ElementType) -> List[BaseElement]:
        return [
            elem
            for scene in self.scenes
            for elem in scene.elements
            if elem.type == element_type
        ]

    def is_valid(self):
        return len(self.scenes) > 0
