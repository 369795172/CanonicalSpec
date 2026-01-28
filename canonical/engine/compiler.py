"""
LLM Compiler - LLM-based compilation of user input into Canonical Specs.

This module handles:
- compile: Convert raw input to structured spec
- generate_clarify_questions: Generate questions for missing fields
- apply_answers: Apply user answers to update spec
- plan_tasks: Generate task planning from spec
- generate_vv: Generate V&V items from tasks
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from openai import OpenAI

from canonical.models.spec import (
    CanonicalSpec,
    Feature,
    FeatureStatus,
    Spec,
    AcceptanceCriteria,
    Planning,
    Task,
    TaskType,
    VV,
    VVType,
    Quality,
    MissingField,
    Decision,
    Meta,
    Estimate,
    ProjectContextRef,
)
from canonical.models.gate import ClarifyQuestion
from canonical.config import config


class LLMCompiler:
    """
    LLM-based compiler for generating and updating Canonical Specs.
    
    Uses OpenAI API (or compatible) for natural language understanding.
    """
    
    # System prompts for different operations
    COMPILE_SYSTEM_PROMPT = """你是一个需求分析专家。你的任务是将用户的输入转换为结构化的需求规格。

请从用户输入中提取以下信息（如果能够识别的话）：
1. goal: 核心目标/要解决的问题（必须至少10个字符）
2. non_goals: 明确不做什么（数组）
3. acceptance_criteria: 验收标准（数组，每个包含 id 和 criteria）
4. title: 简短标题

如果某些信息无法从输入中提取，请将其留空或使用合理的默认值。

以 JSON 格式返回结果。"""

    CLARIFY_SYSTEM_PROMPT = """你是一个需求分析专家。根据缺失的字段，生成简洁明确的澄清问题。

每个问题应该：
1. 直接针对缺失的信息
2. 使用简单易懂的语言
3. 提供一些指导或示例

以 JSON 数组格式返回问题列表。"""

    PLAN_TASKS_SYSTEM_PROMPT = """你是一个项目规划专家。根据需求规格，生成最小可执行任务集。

每个任务应包含：
1. task_id: 格式为 T-N
2. title: 任务标题
3. type: 任务类型（dev/test/doc/ops/design/research）
4. scope: 任务范围
5. deliverables: 交付物列表
6. owner_role: 负责角色
7. estimate: 估时（unit: hour/day, value: 数字）

任务应该：
- 粒度控制在2-8小时
- 包含开发、测试和文档任务
- 有明确的交付物

以 JSON 数组格式返回任务列表。"""

    GENERATE_VV_SYSTEM_PROMPT = """你是一个质量保证专家。根据任务列表，为每个任务生成验证方法。

每个验证项应包含：
1. vv_id: 格式为 VV-N
2. task_id: 关联的任务ID
3. type: 验证类型（unit/integration/e2e/manual/benchmark）
4. procedure: 验证步骤（可复制执行）
5. expected_result: 预期结果
6. evidence_required: 需要的证据类型

每个任务至少需要一个验证项。

