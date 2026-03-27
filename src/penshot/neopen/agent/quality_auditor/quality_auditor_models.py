"""
@FileName: quality_auditor_models.py
@Description: 质量审核模型
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/1/19 22:58
"""
from datetime import datetime
from enum import Enum, unique
from typing import List, Optional, Any, Dict, Literal

from pydantic import Field, BaseModel

from penshot.neopen.agent.workflow.workflow_models import PipelineNode


@unique
class SeverityLevel(str, Enum):
    """违规严重程度"""
    INFO = "info"  # 信息级别，不影响执行
    WARNING = "warning"  # 警告级别，建议修复
    MODERATE = "moderate"  # 中度问题，需要调整
    MAJOR = "major"  # 主要问题，需要重新处理
    CRITICAL = "critical"  # 严重问题，需要人工干预
    ERROR = "error"  # 错误级别，无法继续


@unique
class AuditStatus(str, Enum):
    """质量审查状态枚举"""
    PASSED = "passed"  # 完全通过
    MINOR_ISSUES = "minor_issues"  # 轻微问题（警告级别）
    MODERATE_ISSUES = "moderate_issues"  # 中度问题（需要调整）
    MAJOR_ISSUES = "major_issues"  # 主要问题（需要重新处理）
    CRITICAL_ISSUES = "critical_issues"  # 严重问题（需要人工干预）
    FAILED = "failed"  # 完全失败
    NEEDS_HUMAN = "needs_human"  # 需要人工决策

    NEEDS_REVIEW = "needs_review"  # 需要审查
    WARNING = "warning"  # 有警告


class IssueType(str, Enum):
    """问题类型枚举 - 统一规范"""
    TRUNCATION = "truncation"  # 提示词截断
    SCENE = "scene"  # 场景引用错误
    WEATHER = "weather"  # 气象矛盾
    CHARACTER = "character"  # 角色不一致
    ACTION = "action"  # 动作不连贯
    DIALOGUE = "dialogue"  # 对话问题
    PROMPT = "prompt"  # 提示词质量问题
    DURATION = "duration"  # 时长不合理
    STYLE = "style"  # 风格不一致
    FRAGMENT = "fragment"  # 片段分隔或分镜问题
    MODEL = "model"  # 模型问题
    OTHER = "other"  # 其他问题


class RuleType(Enum):
    LLM_COHERENCE = ("llm_coherence", "LLM连贯性检查")
    DURATION_LIMIT = ("duration_limit", "片段时长限制")
    PROMPT_NOT_EMPTY = ("prompt_not_empty", "提示词非空")
    PROMPT_LENGTH = ("prompt_length", "提示词长度")
    FRAGMENT_COUNT = ("fragment_count", "片段数量")
    MODEL_SUPPORTED = ("model_supported", "模型支持")
    SCENE_MISSING = ("scene_missing", "场景缺失")
    SCENE_INSUFFICIENT = ("scene_insufficient", "场景不足")
    CHARACTER_MISSING = ("character_missing", "角色缺失")
    CHARACTER_INCONSISTENT = ("character_inconsistent", "角色不一致")
    DIALOGUE_MISSING = ("dialogue_missing", "对话缺失")
    ACTION_INSUFFICIENT = ("action_insufficient", "动作提取不足")

    def __init__(self, code, description):
        self.code = code
        self.description = description


class BasicViolation(BaseModel):
    """MVP违规记录"""
    rule_code: str = Field(..., description="规则编码")
    rule_name: str = Field(..., description="规则名称")
    description: str = Field(..., description="违规描述")
    issue_type: IssueType = Field(..., description="问题类型")
    severity: Literal[SeverityLevel.INFO, SeverityLevel.WARNING, SeverityLevel.ERROR,
    SeverityLevel.MAJOR, SeverityLevel.MODERATE, SeverityLevel.CRITICAL] = Field(
        default=SeverityLevel.WARNING,
        description="严重程度"
    )
    fragment_id: Optional[str] = Field(
        default=None,
        description="涉及的片段ID"
    )
    suggestion: Optional[str] = Field(
        default=None,
        description="改进建议"
    )


class QualityRepairParams(BaseModel):
    fix_needed: bool = Field(
        default=False,
        description="是否需要修复"
    )

    issue_count: int = Field(
        default=0,
        description="问题数量"
    )

    issue_types: List[IssueType] = Field(
        default_factory=list,
        description="修复类型"
    )

    fragments: List[str] = Field(
        default_factory=list,
        description="对应的片段ID集合"
    )

    suggestions: Dict[str, List[str]] = Field(
        default=None,
        description="修复建议"
    )

    severity_summary: Dict[str, int] = Field(
        default=None,
        description="严重程度摘要"
    )


class QualityAuditReport(BaseModel):
    """MVP质量审查报告"""

    # 元数据
    metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "audited_at": datetime.now().isoformat(),
            "version": "mvp_1.0",
            "auditor_type": "basic"
        }
    )

    # 项目信息
    project_info: Dict[str, Any] = Field(
        default_factory=lambda: {
            "title": "",
            "fragment_count": 0,
            "total_duration": 0.0
        }
    )

    # 审查状态
    status: AuditStatus = Field(
        default=AuditStatus.PASSED,
        description="审查状态：passed=通过, needs_revision=需要调整, failed=失败"
    )

    # 检查明细
    checks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="执行的检查项目"
    )

    # 违规记录
    violations: List[BasicViolation] = Field(
        default_factory=list,
        description="发现的违规问题"
    )

    # 统计数据
    stats: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_checks": 0,
            "passed_checks": 0,
            SeverityLevel.WARNING.value: 0,
            SeverityLevel.ERROR.value: 0,
            "fragments_checked": 0
        }
    )

    # 简单建议
    suggestions: List[str] = Field(
        default_factory=lambda: [
            "检查所有片段时长是否≤5秒",
            "确保没有空提示词"
        ]
    )

    # 最终结论
    conclusion: str = Field(
        default="审查通过，可以开始视频生成",
        description="审查结论"
    )

    score: float = Field(
        default=100.0,
        description="质量评分（0-100）"
    )

    detailed_analysis: Dict[str, Any] = Field(
        default=None,
        description="详细分析报告"
    )

    issues_source: Dict[PipelineNode, List[BasicViolation]] = Field(
        default=None,
        description="问题来源"
    )

    repair_params: Dict[PipelineNode, QualityRepairParams] = Field(
        default=None,
        description="修复参数"
    )
