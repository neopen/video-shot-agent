"""
@FileName: multi_agent_pipeline.py
@Description: 多智能体协作流程，负责协调各个智能体完成端到端的分镜生成
@Author: HiPeng
@Github: https://github.com/neopen/story-shot-agent
@Time: 2025/10 - 至今
"""
import asyncio
from typing import Dict, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END

from penshot.logger import debug, error, info, warning
from penshot.neopen.agent.script_parser_agent import ScriptParserAgent
from penshot.utils.log_utils import print_log_exception
from .workflow_decision import PipelineDecision
from .workflow_models import AgentStage, PipelineNode, PipelineState
from .workflow_nodes import WorkflowNodes
from .workflow_output_fixer import WorkflowOutputFixer
from .workflow_orchestrator import WorkflowOrchestrator
from .workflow_state_types import WorkflowState, InputState, ConfigState
from ..prompt_converter_agent import PromptConverterAgent
from ..quality_auditor_agent import QualityAuditorAgent
from ..shot_segmenter_agent import ShotSegmenterAgent
from ..video_splitter_agent import VideoSplitterAgent
from ...shot_config import ShotConfig


class MultiAgentPipeline:
    """多智能体协作流程"""

    def __init__(self, script_id, task_id, config: ShotConfig, task_manager):
        """
        初始化多智能体流程
        
        Args:
            script_id: 剧本ID
            config: 用户配置（LLM）
        """
        self.script_id = script_id
        self.task_id = task_id
        self.memory = MemorySaver()  # 状态记忆器
        self.config = config or ShotConfig()
        self.llm = self.config.get_llm_by_config()
        self.embeddings = self.config.get_embed_by_config()
        self.task_manager = task_manager
        self._init_agents()
        self.workflow = self._build_workflow()

    def _init_agents(self):
        """初始化各个智能体"""
        debug("初始化智能体组件")

        self.script_parser = ScriptParserAgent(llm=self.llm, config=self.config)
        self.shot_segmenter = ShotSegmenterAgent(llm=self.llm, config=self.config)
        self.video_splitter = VideoSplitterAgent(llm=self.llm, config=self.config)
        self.prompt_converter = PromptConverterAgent(llm=self.llm, config=self.config)
        self.quality_auditor = QualityAuditorAgent(llm=self.llm, config=self.config)

        # 初始化工作流节点集合
        self.workflow_nodes = WorkflowNodes(
            script_id=self.script_id,
            script_parser=self.script_parser,
            shot_segmenter=self.shot_segmenter,
            video_splitter=self.video_splitter,
            prompt_converter=self.prompt_converter,
            quality_auditor=self.quality_auditor,
            llm=self.llm,
            embeddings=self.embeddings,
            task_manager=self.task_manager
        )
        # 工作流决策函数
        self.decision_funcs = PipelineDecision()
        # 初始化修复器
        self.output_fixer = WorkflowOutputFixer()

    def _build_workflow(self):
        """使用 WorkflowOrchestrator 初始化基于LangGraph的工作流"""
        debug("使用 WorkflowOrchestrator 初始化LangGraph工作流")

        # 创建编排器
        orchestrator = WorkflowOrchestrator()

        # ========== 注册所有工作流节点 ==========
        orchestrator.add_node(
            PipelineNode.PARSE_SCRIPT.value,
            lambda graph_state: self.workflow_nodes.parse_script_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.SEGMENT_SHOT.value,
            lambda graph_state: self.workflow_nodes.split_shots_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.SPLIT_VIDEO.value,
            lambda graph_state: self.workflow_nodes.fragment_for_ai_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.CONVERT_PROMPT.value,
            lambda graph_state: self.workflow_nodes.generate_prompts_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.AUDIT_QUALITY.value,
            lambda graph_state: self.workflow_nodes.quality_audit_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.CONTINUITY_CHECK.value,
            lambda graph_state: self.workflow_nodes.continuity_check_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.ERROR_HANDLER.value,
            lambda graph_state: self.workflow_nodes.error_handler_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.GENERATE_OUTPUT.value,
            lambda graph_state: self.workflow_nodes.generate_output_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.HUMAN_INTERVENTION.value,
            lambda graph_state: self.workflow_nodes.human_intervention_node(graph_state)
        )

        orchestrator.add_node(
            PipelineNode.LOOP_CHECK.value,
            lambda graph_state: self.workflow_nodes.loop_check_node(graph_state)
        )

        # ========== 添加条件边（决策路由） ==========

        # 剧本解析后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.PARSE_SCRIPT.value,
            lambda graph_state: self.decision_funcs.decide_after_parsing(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.SEGMENT_SHOT.value,
                PipelineState.NEEDS_RETRY: PipelineNode.PARSE_SCRIPT.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value
            }
        )

        # 镜头拆分后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.SEGMENT_SHOT.value,
            lambda graph_state: self.decision_funcs.decide_after_splitting(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.LOOP_CHECK.value,
                PipelineState.NEEDS_RETRY: PipelineNode.SEGMENT_SHOT.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.SEGMENT_SHOT.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value
            }
        )

        # AI分段后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.SPLIT_VIDEO.value,
            lambda graph_state: self.decision_funcs.decide_after_fragmenting(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.LOOP_CHECK.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.SPLIT_VIDEO.value,
                PipelineState.NEEDS_RETRY: PipelineNode.SPLIT_VIDEO.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value
            }
        )

        # Prompt生成后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.CONVERT_PROMPT.value,
            lambda graph_state: self.decision_funcs.decide_after_prompts(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.LOOP_CHECK.value,
                PipelineState.VALID: PipelineNode.LOOP_CHECK.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.NEEDS_RETRY: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value
            }
        )

        # 循环检查节点的分支
        orchestrator.add_conditional_edge(
            PipelineNode.LOOP_CHECK.value,
            lambda graph_state: self.decision_funcs.decide_after_loop_check(graph_state),
            {
                PipelineNode.SEGMENT_SHOT: PipelineNode.SEGMENT_SHOT.value,
                PipelineNode.SPLIT_VIDEO: PipelineNode.SPLIT_VIDEO.value,
                PipelineNode.CONVERT_PROMPT: PipelineNode.CONVERT_PROMPT.value,
                PipelineNode.AUDIT_QUALITY: PipelineNode.AUDIT_QUALITY.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value,
            }
        )

        # 质量审查后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.AUDIT_QUALITY.value,
            lambda graph_state: self.decision_funcs.decide_after_audit(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.CONTINUITY_CHECK.value,
                PipelineState.VALID: PipelineNode.CONTINUITY_CHECK.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.NEEDS_RETRY: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value,
            }
        )

        # 连续性检查后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.CONTINUITY_CHECK.value,
            lambda graph_state: self.decision_funcs.decide_after_continuity(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.GENERATE_OUTPUT.value,
                PipelineState.VALID: PipelineNode.GENERATE_OUTPUT.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value
            }
        )

        # 错误处理后的分支（直接返回节点名称）
        orchestrator.add_conditional_edge(
            PipelineNode.ERROR_HANDLER.value,
            lambda graph_state: self.decision_funcs.decide_next_after_error(graph_state),
            {}
        )

        # 人工干预后的分支
        orchestrator.add_conditional_edge(
            PipelineNode.HUMAN_INTERVENTION.value,
            lambda graph_state: self.decision_funcs.decide_after_human(graph_state),
            {
                PipelineState.SUCCESS: PipelineNode.GENERATE_OUTPUT.value,
                PipelineState.VALID: PipelineNode.GENERATE_OUTPUT.value,
                PipelineState.NEEDS_RETRY: PipelineNode.PARSE_SCRIPT.value,
                PipelineState.NEEDS_REPAIR: PipelineNode.CONVERT_PROMPT.value,
                PipelineState.NEEDS_HUMAN: PipelineNode.HUMAN_INTERVENTION.value,
                PipelineState.ABORT: END,
                PipelineState.FAILED: PipelineNode.ERROR_HANDLER.value,
            }
        )

        # 结果生成后结束
        orchestrator.add_edge(PipelineNode.GENERATE_OUTPUT.value, END)

        # 构建工作流图
        orchestrator.build(state_schema=WorkflowState)

        # 验证工作流
        orchestrator.validate()

        # 编译工作流（添加记忆器）
        compiled_graph = orchestrator.graph.compile(checkpointer=self.memory)
        info("工作流构建完成")

        return compiled_graph

    async def run_process(self, raw_script: str, config: ShotConfig) -> Dict:
        """执行完整的工作流"""
        # 计算全局循环限制：所有节点最大循环次数之和
        total_node_max_loops = config.max_total_loops
        default_global_max_loops = total_node_max_loops * 2  # 2倍安全系数

        # 使用新的状态结构（组合方式）
        initial_state = WorkflowState(
            input=InputState(
                raw_script=raw_script,
                user_config=config,
                task_id=self.task_id,
                script_id=self.script_id,
            ),
            config=ConfigState(
                max_shot_duration=config.max_shot_duration,
                min_shot_duration=config.min_shot_duration,
                max_fragment_duration=config.max_fragment_duration,
                min_fragment_duration=config.min_fragment_duration,
                max_prompt_length=config.max_prompt_length,
                min_prompt_length=config.min_prompt_length,
            ),
        )
        
        # 设置执行状态
        initial_state.execution.current_stage = AgentStage.INIT
        initial_state.execution.current_node = PipelineNode.PARSE_SCRIPT
        initial_state.execution.global_max_loops = getattr(config, 'global_max_loops', default_global_max_loops)
        initial_state.execution.global_loop_exceeded = config.global_loop_exceeded
        initial_state.execution.loop_warning_issued = config.loop_warning_issued

        try:
            # 执行工作流
            debug(f"调用 workflow invoke()，任务ID: {self.task_id}")

            final_result = await self._enhanced_workflow_execution(initial_state)

            # 处理返回结果
            success = final_result.get("success", False)
            data = final_result.get("data")
            info(f"工作流执行完成，结果: success={success}, has_data={data is not None}")

            # 如果需要，可以添加额外的验证
            if success and data:
                self._validate_final_output(data)

            return final_result

        except Exception as e:
            error(f"执行工作流时出错: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "error": str(e),
                "data": None,
                "processing_stats": {
                    "error": "workflow_exception",
                    "exception_type": type(e).__name__,
                },
                "task_id": self.task_id,
                "workflow_status": "exception"
            }

    def _get_completed_stages(self, state) -> dict[str, Any]:
        """获取已完成的阶段列表和统计信息（支持字典和对象输入）"""
        try:
            if isinstance(state, dict):
                state_dict = state
            elif hasattr(state, 'dict'):
                state_dict = state.dict()
            elif hasattr(state, '__dict__'):
                state_dict = state.__dict__
            else:
                return {
                    "error": "unknown_state_type",
                    "completed_stages": [],
                    "stage_count": 0
                }

            stages = []

            parsed_script = state_dict.get('parsed_script')
            if parsed_script:
                stages.append("PARSER")

            shot_sequence = state_dict.get('shot_sequence')
            if shot_sequence:
                stages.append("SEGMENTER")

            fragment_sequence = state_dict.get('fragment_sequence')
            if fragment_sequence:
                stages.append("SPLITTER")

            instructions = state_dict.get('instructions')
            if instructions:
                stages.append("CONVERTER")

            audit_report = state_dict.get('audit_report')
            if audit_report:
                stages.append("AUDITOR")

            continuity_issues = state_dict.get('continuity_issues')
            if continuity_issues is not None:
                stages.append("CONTINUITY")

            current_node = state_dict.get('current_node')
            current_stage = state_dict.get('current_stage')

            if hasattr(current_node, 'value'):
                current_node = current_node.value
            if hasattr(current_stage, 'value'):
                current_stage = current_stage.value

            stats = {
                "completed_stages": stages,
                "stage_count": len(stages),
                "has_final_output": state_dict.get('final_output') is not None,
                "current_node": current_node,
                "current_stage": current_stage,
                "global_loops": state_dict.get('global_current_loops', 0),
                "global_max_loops": state_dict.get('global_max_loops', 0),
                "error_count": len(state_dict.get('error_messages', []))
            }

            last_audit_result = state_dict.get('last_audit_result')
            if last_audit_result:
                stats["audit"] = {
                    "score": last_audit_result.get('score', 0),
                    "status": last_audit_result.get('status'),
                    "passed_checks": last_audit_result.get('passed_checks', 0),
                    "total_checks": last_audit_result.get('total_checks', 0)
                }

            node_current_loops = state_dict.get('node_current_loops', {})
            if node_current_loops:
                loops_summary = {}
                for node, count in node_current_loops.items():
                    if hasattr(node, 'value'):
                        loops_summary[node.value] = count
                    else:
                        loops_summary[str(node)] = count
                stats["node_loops"] = loops_summary

            return stats

        except Exception as e:
            error(f"获取完成阶段时出错: {str(e)}")
            return {
                "error": f"无法获取阶段信息: {str(e)}",
                "completed_stages": [],
                "stage_count": 0
            }

    async def _enhanced_workflow_execution(self, initial_state: WorkflowState) -> Dict[str, Any]:
        """
        增强的工作流执行方法
        """
        try:
            debug("开始增强的工作流执行...")

            final_result = await asyncio.wait_for(
                self.output_fixer.enhanced_workflow_invoke(
                    self.workflow,
                    initial_state
                ),
                timeout=initial_state.input.timeout
            )

            if not self._validate_fixed_result(final_result):
                warning("工作流输出修复验证有问题，但继续返回结果")

            return self.output_fixer.parse_result_to_dict(final_result)

        except Exception as e:
            error(f"增强工作流执行失败: {str(e)}")

            warning("尝试原始workflow调用作为回退...")
            try:
                raw_state = await self.workflow.ainvoke(
                    initial_state,
                    config={"configurable": {"thread_id": f"process_{id(initial_state)}"}}
                )

                return self._convert_raw_state_to_result(raw_state, initial_state)

            except Exception as e2:
                error(f"原始调用也失败: {str(e2)}")
                raise e

    def _validate_fixed_result(self, result: Dict[str, Any]) -> bool:
        """验证修复后的结果"""
        try:
            if not result.get("success", False):
                warning("结果标记为不成功")
                return False

            data = result.get("data", {})
            if not isinstance(data, dict):
                warning(f"data字段不是字典: {type(data)}")
                return False

            instructions = data.get("instructions")
            if not instructions:
                warning("结果中没有 instructions")
                return False

            fragments = instructions.fragments
            if not isinstance(fragments, list):
                warning(f"fragments不是列表: {type(fragments)}")
                return False

            if len(fragments) == 0:
                warning("fragments列表为空")
                return False

            metadata = instructions.metadata
            if metadata.get("fixed_by_output_fixer"):
                debug("结果已被修复器修复")

            fragment_ids = [f.fragment_id for f in fragments]
            unique_ids = set(fragment_ids)
            if len(fragment_ids) != len(unique_ids):
                warning(f"片段ID不唯一: {len(fragment_ids)}个片段, {len(unique_ids)}个唯一ID")

            fragments_with_prompts = [f for f in fragments if f.prompt]
            if len(fragments_with_prompts) < len(fragments) * 0.8:
                warning(f"片段中提示词缺失较多: {len(fragments_with_prompts)}/{len(fragments)}个片段有提示词")

            fragments_with_audio_prompts = [f for f in fragments if f.audio_prompt]
            if len(fragments_with_audio_prompts) < len(fragments) * 0.5:
                warning(f"片段中音频提示词缺失较多: {len(fragments_with_audio_prompts)}/{len(fragments)}个片段有音频提示词")

            info(f"工作流输出修复验证通过: {len(fragments)}个片段")
            return True

        except Exception as e:
            error(f"验证结果时出错: {str(e)}")
            print_log_exception()
            return False

    def _validate_final_output(self, data: Dict[str, Any]):
        """验证最终输出"""
        try:
            if not isinstance(data, dict):
                return

            fragment_sequence = data.get("fragment_sequence")
            if fragment_sequence:
                fragments = fragment_sequence.get("fragments", [])
                shot_count = fragment_sequence.get("source_info", {}).get("shot_count", 0)

                info(f"最终输出验证: {shot_count}个镜头 -> {len(fragments)}个片段")

                if len(fragments) == shot_count and shot_count > 0:
                    info(f"片段数({len(fragments)})等于镜头数({shot_count})，没有分割记录")

                    metadata = fragment_sequence.get("metadata", {})
                    ai_split_count = metadata.get("ai_split_count", 0)
        except Exception as e:
            error(f"验证最终输出时出错: {str(e)}")

    def _convert_raw_state_to_result(self, raw_state: Any, initial_state: WorkflowState) -> Dict[str, Any]:
        """将原始状态转换为结果格式"""
        try:
            if isinstance(raw_state, dict):
                state_dict = raw_state
            elif hasattr(raw_state, 'dict'):
                state_dict = raw_state.dict()
            elif hasattr(raw_state, '__dict__'):
                state_dict = raw_state.__dict__
            else:
                return {"success": False, "error": "无法解析状态"}

            success = False
            data = state_dict.get('final_output')

            if data is not None:
                success = True
            else:
                current_stage = state_dict.get('current_stage')
                current_node = state_dict.get('current_node')

                if current_stage == 'completed' or current_node == 'generate_output':
                    success = True
                    data = {
                        "task_id": state_dict.get('task_id', initial_state.input.task_id),
                        "instructions": state_dict.get('instructions'),
                        "fragment_sequence": state_dict.get('fragment_sequence'),
                        "audit_report": state_dict.get('audit_report'),
                        "status": "completed"
                    }

            processing_stats = self._get_completed_stages(state_dict)

            return {
                "success": success,
                "data": data,
                "errors": state_dict.get('error_messages', []),
                "processing_stats": processing_stats,
                "task_id": initial_state.input.task_id,
                "workflow_status": "completed" if success else "failed"
            }

        except Exception as e:
            error(f"转换原始状态时出错: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "task_id": initial_state.input.task_id
            }