以 JSON 数组格式返回验证列表。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize the LLM Compiler.
        
        Args:
            api_key: OpenAI API key. Defaults to config.llm_api_key.
            base_url: API base URL. Defaults to config.llm_base_url.
            model: Model to use. Defaults to config.llm_model.
            temperature: Temperature. Defaults to config.llm_temperature.
            max_tokens: Max tokens. Defaults to config.llm_max_tokens.
        """
        self.api_key = api_key or config.llm_api_key
        self.base_url = base_url or config.llm_base_url
        self.model = model or config.llm_model
        self.temperature = temperature if temperature is not None else config.llm_temperature
        self.max_tokens = max_tokens or config.llm_max_tokens
        
        if not self.api_key:
            raise ValueError("LLM API key is required. Set CANONICAL_LLM_API_KEY environment variable.")
        
        # Initialize OpenAI client
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self.client = OpenAI(**client_kwargs)

    def compile(self, user_input: str, feature_id: Optional[str] = None) -> CanonicalSpec:
        """
        Compile user input into a CanonicalSpec.
        
        Args:
            user_input: Raw user input text
            feature_id: Optional feature ID. If None, generates one.
            
        Returns:
            A new CanonicalSpec in draft status
        """
        # Call LLM to extract structured data
        response = self._call_llm(
            system_prompt=self.COMPILE_SYSTEM_PROMPT,
            user_message=user_input,
        )
        
        # Parse LLM response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # If JSON parsing fails, create minimal spec
            data = {
                "goal": user_input[:500] if len(user_input) > 10 else "",
                "non_goals": [],
                "acceptance_criteria": [],
                "title": user_input[:50] if len(user_input) > 0 else "Untitled",
            }
        
        # Create Feature
        if not feature_id:
            feature_id = self._generate_feature_id()
        
        feature = Feature(
            feature_id=feature_id,
            title=data.get("title", "Untitled"),
            status=FeatureStatus.DRAFT,
        )
        
        # Create Spec
        acceptance_criteria = []
        for i, ac_data in enumerate(data.get("acceptance_criteria", [])):
            if isinstance(ac_data, str):
                ac = AcceptanceCriteria(id=f"AC-{i+1}", criteria=ac_data)
            elif isinstance(ac_data, dict):
                # Validate and fix ID format if needed
                ac_id = ac_data.get("id", f"AC-{i+1}")
                # Ensure format is AC-N (not ACN or AC1)
                if not ac_id.startswith("AC-") or not ac_id[3:].isdigit():
                    ac_id = f"AC-{i+1}"
                ac = AcceptanceCriteria(
                    id=ac_id,
                    criteria=ac_data.get("criteria", ""),
                    test_hint=ac_data.get("test_hint"),
                )
            else:
                continue
            acceptance_criteria.append(ac)
        
        spec = Spec(
            goal=data.get("goal", ""),
            non_goals=data.get("non_goals", []),
            acceptance_criteria=acceptance_criteria,
        )
        
        # Initialize project_context_ref from config defaults if available
        project_context_ref = None
        if config.default_project_record_id:
            project_context_ref = ProjectContextRef(
                project_record_id=config.default_project_record_id,
                mentor_user_id=config.default_mentor_user_id,
                intern_user_id=config.default_intern_user_id,
            )
        
        # Create CanonicalSpec
        return CanonicalSpec(
            feature=feature,
            spec=spec,
            planning=Planning(),
            quality=Quality(),
            decision=Decision(),
            meta=Meta(),
            project_context_ref=project_context_ref,
        )

    def generate_clarify_questions(
        self,
        spec: CanonicalSpec,
        missing_fields: List[MissingField],
    ) -> List[ClarifyQuestion]:
        """
        Generate clarification questions for missing fields.
        
        Args:
            spec: Current spec
            missing_fields: List of missing fields
            
        Returns:
            List of clarification questions
        """
        if not missing_fields:
            return []
        
        # Format missing fields for the prompt
        fields_text = "\n".join([
            f"- {mf.path}: {mf.reason}"
            for mf in missing_fields
        ])
        
        user_message = f"""当前需求规格缺少以下信息：
{fields_text}

