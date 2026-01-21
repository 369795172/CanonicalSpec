"""
Gate Engine - Deterministic validation of Canonical Specs.

This module implements the Gate validation logic following 02_gate_model.md.
All calculations are deterministic - same input always produces same output.
"""

from typing import List, Tuple
from canonical.models.spec import (
    CanonicalSpec,
    FeatureStatus,
    MissingField,
)
from canonical.models.gate import (
    GateResult,
    GateStatus,
    ClarifyQuestion,
    WeightedDetails,
)


class GateEngine:
    """
    Deterministic Gate Engine for validating Canonical Specs.
    
    Implements three gates:
    - Gate S: Specification completeness (goal, non_goals, acceptance_criteria)
    - Gate T: Tasks existence (planning.tasks)
    - Gate V: Verification coverage (planning.vv)
    
    All calculations are deterministic - no LLM or random elements.
    """
    
    # Weight constants for completeness score
    WEIGHT_GOAL = 0.30
    WEIGHT_AC = 0.25
    WEIGHT_TASKS = 0.25
    WEIGHT_VV = 0.20
    
    # Thresholds
    MIN_GOAL_LENGTH = 10
    MAX_GOAL_LENGTH = 500
    MIN_AC_COUNT = 1
    IDEAL_AC_COUNT = 3
    IDEAL_TASK_COUNT = 3

    def validate(self, spec: CanonicalSpec) -> GateResult:
        """
        Validate a Canonical Spec through all gates.
        
        Args:
            spec: The CanonicalSpec to validate
            
        Returns:
            GateResult with status of all gates and completeness score
        """
        # Validate each gate
        gate_s = self._validate_gate_s(spec)
        gate_t = self._validate_gate_t(spec)
        gate_v = self._validate_gate_v(spec)
        
        # Calculate weighted scores
        weighted_details = self._calculate_weighted_details(spec)
        
        # Calculate overall completeness score
        completeness_score = self._calculate_completeness_score(weighted_details)
        
        # Determine overall pass and next action
        overall_pass = gate_s.is_passed and gate_t.is_passed and gate_v.is_passed
        next_action = self._determine_next_action(spec, gate_s, gate_t, gate_v)
        
        # Generate clarify questions if needed
        clarify_questions = self._generate_clarify_questions(gate_s, gate_t, gate_v)
        
        return GateResult(
            gate_s=gate_s,
            gate_t=gate_t,
            gate_v=gate_v,
            completeness_score=completeness_score,
            weighted_details=weighted_details,
            overall_pass=overall_pass,
            next_action=next_action,
            clarify_questions=clarify_questions,
        )

    def _validate_gate_s(self, spec: CanonicalSpec) -> GateStatus:
        """
        Validate Gate S: Specification completeness.
        
        Checks:
        - spec.goal is non-empty and >= 10 chars
        - spec.non_goals exists (can be empty array)
        - spec.acceptance_criteria has at least 1 item
        - Each AC has id and criteria
        """
        missing_fields: List[MissingField] = []
        reasons: List[str] = []
        
        # Check goal
        goal = spec.spec.goal
        if not goal or len(goal.strip()) == 0:
            missing_fields.append(MissingField(
                path="spec.goal",
                reason="Goal is required - describe the core problem/user value"
            ))
            reasons.append("Gate S fail: goal 缺失")
        elif len(goal.strip()) < self.MIN_GOAL_LENGTH:
            missing_fields.append(MissingField(
                path="spec.goal",
                reason=f"Goal is too short (minimum {self.MIN_GOAL_LENGTH} chars)"
            ))
            reasons.append(f"Gate S fail: goal 长度不足 (< {self.MIN_GOAL_LENGTH} chars)")
        
        # Check non_goals (must exist as array, can be empty)
        # This is always valid since we default to empty list in the model
        
        # Check acceptance_criteria
        ac_list = spec.spec.acceptance_criteria
        if len(ac_list) < self.MIN_AC_COUNT:
            missing_fields.append(MissingField(
                path="spec.acceptance_criteria",
                reason="At least 1 acceptance criterion is required"
            ))
            reasons.append(f"Gate S fail: acceptance_criteria 数量为 {len(ac_list)}")
        else:
            # Validate each AC
            for i, ac in enumerate(ac_list):
                if not ac.id:
                    missing_fields.append(MissingField(
                        path=f"spec.acceptance_criteria[{i}].id",
                        reason="Acceptance criterion missing id"
                    ))
                    reasons.append(f"Gate S fail: acceptance_criteria[{i}] 缺少 id")
                if not ac.criteria or len(ac.criteria.strip()) == 0:
                    missing_fields.append(MissingField(
                        path=f"spec.acceptance_criteria[{i}].criteria",
                        reason="Acceptance criterion missing criteria text"
                    ))
                    reasons.append(f"Gate S fail: acceptance_criteria[{i}] 缺少 criteria")
        
        is_passed = len(missing_fields) == 0
        if is_passed:
            reasons.append("Gate S pass: 规格完整")
        
        return GateStatus(
            is_passed=is_passed,
            missing_fields=missing_fields,
            reasons=reasons,
        )

    def _validate_gate_t(self, spec: CanonicalSpec) -> GateStatus:
        """
        Validate Gate T: Tasks existence.
        
        For draft status: tasks can be empty
        For executable_ready: at least 1 task required
        
        Each task must have: task_id, title, type, scope
        """
        missing_fields: List[MissingField] = []
        reasons: List[str] = []
        
        tasks = spec.planning.tasks
        is_executable = spec.feature.status == FeatureStatus.EXECUTABLE_READY
        
        # Check if tasks are required based on status
        if is_executable and len(tasks) == 0:
            missing_fields.append(MissingField(
                path="planning.tasks",
                reason="At least 1 task is required for executable_ready status"
            ))
            reasons.append("Gate T fail: tasks 数量为 0，无法形成可执行最小任务集")
        elif len(tasks) == 0:
            # Draft status allows empty tasks, but still note it
            reasons.append("Gate T pass (draft): tasks 可以为空")
            return GateStatus(is_passed=True, missing_fields=[], reasons=reasons)
        
        # Validate each task
        for i, task in enumerate(tasks):
            if not task.task_id:
                missing_fields.append(MissingField(
                    path=f"planning.tasks[{i}].task_id",
                    reason="Task missing task_id"
                ))
                reasons.append(f"Gate T fail: task[{i}] 缺少 task_id")
            if not task.title or len(task.title.strip()) == 0:
                missing_fields.append(MissingField(
                    path=f"planning.tasks[{i}].title",
                    reason="Task missing title"
                ))
                reasons.append(f"Gate T fail: task[{i}] 缺少 title")
            if not task.type:
                missing_fields.append(MissingField(
                    path=f"planning.tasks[{i}].type",
                    reason="Task missing type"
                ))
                reasons.append(f"Gate T fail: task[{i}] 缺少 type")
            if not task.scope or len(task.scope.strip()) == 0:
                missing_fields.append(MissingField(
                    path=f"planning.tasks[{i}].scope",
                    reason="Task missing scope"
                ))
                reasons.append(f"Gate T fail: task[{i}] 缺少 scope")
        
        is_passed = len(missing_fields) == 0
        if is_passed:
            reasons.append(f"Gate T pass: {len(tasks)} 个任务完整定义")
        
        return GateStatus(
            is_passed=is_passed,
            missing_fields=missing_fields,
            reasons=reasons,
        )

    def _validate_gate_v(self, spec: CanonicalSpec) -> GateStatus:
        """
        Validate Gate V: Verification coverage.
        
        For draft status: vv can be empty
        For executable_ready: each task must have at least 1 vv
        
        Each vv must have: vv_id, task_id (valid), procedure, expected_result
        """
        missing_fields: List[MissingField] = []
        reasons: List[str] = []
        
        tasks = spec.planning.tasks
        vv_list = spec.planning.vv
        is_executable = spec.feature.status == FeatureStatus.EXECUTABLE_READY
        
        # If no tasks, vv is not required
        if len(tasks) == 0:
            reasons.append("Gate V pass (no tasks): vv 不需要")
            return GateStatus(is_passed=True, missing_fields=[], reasons=reasons)
        
        # If draft status and no vv, still pass
        if not is_executable and len(vv_list) == 0:
            reasons.append("Gate V pass (draft): vv 可以为空")
            return GateStatus(is_passed=True, missing_fields=[], reasons=reasons)
        
        # Build set of valid task_ids
        valid_task_ids = {task.task_id for task in tasks}
        
        # Validate each vv
        for i, vv in enumerate(vv_list):
            if not vv.vv_id:
                missing_fields.append(MissingField(
                    path=f"planning.vv[{i}].vv_id",
                    reason="VV missing vv_id"
                ))
                reasons.append(f"Gate V fail: vv[{i}] 缺少 vv_id")
            if not vv.task_id:
                missing_fields.append(MissingField(
                    path=f"planning.vv[{i}].task_id",
                    reason="VV missing task_id"
                ))
                reasons.append(f"Gate V fail: vv[{i}] 缺少 task_id")
            elif vv.task_id not in valid_task_ids:
                missing_fields.append(MissingField(
                    path=f"planning.vv[{i}].task_id",
                    reason=f"VV references non-existent task: {vv.task_id}"
                ))
                reasons.append(f"Gate V fail: vv[{i}] 的 task_id '{vv.task_id}' 不存在")
            if not vv.procedure or len(vv.procedure.strip()) == 0:
                missing_fields.append(MissingField(
                    path=f"planning.vv[{i}].procedure",
                    reason="VV missing procedure"
                ))
                reasons.append(f"Gate V fail: vv[{i}] 缺少 procedure")
            if not vv.expected_result or len(vv.expected_result.strip()) == 0:
                missing_fields.append(MissingField(
                    path=f"planning.vv[{i}].expected_result",
                    reason="VV missing expected_result"
                ))
                reasons.append(f"Gate V fail: vv[{i}] 缺少 expected_result")
        
        # Check that each task has at least one vv (for executable_ready)
        if is_executable:
            task_ids_with_vv = {vv.task_id for vv in vv_list}
            for task in tasks:
                if task.task_id not in task_ids_with_vv:
                    missing_fields.append(MissingField(
                        path=f"planning.vv",
                        reason=f"Task {task.task_id} has no associated vv"
                    ))
                    reasons.append(f"Gate V fail: task {task.task_id} 没有绑定的 vv")
        
        is_passed = len(missing_fields) == 0
        if is_passed:
            reasons.append(f"Gate V pass: {len(vv_list)} 个验证项覆盖 {len(tasks)} 个任务")
        
        return GateStatus(
            is_passed=is_passed,
            missing_fields=missing_fields,
            reasons=reasons,
        )

    def _calculate_weighted_details(self, spec: CanonicalSpec) -> WeightedDetails:
        """Calculate weighted scoring details."""
        return WeightedDetails(
            goal_quality=self._calculate_goal_quality(spec.spec.goal),
            acceptance_criteria_quality=self._calculate_ac_quality(spec.spec.acceptance_criteria),
            tasks_quality=self._calculate_tasks_quality(spec.planning.tasks),
            vv_quality=self._calculate_vv_quality(spec.planning.tasks, spec.planning.vv),
        )

    def _calculate_goal_quality(self, goal: str) -> float:
        """
        Calculate goal quality score (0.0-1.0).
        
        Factors:
        - Length: 10-500 chars (ideal)
        - Structure: Contains keywords like "目标", "解决"
        """
        if not goal or len(goal.strip()) < self.MIN_GOAL_LENGTH:
            return 0.0
        
        # Length score (0-1): normalized by max length
        length = len(goal.strip())
        length_score = min(1.0, length / self.MAX_GOAL_LENGTH)
        
        # Structure score: bonus for containing certain keywords
        structure_keywords = ["目标", "解决", "问题", "用户", "价值", "需要", "实现"]
        keyword_hits = sum(1 for kw in structure_keywords if kw in goal)
        structure_score = min(1.0, keyword_hits / 3)  # Max bonus at 3 keywords
        
        # Weighted combination
        return length_score * 0.6 + structure_score * 0.4

    def _calculate_ac_quality(self, ac_list: list) -> float:
        """
        Calculate acceptance criteria quality score (0.0-1.0).
        
        Factors:
        - Count: >= 3 is ideal
        - Test hints: bonus for having test_hint
        """
        if len(ac_list) == 0:
            return 0.0
        
        # Count score
        count_score = min(1.0, len(ac_list) / self.IDEAL_AC_COUNT)
        
        # Test hint score
        hint_count = sum(1 for ac in ac_list if ac.test_hint)
        hint_score = hint_count / max(len(ac_list), 1)
        
        return count_score * 0.7 + hint_score * 0.3

    def _calculate_tasks_quality(self, tasks: list) -> float:
        """
        Calculate tasks quality score (0.0-1.0).
        
        Factors:
        - Count: >= 3 is ideal
        - Type diversity: multiple task types is better
        - Dependencies: having dependencies defined is better
        """
        if len(tasks) == 0:
            return 0.0
        
        # Count score
        count_score = min(1.0, len(tasks) / self.IDEAL_TASK_COUNT)
        
        # Type diversity score
        task_types = {task.type for task in tasks}
        type_score = min(1.0, len(task_types) / 3)  # Max at 3 different types
        
        # Dependencies score
        dep_count = sum(1 for task in tasks if task.dependencies)
        dep_score = dep_count / max(len(tasks), 1)
        
        return count_score * 0.5 + type_score * 0.3 + dep_score * 0.2

    def _calculate_vv_quality(self, tasks: list, vv_list: list) -> float:
        """
        Calculate V&V quality score (0.0-1.0).
        
        Factors:
        - Coverage: each task should have vv
        - Type diversity: multiple vv types is better
        """
        if len(tasks) == 0:
            return 1.0  # No tasks, no vv needed
        
        if len(vv_list) == 0:
            return 0.0
        
        # Coverage score
        task_ids = {task.task_id for task in tasks}
        covered_tasks = {vv.task_id for vv in vv_list if vv.task_id in task_ids}
        coverage_score = len(covered_tasks) / max(len(task_ids), 1)
        
        # Type diversity score
        vv_types = {vv.type for vv in vv_list}
        type_score = min(1.0, len(vv_types) / 3)
        
        return coverage_score * 0.7 + type_score * 0.3

    def _calculate_completeness_score(self, details: WeightedDetails) -> float:
        """Calculate overall completeness score from weighted details."""
        return (
            details.goal_quality * self.WEIGHT_GOAL +
            details.acceptance_criteria_quality * self.WEIGHT_AC +
            details.tasks_quality * self.WEIGHT_TASKS +
            details.vv_quality * self.WEIGHT_VV
        )

    def _determine_next_action(
        self,
        spec: CanonicalSpec,
        gate_s: GateStatus,
        gate_t: GateStatus,
        gate_v: GateStatus,
    ) -> str:
        """Determine the next action based on gate results."""
        # If any gate fails, need clarification
        if not gate_s.is_passed:
            return "clarify"
        
        # If Gate S passes but no tasks yet, need task planning
        if len(spec.planning.tasks) == 0:
            return "plan_tasks"
        
        if not gate_t.is_passed:
            return "clarify"
        
        # If tasks exist but no vv yet, need vv generation
        if len(spec.planning.vv) == 0:
            return "generate_vv"
        
        if not gate_v.is_passed:
            return "clarify"
        
        # All gates pass, ready for publish
        return "publish"

    def _generate_clarify_questions(
        self,
        gate_s: GateStatus,
        gate_t: GateStatus,
        gate_v: GateStatus,
    ) -> List[ClarifyQuestion]:
        """Generate clarification questions based on missing fields."""
        questions = []
        question_id = 1
        
        # Questions for Gate S failures
        for mf in gate_s.missing_fields:
            q = self._missing_field_to_question(mf, question_id)
            if q:
                questions.append(q)
                question_id += 1
        
        # Questions for Gate T failures
        for mf in gate_t.missing_fields:
            q = self._missing_field_to_question(mf, question_id)
            if q:
                questions.append(q)
                question_id += 1
        
        # Questions for Gate V failures
        for mf in gate_v.missing_fields:
            q = self._missing_field_to_question(mf, question_id)
            if q:
                questions.append(q)
                question_id += 1
        
        return questions

    def _missing_field_to_question(self, mf: MissingField, question_id: int) -> ClarifyQuestion:
        """Convert a missing field to a clarification question."""
        # Map field paths to human-readable questions
        question_templates = {
            "spec.goal": '你希望这个功能解决的"用户痛点"一句话是什么？（谁/在什么场景/遇到什么问题）',
            "spec.acceptance_criteria": '如果做完了，你怎么判定它"真的完成"？请给 1-3 条可检查的标准',
            "planning.tasks": "请提供至少 1 个可执行任务，包括任务标题、类型和范围",
            "planning.vv": "请为每个任务提供至少 1 个验证方法，说明如何验证任务完成",
        }
        
        # Try to match exact path first, then prefix
        question_text = question_templates.get(mf.path)
        if not question_text:
            for prefix, template in question_templates.items():
                if mf.path.startswith(prefix):
                    question_text = template
                    break
        
        if not question_text:
            question_text = f"请补充缺失的信息: {mf.reason}"
        
        return ClarifyQuestion(
            id=f"Q{question_id}",
            field_path=mf.path,
            question=question_text,
            asks_for=mf.path,
        )
