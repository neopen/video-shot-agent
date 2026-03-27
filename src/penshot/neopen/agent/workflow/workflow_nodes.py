"""
@FileName: workflow_nodes.py
@Description: LangGraph工作流节点实现，包含所有工作流执行功能
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2025/10 - 2025/11
"""
import time
import traceback
from datetime import datetime
from typing import Dict, Any, List

from penshot.neopen.agent.human_decision.human_decision_intervention import HumanIntervention
from penshot.neopen.agent.quality_auditor.quality_auditor_models import AuditStatus, QualityAuditReport, SeverityLevel
from penshot.neopen.agent.workflow.workflow_models import AgentStage, PipelineNode
from penshot.neopen.agent.workflow.workflow_states import WorkflowState
from penshot.neopen.tools.result_storage_tool import create_result_storage
from penshot.logger import error, debug, info, warning
from penshot.utils.log_utils import print_log_exception


class WorkflowNodes:
    """工作流节点集合，封装所有工作流执行功能"""

    def __init__(self, script_parser, shot_segmenter, video_splitter, prompt_converter, quality_auditor, llm=None):
        """
        初始化工作流节点集合
        
        Args:
            script_parser: 剧本解析器实例
            shot_segmenter: 分镜生成器实例
            video_splitter: 视频分割
            prompt_converter: 提示词转换
            quality_auditor: 质量审查实例
            llm: 语言模型实例（可选）
        """
        self.llm = llm

        self.script_parser = script_parser
        self.shot_segmenter = shot_segmenter
        self.video_splitter = video_splitter
        self.prompt_converter = prompt_converter
        self.quality_auditor = quality_auditor

        # 初始化人工干预节点
        self.human_intervention = HumanIntervention(timeout_seconds=180)
        self.storage = create_result_storage()

    def parse_script_node(self, state: WorkflowState) -> WorkflowState:
        """
        剧本解析节点（增强版）
        功能：将原始剧本解析为结构化元素序列，支持修复参数

        新增功能：
        - 支持修复参数传递（来自质量审查的修复建议）
        - 记录解析过程中的问题
        - 更新修复历史
        """
        try:
            # 检查是否有修复参数需要传递
            repair_params = state.repair_params.get(PipelineNode.PARSE_SCRIPT, None)

            if repair_params:
                info(f"剧本解析节点收到修复参数，问题类型: {repair_params.issue_types}")
                info(f"修复建议: {repair_params.suggestions}")
                # 记录修复来源
                state.repair_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "node": PipelineNode.PARSE_SCRIPT,
                    "repair_params": repair_params
                })
            else:
                debug("剧本解析节点执行（无修复参数）")

            # 执行剧本解析（传入修复参数）
            parsed_script = self.script_parser.parser_process(
                state.raw_script,
                repair_params=repair_params
            )

            debug(f"剧本解析完成，场景数: {len(parsed_script.scenes)}，角色数: {len(parsed_script.characters)}")
            debug(f"完整性评分: {parsed_script.stats.get('completeness_score', 0)}")

            # 保存剧本解析结果
            self.storage.save_obj_result(state.task_id, parsed_script, "script_parser_result.json")

            # 如果有修复历史，也保存到文件
            if hasattr(state, 'repair_history') and state.repair_history:
                self.storage.save_obj_result(state.task_id, state.repair_history, "script_parser_repair_history.json")

            # 检测解析过程中发现的问题（用于后续质量审查）
            if hasattr(self.script_parser, 'detect_issues'):
                parse_issues = self.script_parser.detect_issues(parsed_script, state.raw_script)
                if parse_issues:
                    debug(f"解析过程发现问题: {len(parse_issues)}个")
                    state.parse_issues.extend(parse_issues)

            state.parsed_script = parsed_script
            state.current_stage = AgentStage.PARSER
            state.current_node = PipelineNode.PARSE_SCRIPT

            # 更新解析统计
            state.parse_stats.update({
                "parse_attempts": parsed_script.stats.get("parse_attempts", 1),
                "completeness_score": parsed_script.stats.get("completeness_score", 0),
                "parsing_confidence": parsed_script.stats.get("parsing_confidence", {}),
                "repair_applied": repair_params is not None,
            })

            info(f"剧本解析节点完成，置信度: {state.parse_stats.get('parsing_confidence', {}).get('overall', 0)}")

        except Exception as e:
            print_log_exception()
            # 捕获异常，记录错误
            error_msg = f"剧本解析失败: {str(e)}"
            error(error_msg)
            state.error = error_msg
            # 添加到错误信息
            state.error_messages.append(error_msg)

            # 记录堆栈跟踪（开发环境）
            debug(f"解析异常堆栈: {traceback.format_exc()}")

            # 设置错误状态
            state.current_node = PipelineNode.PARSE_SCRIPT
            state.current_stage = AgentStage.ERROR_HANDLER
            state.error_source = PipelineNode.PARSE_SCRIPT

        return state

    def split_shots_node(self, state: WorkflowState) -> WorkflowState:
        """
        镜头拆分节点
        功能：将结构化剧本拆分为视觉镜头
        输入：parsed_script
        输出：shots (带时间戳的镜头序列)
        """
        try:
            shot_sequence = self.shot_segmenter.shot_process(state.parsed_script)
            debug(f"分镜解析完成，镜头数: {len(shot_sequence.shots)}")

            # 保存剧本解析结果
            self.storage.save_obj_result(state.task_id, shot_sequence, "shot_segmenter_result.json")

            state.shot_sequence = shot_sequence
            state.current_stage = AgentStage.SEGMENTER
            state.current_node = PipelineNode.SEGMENT_SHOT

        except Exception as e:
            print_log_exception()
            # 捕获异常，记录错误
            error_msg = f"分镜解析节点异常: {str(e)}"
            error(error_msg)
            state.error = error_msg
            # 添加到错误信息
            state.error_messages.append(error_msg)

            # 设置错误状态
            state.current_node = PipelineNode.SEGMENT_SHOT
            state.current_stage = AgentStage.ERROR_HANDLER
            state.error_source = PipelineNode.SEGMENT_SHOT

        return state

    def fragment_for_ai_node(self, state: WorkflowState) -> WorkflowState:
        """
        AI分段节点
        功能：将镜头按5秒限制切分为AI可处理的片段
        输入：shots
        输出：fragments (符合5秒限制的片段序列)
        """
        # 1. 检查镜头时长，>5秒的进行切分
        # 2. <2秒的考虑合并
        # 3. 在动作边界自然切分
        # 4. 生成片段级连续性锚点
        try:
            fragment_sequence = self.video_splitter.video_process(state.shot_sequence, state.parsed_script)
            debug(f"视频分段完成，视频片段数: {len(fragment_sequence.fragments)}")

            # 保存剧本解析结果
            self.storage.save_obj_result(state.task_id, fragment_sequence, "video_splitter_result.json")

            state.fragment_sequence = fragment_sequence
            state.current_stage = AgentStage.SPLITTER
            state.current_node = PipelineNode.SPLIT_VIDEO

        except Exception as e:
            print_log_exception()
            # 捕获异常，记录错误
            error_msg = f"视频分段异常: {str(e)}"
            error(error_msg)
            state.error = error_msg
            # 添加到错误信息
            state.error_messages.append(error_msg)

            # 设置错误状态
            state.current_node = PipelineNode.SPLIT_VIDEO
            state.current_stage = AgentStage.ERROR_HANDLER
            state.error_source = PipelineNode.SPLIT_VIDEO

        return state

    def generate_prompts_node(self, state: WorkflowState) -> WorkflowState:
        """
        Prompt生成节点
        功能：为每个片段生成AI视频生成提示词
        输入：fragments
        输出：ai_instructions (包含Prompt和技术参数)
        """
        # 1. 选择AI视频模型模板
        # 2. 使用LLM优化视觉描述
        # 3. 嵌入连续性约束
        # 4. 生成技术参数

        try:
            instructions = self.prompt_converter.prompt_process(state.fragment_sequence, state.parsed_script)
            debug(f"片段指令转换完成，指令片段数: {len(instructions.fragments)}")

            # 保存剧本解析结果
            self.storage.save_obj_result(state.task_id, instructions, "prompt_converter_result.json")

            state.instructions = instructions
            state.current_stage = AgentStage.CONVERTER
            state.current_node = PipelineNode.CONVERT_PROMPT

        except Exception as e:
            print_log_exception()
            # 捕获异常，记录错误
            error_msg = f"片段指令转换异常: {str(e)}"
            error(error_msg)
            state.error = error_msg
            # 添加到错误信息
            state.error_messages.append(error_msg)

            # 设置错误状态
            state.current_node = PipelineNode.CONVERT_PROMPT
            state.current_stage = AgentStage.ERROR_HANDLER
            state.error_source = PipelineNode.CONVERT_PROMPT

        return state

    def quality_audit_node(self, state: WorkflowState) -> WorkflowState:
        """
        质量审查节点（增强版）
        功能：合并基本规则审查和LLM深度审查，输出详细的审查报告

        变更说明：
        - 新增LLM深度审查能力
        - 支持问题分类和来源追溯
        - 生成增强的修复参数
        """
        # 检查是否已经执行过
        if state.audit_executed and state.audit_timestamp:
            # 如果10秒内重复执行，跳过
            last_time = datetime.fromisoformat(state.audit_timestamp)
            current_time = datetime.now()
            time_diff = (current_time - last_time).total_seconds()

            if time_diff < 10 and state.last_audit_result:
                warning(f"质量审查在 {time_diff:.1f} 秒内重复执行，使用上次结果")
                return state

        info(f"进入质量审查节点（增强版），当前阶段={state.current_stage.value}")
        info(f"审查前状态: 片段数={len(state.fragment_sequence.fragments) if state.fragment_sequence else 0}")

        try:
            # 执行质量审查（已合并基本规则和LLM审查）
            result = self.quality_auditor.qa_process(state.instructions)

            debug(f"质量审查完成:")
            debug(f"  - 审查状态: {result.status.value}")
            debug(f"  - 质量分数: {result.score}%")
            debug(f"  - 总问题数: {len(result.violations)}")
            debug(f"  - 检查项数: {len(result.checks)}")

            # 如果有详细的分类信息，记录日志
            # if hasattr(result, 'detailed_analysis'):
            #     analysis = result.detailed_analysis
            #     issues_by_source = analysis.get("issues_by_source", {})
            #     if issues_by_source:
            #         debug(f"  - 问题分布: {list(issues_by_source.keys())}")

            # 更新执行标志
            state.audit_executed = True
            state.repair_params = result.repair_params
            state.audit_timestamp = datetime.now().isoformat()
            state.last_audit_result = {
                "status": result.status.value,
                "score": result.score,
                "stats": result.stats,
                "violations_count": len(result.violations),
                "has_llm_audit": self.quality_auditor.llm_auditor is not None,
            }

            info(f"审计结果汇总: 状态={result.status.value}, 分数={result.score}%, 问题统计={result.stats}")

            # 记录错误来源（根据审查结果）
            if result.status in [AuditStatus.FAILED, AuditStatus.CRITICAL_ISSUES]:
                state.error_source = PipelineNode.AUDIT_QUALITY
                # 如果存在严重问题，记录错误信息
                critical_issues = [
                    v for v in result.violations
                    if v.severity in [SeverityLevel.CRITICAL, SeverityLevel.ERROR]
                ]
                if critical_issues:
                    state.error = f"质量审查发现严重问题: {len(critical_issues)}个"
                    state.error_messages.extend([
                        f"[{v.severity.value}] {v.description}"
                        for v in critical_issues[:3]  # 保留前3个
                    ])

            # 保存审查结果（增强版报告）
            self.storage.save_obj_result(state.task_id, result, "quality_auditor_result.json")

            # 如果有详细分析，单独保存一份便于调试
            if hasattr(result, 'detailed_analysis'):
                self.storage.save_obj_result(state.task_id, result.detailed_analysis, "quality_auditor_detailed_analysis.json")

            state.audit_report = result
            state.current_stage = AgentStage.AUDITOR
            state.current_node = PipelineNode.AUDIT_QUALITY

            # 根据审查状态决定后续流程
            if result.status == AuditStatus.PASSED:
                info("质量审查通过，继续执行后续流程")
            elif result.status == AuditStatus.MINOR_ISSUES:
                info("质量审查发现轻微问题，可以继续但建议关注")
            elif result.status in [AuditStatus.MODERATE_ISSUES, AuditStatus.MAJOR_ISSUES]:
                warning(f"质量审查发现中等问题，需要修复，建议进入修正流程")
                # 可选：触发修正流程标志
                state.needs_auto_fix = True
            elif result.status in [AuditStatus.CRITICAL_ISSUES, AuditStatus.FAILED]:
                error(f"质量审查发现严重问题，需要人工干预")
                state.needs_human_review = True
                state.error_source = PipelineNode.AUDIT_QUALITY

        except Exception as e:
            print_log_exception()
            # 捕获异常，记录错误
            error_msg = f"质量审查异常: {str(e)}"
            error(error_msg)
            state.error = error_msg
            # 添加到错误信息
            state.error_messages.append(error_msg)

            # 设置错误状态
            state.current_node = PipelineNode.AUDIT_QUALITY
            state.current_stage = AgentStage.ERROR_HANDLER
            state.error_source = PipelineNode.AUDIT_QUALITY

            # 创建回退报告
            state.audit_report = self._create_fallback_audit_report(state)

        return state

    def continuity_check_node(self, state: WorkflowState) -> WorkflowState:
        """
        连续性检查节点
        功能：检查跨片段的视觉连续性
        输入：ai_instructions, fragments
        输出：continuity_issues (连续性问题列表)
        """
        # TODO: 实现连续性检查逻辑
        # 1. 跟踪角色服装、道具状态
        # 2. 检查场景一致性
        # 3. 验证位置和动作连续性
        # 4. 标记不连续点
        state.continuity_issues = []
        state.current_stage = AgentStage.CONTINUITY

        return state

    def error_handler_node(self, graph_state: WorkflowState) -> WorkflowState:
        """错误处理节点 - 处理工作流中的错误和异常

        职责：
        1. 收集和分类错误信息
        2. 根据错误类型制定恢复策略
        3. 记录错误处理日志
        4. 决定是否可以恢复或需要人工干预

        设计原则：
        - 尽可能自动恢复
        - 提供详细的错误信息
        - 避免无限重试循环
        - 必要时请求人工干预
        """
        # 记录进入错误处理的时间
        error_time = time.time()

        # 确保有错误信息集合
        graph_state.error_messages = ["未知错误：进入错误处理节点但没有错误信息"]

        # 获取最近的重要错误
        recent_errors = graph_state.error_messages[-5:] if len(graph_state.error_messages) > 5 else graph_state.error_messages

        # 错误分类和分析
        error_analysis = self._analyze_errors(recent_errors)

        info(f"进入错误处理节点，错误分析: {error_analysis}")

        # 根据错误类型采取相应措施
        recovery_action = self._determine_recovery_action(error_analysis, graph_state)

        # 记录错误处理详情
        error_details = {
            "timestamp": error_time,
            "recent_errors": recent_errors,
            "error_analysis": error_analysis,
            "recovery_action": recovery_action,
            "current_node": graph_state.current_node,
            "global_loops": getattr(graph_state, 'global_current_loops', 0),
            "retry_count": getattr(graph_state, 'total_retries', 0),
        }

        # 保存错误处理历史
        graph_state.error_handling_history.append(error_details)

        # 清理过长的错误历史（保留最近10次）
        if len(graph_state.error_handling_history) > 10:
            graph_state.error_handling_history = graph_state.error_handling_history[-10:]

        # 根据恢复行动采取具体措施
        self._execute_recovery_action(recovery_action, graph_state, error_analysis)

        # 更新节点状态
        graph_state.current_node = PipelineNode.ERROR_HANDLER
        graph_state.current_stage = AgentStage.ERROR_HANDLER

        # 记录错误处理完成
        processing_time = time.time() - error_time
        info(f"错误处理完成，采取行动: {recovery_action}，耗时: {processing_time:.2f}秒")

        return graph_state

    def generate_output_node(self, state: WorkflowState) -> WorkflowState:
        """
        结果生成节点
        功能：组装最终输出结果
        输入：所有阶段的结果
        输出：final_output (完整处理结果)
        """
        info("进入生成输出节点")

        try:
            # 生成最终输出
            output_data = {
                "task_id": state.task_id,
                "script_analysis": state.parsed_script.model_dump() if state.parsed_script else None,
                "shot_sequence": state.shot_sequence.model_dump() if state.shot_sequence else None,
                "fragment_sequence": state.fragment_sequence.model_dump() if state.fragment_sequence else None,
                "instructions": state.instructions.model_dump() if state.instructions else None,
                "audit_report": state.audit_report.model_dump() if state.audit_report else None,
                "continuity_issues": state.continuity_issues,
                "created_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "status": "completed"
            }

            # 设置最终输出
            state.final_output = output_data

            # 更新阶段为 END
            state.current_stage = AgentStage.END
            state.current_node = PipelineNode.GENERATE_OUTPUT

            info(f"生成输出完成，数据大小: {len(str(output_data))} 字符，阶段更新为 END")

        except Exception as e:
            error(f"生成输出时出错: {str(e)}")
            state.error_messages.append(f"生成输出失败: {str(e)}")
            state.current_stage = AgentStage.ERROR_HANDLER
            state.current_node = PipelineNode.GENERATE_OUTPUT
            state.error_source = PipelineNode.GENERATE_OUTPUT

        return state

    def human_intervention_node(self, state: WorkflowState) -> WorkflowState:
        """
        人工干预节点
        功能：暂停流程等待人工输入
        输入：需要人工决策的状态
        输出：人工处理后的状态
        """
        state.current_stage = AgentStage.HUMAN
        # 这里应该等待外部系统（如Web界面）提供反馈
        # 实际实现时可以通过回调或消息队列处理

        # 模拟人工反馈（实际应从外部获取）
        if state.human_feedback:
            # 应用人工修正
            self.human_intervention(state)

        return state

    def loop_check_node(self, graph_state: WorkflowState) -> WorkflowState:
        """循环检查节点 - 检查节点循环次数并记录状态"""
        # 增加全局循环计数
        graph_state.global_current_loops += 1

        # 获取当前节点
        current_node = graph_state.current_node or None

        # 增加当前节点的循环计数
        current_node_loops = graph_state.node_current_loops.get(current_node, 0) + 1
        graph_state.node_current_loops[current_node] = current_node_loops

        # 获取该节点的最大循环次数
        node_max_loops = graph_state.node_max_loops.get(current_node, 3)  # 默认3次

        info(f"节点循环检查: 节点={current_node}, "
             f"节点循环={current_node_loops}/{node_max_loops}, "
             f"全局循环={graph_state.global_current_loops}/{graph_state.global_max_loops}")

        # 1. 检查节点循环限制
        if current_node_loops > node_max_loops:
            graph_state.node_loop_exceeded[current_node] = True
            error(f"节点 '{current_node}' 循环次数超过限制: {current_node_loops}/{node_max_loops}")

            graph_state.error_messages.append(
                f"节点 '{current_node}' 循环次数超过限制 ({current_node_loops}/{node_max_loops})"
            )

        # 2. 检查全局循环限制
        if graph_state.global_current_loops > graph_state.global_max_loops:
            graph_state.global_loop_exceeded = True
            error(f"全局循环次数超过限制: {graph_state.global_current_loops}/{graph_state.global_max_loops}")

            graph_state.error_messages.append(
                f"全局循环次数超过限制 ({graph_state.global_current_loops}/{graph_state.global_max_loops})"
            )

        # 3. 检查是否接近节点限制（警告）
        elif current_node_loops >= node_max_loops * 0.8:
            if not graph_state.loop_warning_issued:
                graph_state.loop_warning_issued = True
                warning(f"节点 '{current_node}' 循环次数接近限制: {current_node_loops}/{node_max_loops}")

        # 4. 记录节点进入详情（可选，便于调试）
        graph_state.node_loop_details.append({
            "node": current_node,
            "node_loop": current_node_loops,
            "global_loop": graph_state.global_current_loops,
            "timestamp": time.time()
        })

        # 更新节点追踪
        graph_state.last_node = current_node

        return graph_state

    # =============================================== 私有方法 ===============================================

    def _create_fallback_audit_report(self, state: WorkflowState) -> QualityAuditReport:
        """创建回退报告（当审查异常时）"""
        return QualityAuditReport(
            project_info={
                "title": getattr(state.instructions, 'project_info', {}).get("title", "未知项目"),
                "fragment_count": len(state.instructions.fragments) if state.instructions else 0,
                "total_duration": getattr(state.instructions, 'project_info', {}).get("total_duration", 0.0)
            },
            status=AuditStatus.FAILED,
            checks=[],
            violations=[],
            stats={"error": "audit_exception", "message": state.error},
            score=0.0
        )

    def _analyze_errors(self, error_list: List[str]) -> Dict[str, Any]:
        """分析错误列表，分类错误类型

        Args:
            error_list: 错误信息列表

        Returns:
            Dict: 错误分析结果
        """
        analysis = {
            "total_errors": len(error_list),
            "error_types": {},
            "most_common_error": "",
            "suggested_action": "unknown",
            "can_recover": True,
        }

        if not error_list:
            return analysis

        # 错误类型分类
        error_categories = {
            "network": ["network", "timeout", "connection", "socket", "http", "request"],
            "validation": ["validation", "invalid", "format", "type", "value"],
            "resource": ["memory", "disk", "cpu", "resource", "out of"],
            "configuration": ["configuration", "config", "parameter", "setting"],
            "business": ["业务", "逻辑", "规则", "requirement", "business"],
            "external": ["api", "external", "third", "service", "dependency"],
            "system": ["system", "os", "kernel", "fatal", "critical", "segmentation"],
            "data": ["data", "corrupt", "missing", "empty", "null"],
            "loop": ["循环", "loop", "exceeded", "超过限制"],
            "unknown": ["unknown", "未定义", "不明"],
        }

        # 统计错误类型
        type_counts = {category: 0 for category in error_categories.keys()}

        for error_msg in error_list:
            error_msg_lower = error_msg.lower()
            matched = False

            for category, keywords in error_categories.items():
                for keyword in keywords:
                    if keyword in error_msg_lower:
                        type_counts[category] += 1
                        matched = True
                        break
                if matched:
                    break

            if not matched:
                type_counts["unknown"] += 1

        # 找出最常见的错误类型
        if type_counts:
            most_common = max(type_counts.items(), key=lambda x: x[1])
            analysis["most_common_error"] = most_common[0]
            analysis["error_types"] = {k: v for k, v in type_counts.items() if v > 0}

        # 根据错误类型建议恢复行动
        if type_counts.get("system", 0) > 0 or type_counts.get("fatal", 0) > 0:
            analysis["suggested_action"] = "abort"
            analysis["can_recover"] = False
        elif type_counts.get("loop", 0) > 0:
            analysis["suggested_action"] = "human_intervention"
            analysis["can_recover"] = False
        elif type_counts.get("resource", 0) > 0:
            analysis["suggested_action"] = "retry_with_delay"
        elif type_counts.get("network", 0) > 0:
            analysis["suggested_action"] = "retry"
        elif type_counts.get("validation", 0) > 0 or type_counts.get("data", 0) > 0:
            analysis["suggested_action"] = "repair"
        else:
            analysis["suggested_action"] = "retry"

        return analysis

    def _determine_recovery_action(self, error_analysis: Dict[str, Any],
                                   state: WorkflowState) -> str:
        """根据错误分析和当前状态确定恢复行动

        Args:
            error_analysis: 错误分析结果
            state: 当前工作流状态

        Returns:
            str: 恢复行动类型
        """
        # 检查循环限制
        if getattr(state, 'global_loop_exceeded', False):
            return "abort"

        # 检查节点循环限制
        current_node = getattr(state, 'current_node', "")
        if hasattr(state, 'node_loop_exceeded') and current_node:
            if state.node_loop_exceeded.get(current_node, False):
                return "human_intervention"

        # 检查重试次数
        total_retries = getattr(state, 'total_retries', 0)
        max_allowed_retries = sum(getattr(state, 'stage_max_retries', {}).values())

        if total_retries >= max_allowed_retries:
            return "human_intervention"

        # 根据错误分析决定
        suggested_action = error_analysis.get("suggested_action", "retry")

        # 调整基于具体情况的行动
        if suggested_action == "retry":
            # 检查最近是否已经重试过多次
            if hasattr(state, 'error_handling_history'):
                recent_retries = sum(1 for h in state.error_handling_history[-3:]
                                     if h.get("recovery_action") == "retry")
                if recent_retries >= 2:
                    return "retry_with_delay"  # 连续重试多次，增加延迟
            return "retry"

        elif suggested_action == "repair":
            # 修复行动可能需要参数调整
            return "repair_with_adjustment"

        elif suggested_action == "abort":
            return "abort"

        elif suggested_action == "human_intervention":
            return "human_intervention"

        else:
            # 默认行动：带延迟的重试
            return "retry_with_delay"

    def _execute_recovery_action(self, action: str, state: WorkflowState,
                                 error_analysis: Dict[str, Any]) -> None:
        """执行具体的恢复行动

        Args:
            action: 恢复行动类型
            state: 工作流状态（会修改）
            error_analysis: 错误分析结果
        """
        from penshot.logger import info, warning

        info(f"执行恢复行动: {action}")

        if action == "retry":
            # 简单重试，清理部分错误信息
            state.error_messages = state.error_messages[-3:]  # 保留最近3个错误
            info("准备重试：清理错误信息，保持原状态")

        elif action == "retry_with_delay":
            # 带延迟的重试，可能需要调整参数
            state.error_messages = state.error_messages[-3:]

            # 添加延迟标记
            if not hasattr(state, 'recovery_flags'):
                state.recovery_flags = {}
            state.recovery_flags['need_delay'] = True
            state.recovery_flags['delay_seconds'] = 5  # 默认5秒延迟

            warning("检测到连续错误，将在重试前延迟5秒")

        elif action == "repair":
            # 修复行动，可能需要调整配置
            state.error_messages = state.error_messages[-3:]

            if not hasattr(state, 'recovery_flags'):
                state.recovery_flags = {}
            state.recovery_flags['need_repair'] = True
            state.recovery_flags['repair_type'] = error_analysis.get("most_common_error", "general")

            # 根据错误类型设置修复参数
            if error_analysis.get("most_common_error") == "validation":
                state.recovery_flags['adjust_validation'] = True
            elif error_analysis.get("most_common_error") == "configuration":
                state.recovery_flags['adjust_config'] = True

            info(f"准备修复：错误类型={error_analysis.get('most_common_error')}")

        elif action == "repair_with_adjustment":
            # 修复并调整参数
            state.error_messages = state.error_messages[-3:]

            if not hasattr(state, 'recovery_flags'):
                state.recovery_flags = {}

            state.recovery_flags['need_repair'] = True
            state.recovery_flags['need_adjustment'] = True

            # 记录需要调整的参数
            common_error = error_analysis.get("most_common_error", "")
            if common_error == "network":
                state.recovery_flags['adjust_timeout'] = True
                state.recovery_flags['timeout_multiplier'] = 1.5
            elif common_error == "resource":
                state.recovery_flags['reduce_load'] = True
                state.recovery_flags['batch_size'] = 0.5  # 减少50%的批量

            warning(f"准备修复并调整参数：{common_error}")

        elif action == "human_intervention":
            # 需要人工干预
            state.needs_human_review = True

            # 准备人工干预的详细信息
            if not hasattr(state, 'human_intervention_info'):
                state.human_intervention_info = {}

            state.human_intervention_info['reason'] = "自动恢复失败，需要人工决策"
            state.human_intervention_info['error_summary'] = error_analysis
            state.human_intervention_info['suggested_actions'] = [
                "retry_with_adjusted_params",
                "skip_current_stage",
                "abort_process"
            ]

            warning("错误需要人工干预：自动恢复失败")

        elif action == "abort":
            # 中止流程
            state.error_messages.append("流程被中止：无法恢复的错误")

            # 设置中止标志
            if not hasattr(state, 'recovery_flags'):
                state.recovery_flags = {}
            state.recovery_flags['should_abort'] = True

            error("流程中止：无法恢复的错误")

        else:
            # 未知行动，默认重试
            warning(f"未知恢复行动: {action}，使用默认重试")
            state.error_messages = state.error_messages[-3:]