请为每个缺失字段生成一个澄清问题。返回 JSON 数组格式：
[{{"field_path": "...", "question": "..."}}]"""
        
        response = self._call_llm(
            system_prompt=self.CLARIFY_SYSTEM_PROMPT,
            user_message=user_message,
        )
        
        try:
            questions_data = json.loads(response)
        except json.JSONDecodeError:
            # Generate default questions
            questions_data = [
                {"field_path": mf.path, "question": f"请提供 {mf.path} 的信息: {mf.reason}"}
                for mf in missing_fields
            ]
        
        questions = []
        for i, q_data in enumerate(questions_data):
            if isinstance(q_data, dict):
                questions.append(ClarifyQuestion(
                    id=f"Q{i+1}",
                    field_path=q_data.get("field_path", missing_fields[i].path if i < len(missing_fields) else ""),
                    question=q_data.get("question", ""),
                    asks_for=q_data.get("field_path"),
                ))
        
        return questions

    def apply_answers(
        self,
        spec: CanonicalSpec,
        answers: Dict[str, str],
    ) -> CanonicalSpec:
        """
        Apply user answers to update the spec.
        
        Args:
            spec: Current spec
            answers: Dict mapping field paths to answers
            
        Returns:
            Updated CanonicalSpec (new version)
        """
        # Create a copy of the spec
        spec_dict = spec.model_dump()
        
        # Apply each answer with basic type normalization
        for field_path, answer in answers.items():
            normalized_value = self._normalize_answer_value(spec_dict, field_path, answer)
            self._set_nested_value(spec_dict, field_path, normalized_value)
        
        # Clear the spec_version to force new version generation
        spec_dict["meta"]["spec_version"] = None
        
        return CanonicalSpec.model_validate(spec_dict)

    def _normalize_answer_value(
        self,
        spec_dict: Dict[str, Any],
        field_path: str,
        answer: Any,
    ) -> Any:
        """Normalize answer value based on field path."""
        if not isinstance(answer, str):
            return answer

        trimmed = answer.strip()
        if not trimmed:
            return answer

        # Try JSON decode for structured inputs
        if trimmed.startswith("{") or trimmed.startswith("["):
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError:
                pass

        # List-like fields (simple newline/bullet split)
        list_fields = {
            "spec.non_goals",
            "planning.known_assumptions",
            "planning.constraints",
        }
        if field_path in list_fields:
            items = [
                line.strip().lstrip("-*•").strip()
                for line in trimmed.splitlines()
                if line.strip()
            ]
            return items

        # Acceptance criteria: parse lines into AC entries
        if field_path == "spec.acceptance_criteria":
            ac_items = []
            for line in trimmed.splitlines():
                raw = line.strip().lstrip("-*•").strip()
                if not raw:
                    continue
                if ":" in raw:
                    left, right = raw.split(":", 1)
                    ac_id = left.strip()
                    criteria = right.strip()
                else:
                    ac_id = f"AC-{len(ac_items) + 1}"
                    criteria = raw
                if not ac_id.startswith("AC-"):
                    ac_id = f"AC-{len(ac_items) + 1}"
                ac_items.append({"id": ac_id, "criteria": criteria})
            return ac_items

        # Tasks: minimal fallback from plain text
        if field_path == "planning.tasks":
            tasks = []
            for line in trimmed.splitlines():
                raw = line.strip().lstrip("-*•").strip()
                if not raw:
                    continue
                tasks.append({
                    "task_id": f"T-{len(tasks) + 1}",
                    "title": raw,
                    "type": "dev",
                    "scope": raw or "待补充",
                    "deliverables": [],
                    "dependencies": [],
                    "affected_components": [],
                })
            return tasks

        # V&V: minimal fallback from plain text
        if field_path == "planning.vv":
            vv_items = []
            tasks = spec_dict.get("planning", {}).get("tasks", [])
            for line in trimmed.splitlines():
                raw = line.strip().lstrip("-*•").strip()
                if not raw:
                    continue
                task_id = tasks[len(vv_items)].get("task_id") if len(tasks) > len(vv_items) else "T-1"
                vv_items.append({
                    "vv_id": f"VV-{len(vv_items) + 1}",
                    "task_id": task_id,
                    "type": "manual",
                    "procedure": raw,
                    "expected_result": "满足验收标准",
                    "evidence_required": [],
                })
            return vv_items

        return answer

    def plan_tasks(self, spec: CanonicalSpec) -> CanonicalSpec:
        """
        Generate task planning for the spec.
        
        Args:
            spec: Current spec (should have goal and acceptance_criteria)
            
        Returns:
            Updated CanonicalSpec with tasks (new version)
        """
        # Format spec for the prompt
        spec_summary = f"""目标: {spec.spec.goal}

验收标准:
{chr(10).join([f"- {ac.id}: {ac.criteria}" for ac in spec.spec.acceptance_criteria])}
"""
        
        response = self._call_llm(
            system_prompt=self.PLAN_TASKS_SYSTEM_PROMPT,
            user_message=spec_summary,
        )
        
        try:
            tasks_data = json.loads(response)
        except json.JSONDecodeError:
            # Generate minimal task set
            tasks_data = [
                {
                    "task_id": "T-1",
                    "title": "实现核心功能",
                    "type": "dev",
                    "scope": spec.spec.goal[:100],
                    "deliverables": ["代码实现"],
                    "owner_role": "dev",
                    "estimate": {"unit": "hour", "value": 4},
                }
            ]
        
        # Convert to Task objects
        tasks = []
        for t_data in tasks_data:
            if not isinstance(t_data, dict):
                continue
            
            estimate = None
            if "estimate" in t_data and isinstance(t_data["estimate"], dict):
                estimate = Estimate(
                    unit=t_data["estimate"].get("unit", "hour"),
                    value=t_data["estimate"].get("value", 1),
                )
            
            # Validate and fix task_id format if needed
            task_id = t_data.get("task_id", f"T-{len(tasks)+1}")
            if not task_id.startswith("T-") or not task_id[2:].isdigit():
                task_id = f"T-{len(tasks)+1}"
            
            task = Task(
                task_id=task_id,
                title=t_data.get("title", ""),
                type=TaskType(t_data.get("type", "dev")),
                scope=t_data.get("scope", ""),
                deliverables=t_data.get("deliverables", []),
                owner_role=t_data.get("owner_role"),
                estimate=estimate,
                dependencies=t_data.get("dependencies", []),
            )
            tasks.append(task)
        
        # Update spec with tasks
        spec_dict = spec.model_dump()
        spec_dict["planning"]["tasks"] = [t.model_dump() for t in tasks]
        spec_dict["meta"]["spec_version"] = None  # Force new version
        
        return CanonicalSpec.model_validate(spec_dict)

    def generate_vv(self, spec: CanonicalSpec) -> CanonicalSpec:
        """
        Generate V&V items for the tasks.
        
        Args:
            spec: Current spec (should have tasks)
            
        Returns:
            Updated CanonicalSpec with vv items (new version)
        """
        if not spec.planning.tasks:
            return spec
        
        # Format tasks for the prompt
        tasks_summary = "\n".join([
            f"- {t.task_id}: {t.title} ({t.type.value}) - {t.scope}"
            for t in spec.planning.tasks
        ])
        
        user_message = f"""任务列表:
{tasks_summary}

请为每个任务生成至少一个验证方法。"""
        
        response = self._call_llm(
            system_prompt=self.GENERATE_VV_SYSTEM_PROMPT,
            user_message=user_message,
        )
        
        try:
            vv_data = json.loads(response)
        except json.JSONDecodeError:
            # Generate minimal vv for each task
            vv_data = [
                {
                    "vv_id": f"VV-{i+1}",
                    "task_id": t.task_id,
                    "type": "manual",
                    "procedure": f"验证 {t.title} 是否完成",
                    "expected_result": "功能正常工作",
                    "evidence_required": ["screenshot"],
                }
                for i, t in enumerate(spec.planning.tasks)
            ]
        
        # Convert to VV objects
        vv_items = []
        for v_data in vv_data:
            if not isinstance(v_data, dict):
                continue
            
            # Ensure evidence_required is a list
            evidence = v_data.get("evidence_required", [])
            if isinstance(evidence, str):
                evidence = [evidence]
            elif not isinstance(evidence, list):
                evidence = []
            
            # Validate and fix vv_id format if needed
            vv_id = v_data.get("vv_id", f"VV-{len(vv_items)+1}")
            if not vv_id.startswith("VV-") or not vv_id[3:].isdigit():
                vv_id = f"VV-{len(vv_items)+1}"
            
            # Validate and fix task_id format if needed
            task_id = v_data.get("task_id", "")
            if task_id and (not task_id.startswith("T-") or not task_id[2:].isdigit()):
                task_id = ""  # Will be validated by VV model
            
            vv = VV(
                vv_id=vv_id,
                task_id=task_id,
                type=VVType(v_data.get("type", "manual")),
                procedure=v_data.get("procedure", ""),
                expected_result=v_data.get("expected_result", ""),
                evidence_required=evidence,
            )
            vv_items.append(vv)
        
        # Update spec with vv
        spec_dict = spec.model_dump()
        spec_dict["planning"]["vv"] = [v.model_dump() for v in vv_items]
        spec_dict["meta"]["spec_version"] = None  # Force new version
        
        return CanonicalSpec.model_validate(spec_dict)

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """
        Call the LLM API.
        
        Args:
            system_prompt: System prompt
            user_message: User message
            
        Returns:
            LLM response content
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        return response.choices[0].message.content or ""

    def _generate_feature_id(self) -> str:
        """Generate a new feature ID."""
        year = datetime.utcnow().strftime("%Y")
        # Simple counter - in production would check existing IDs
        import random
        num = random.randint(1, 999)
        return f"F-{year}-{num:03d}"

    def _set_nested_value(self, obj: dict, path: str, value: Any) -> None:
        """Set a nested value in a dict using dot + bracket notation path."""
        import re

        def parse_part(part: str) -> list:
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+)\])?$", part)
            if not match:
                return [part]
            key = match.group(1)
            idx = match.group(2)
            return [key, int(idx)] if idx is not None else [key]

        # Expand path parts with list indices
        expanded = []
        for part in path.split("."):
            expanded.extend(parse_part(part))

        current = obj
        parent = None
        parent_key = None

        for part in expanded[:-1]:
            if isinstance(part, int):
                if not isinstance(current, list):
                    new_list = []
                    if parent is not None:
                        parent[parent_key] = new_list
                    current = new_list
                while len(current) <= part:
                    current.append({})
                parent = current
                parent_key = part
                current = current[part]
            else:
                if part not in current or current[part] is None:
                    current[part] = {}
                parent = current
                parent_key = part
                current = current[part]

        last = expanded[-1]
        if isinstance(last, int):
            if not isinstance(current, list):
                new_list = []
                if parent is not None:
                    parent[parent_key] = new_list
                current = new_list
            while len(current) <= last:
                current.append(None)
            current[last] = value
        else:
            current[last] = value
