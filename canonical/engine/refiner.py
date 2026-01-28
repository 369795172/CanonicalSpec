"""
Requirement Refiner - LLM-driven requirement refinement and clarification.

This module implements intelligent requirement analysis using LLM to:
1. Understand user intent and infer assumptions
2. Generate contextual clarification questions
3. Refine vague requirements through conversational interaction
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from openai import OpenAI

from canonical.models.refine import (
    RefineResult,
    RefineQuestion,
    RefineContext,
)
from canonical.models.spec import CanonicalSpec, MissingField
from canonical.models.gate import ClarifyQuestion
from canonical.config import config

# Import Genome models
try:
    from canonical.models.genome import (
        RequirementGenome,
        GenomeChanges,
        GenomeSnapshot,
        Assumption,
        Constraint,
        UserStory,
    )
except ImportError:
    RequirementGenome = None
    GenomeChanges = None
    GenomeSnapshot = None
    Assumption = None
    Constraint = None
    UserStory = None


class RequirementRefiner:
    """
    LLM-based requirement refiner for intelligent requirement analysis.
    
    Uses LLM to:
    - Analyze user input and infer intent/assumptions
    - Generate contextual clarification questions
    - Refine vague requirements through conversation
    """
    
    REFINE_SYSTEM_PROMPT = """你是一个需求分析专家。你的任务是帮助用户将模糊的需求想法转化为清晰、可执行的规格。

## 你的工作方式

1. **理解意图**：从用户输入中识别核心目标和业务场景
2. **识别假设**：推断用户可能的隐含假设（技术栈、目标用户、规模、使用场景等）
3. **提取结构化信息**：从对话中提取目标、约束、用户故事等结构化信息
4. **生成摘要**：用 2-3 句话总结你的理解，让用户确认或修正
5. **提问细化**：只问最关键的 1-2 个问题，每个问题解释为什么需要这个信息，并提供可能的答案建议

## 输出格式（JSON）

{
  "understanding_summary": "你对需求的理解摘要（2-3句话，Markdown格式）",
  "inferred_assumptions": ["假设1", "假设2"],
  "goals": ["目标1", "目标2"],
  "constraints": ["约束1", "约束2"],
  "user_stories": [
    {
      "as_a": "角色",
      "i_want": "功能",
      "so_that": "价值"
    }
  ],
  "questions": [
    {
      "id": "Q1",
      "question": "问题内容",
      "why_asking": "这个信息为什么重要",
      "suggestions": ["可能的答案1", "可能的答案2"]
    }
  ],
  "ready_to_compile": false,
  "draft_spec": null
}

注意：
- goals: 从用户输入和对话历史中提取的核心目标列表（字符串数组）
- constraints: 识别到的技术、业务、时间、资源等约束（字符串数组）
- user_stories: 用户故事列表，格式为 {"as_a": "...", "i_want": "...", "so_that": "..."}
- 如果当前轮次无法提取某些字段，可以返回空数组，但应尽量提取已有信息

如果需求已经足够清晰，设置 ready_to_compile=true，并提供 draft_spec：
{
  "ready_to_compile": true,
  "draft_spec": {
    "goal": "核心目标描述",
    "acceptance_criteria": [
      {"id": "AC-1", "criteria": "验收标准1"},
      {"id": "AC-2", "criteria": "验收标准2"}
    ]
  }
}
"""

    CLARIFY_SYSTEM_PROMPT = """你是一个需求分析专家。根据缺失的字段和当前需求上下文，生成简洁明确的澄清问题。

当前需求上下文：
{context}

缺失的字段：
{missing_fields}

请为每个缺失字段生成一个澄清问题，问题应该：
1. 结合当前需求上下文，而不是使用通用模板
2. 解释为什么需要这个信息
3. 提供可能的答案建议

返回 JSON 数组格式：
[
  {{
    "id": "Q1",
    "field_path": "spec.goal",
    "question": "针对当前需求的具体问题...",
    "why_asking": "为什么需要这个信息",
    "suggestions": ["建议1", "建议2"]
  }}
]
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize the Requirement Refiner.
        
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

    def refine(
        self,
        user_input: str,
        context: Optional[RefineContext] = None,
    ) -> RefineResult:
        """
        Analyze user input and generate refinement result.
        
        Args:
            user_input: Raw user input text
            context: Optional refinement context with conversation history
            
        Returns:
            RefineResult with understanding summary, assumptions, and questions
        """
        if context is None:
            context = RefineContext(round=0)
        
        # Build conversation history for context
        messages = [{"role": "system", "content": self.REFINE_SYSTEM_PROMPT}]
        
        # Add conversation history if available
        for entry in context.conversation_history:
            entry_content = entry.get("content", "")
            messages.append({
                "role": entry.get("role", "user"),
                "content": entry_content
            })
        
        # Add current user input (only if not empty)
        if user_input:
            messages.append({"role": "user", "content": user_input})
        
        # Call LLM
        response = self._call_llm(messages)
        
        # Parse response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            data = {
                "understanding_summary": f"我理解你想要：{user_input}",
                "inferred_assumptions": [],
                "questions": [],
                "ready_to_compile": False,
                "draft_spec": None,
            }
        
        # Build questions list
        questions = []
        for i, q_data in enumerate(data.get("questions", [])):
            if isinstance(q_data, dict):
                questions.append(RefineQuestion(
                    id=q_data.get("id", f"Q{i+1}"),
                    question=q_data.get("question", ""),
                    why_asking=q_data.get("why_asking", ""),
                    suggestions=q_data.get("suggestions", []),
                ))
        
        # Build Genome if available
        genome = None
        changes = None
        new_round = context.round + 1
        
        # Get existing genome from context first (needed for limit calculation)
        existing_genome = None
        if RequirementGenome and context.additional_context and context.additional_context.get('genome'):
            try:
                existing_genome = RequirementGenome.model_validate(context.additional_context['genome'])
            except Exception:
                pass
        
        # Check for clarification limit (max rounds or max total questions)
        MAX_ROUNDS = 5
        MAX_TOTAL_QUESTIONS = 10
        total_questions_asked = 0
        if existing_genome and existing_genome.history:
            total_questions_asked = sum(len(h.questions_asked) for h in existing_genome.history)
        total_questions_asked += len(questions)
        
        # Force ready_to_compile if limit reached
        force_ready = False
        limit_reason = None
        if new_round > MAX_ROUNDS:
            force_ready = True
            limit_reason = f"已达到最大轮次限制（{MAX_ROUNDS}轮）"
        elif total_questions_asked > MAX_TOTAL_QUESTIONS:
            force_ready = True
            limit_reason = f"已达到最大问题数限制（{MAX_TOTAL_QUESTIONS}个）"
        
        if RequirementGenome and GenomeChanges:
            
            # Create new genome
            genome = RequirementGenome(
                genome_version=f"G-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                round=new_round,
                summary=data.get("understanding_summary", ""),
                created_at=existing_genome.created_at if existing_genome else datetime.now(),
                updated_at=datetime.now(),
            )
            
            # Copy existing data
            if existing_genome:
                genome.goals = existing_genome.goals.copy() if existing_genome.goals else []
                genome.non_goals = existing_genome.non_goals.copy() if existing_genome.non_goals else []
                genome.assumptions = existing_genome.assumptions.copy()
                genome.constraints = existing_genome.constraints.copy() if existing_genome.constraints else []
                genome.user_stories = existing_genome.user_stories.copy() if existing_genome.user_stories else []
                genome.decisions = existing_genome.decisions.copy() if existing_genome.decisions else []
                genome.history = existing_genome.history.copy()
            
            # Initialize changes tracker
            changes = GenomeChanges()
            
            # Update goals from LLM output (hybrid: merge with existing, avoid duplicates)
            new_goals = data.get("goals", [])
            if isinstance(new_goals, list):
                for goal_text in new_goals:
                    if goal_text and goal_text.strip() and goal_text not in genome.goals:
                        genome.goals.append(goal_text)
                        changes.updated_fields.append(f"新增目标: {goal_text}")
            
            # Update constraints from LLM output
            new_constraints = data.get("constraints", [])
            if isinstance(new_constraints, list):
                for constraint_text in new_constraints:
                    if constraint_text and constraint_text.strip():
                        # Check if constraint already exists
                        if not any(c.content == constraint_text for c in genome.constraints):
                            genome.constraints.append(Constraint(
                                id=f"C-{len(genome.constraints) + 1}",
                                content=constraint_text,
                                source_round=new_round,
                                type="general",
                            ))
                            changes.new_constraints.append(constraint_text)
            
            # Update user stories from LLM output
            new_user_stories = data.get("user_stories", [])
            if isinstance(new_user_stories, list):
                for us_data in new_user_stories:
                    if isinstance(us_data, dict):
                        as_a = us_data.get("as_a", "").strip()
                        i_want = us_data.get("i_want", "").strip()
                        so_that = us_data.get("so_that", "").strip()
                        if as_a and i_want and so_that:
                            # Check if user story already exists
                            if not any(
                                us.as_a == as_a and us.i_want == i_want and us.so_that == so_that
                                for us in genome.user_stories
                            ):
                                genome.user_stories.append(UserStory(
                                    id=f"US-{len(genome.user_stories) + 1}",
                                    as_a=as_a,
                                    i_want=i_want,
                                    so_that=so_that,
                                    source_round=new_round,
                                    priority="medium",
                                ))
                                changes.new_user_stories.append(f"{as_a} 想要 {i_want}，以便 {so_that}")
            
            # Add new assumptions from inferred_assumptions
            for assumption_text in data.get("inferred_assumptions", []):
                if assumption_text and not any(a.content == assumption_text for a in genome.assumptions):
                    genome.assumptions.append(Assumption(
                        id=f"A-{len(genome.assumptions) + 1}",
                        content=assumption_text,
                        source_round=new_round,
                        confirmed=False,
                    ))
                    changes.new_assumptions.append(assumption_text)
            
            # Hybrid: If draft_spec has goal/acceptance_criteria, use them to enrich genome
            draft_spec = data.get("draft_spec")
            if draft_spec:
                # Extract goal from draft_spec
                spec_goal = draft_spec.get("goal", "").strip()
                if spec_goal and spec_goal not in genome.goals:
                    genome.goals.append(spec_goal)
                    changes.updated_fields.append(f"从draft_spec提取目标: {spec_goal}")
                
                # Convert acceptance criteria to user stories if possible
                acceptance_criteria = draft_spec.get("acceptance_criteria", [])
                if isinstance(acceptance_criteria, list) and len(genome.user_stories) == 0:
                    # If no user stories yet, try to infer from acceptance criteria
                    for ac in acceptance_criteria[:3]:  # Limit to first 3
                        if isinstance(ac, dict):
                            criteria_text = ac.get("criteria", "").strip()
                            if criteria_text:
                                # Simple heuristic: try to extract user story pattern
                                # This is a fallback, LLM should provide proper user stories
                                pass
            
            # Update open questions
            genome.open_questions = [q.model_dump() for q in questions]
            
            # Set ready_to_compile (respect limit)
            if force_ready:
                genome.ready_to_compile = True
                # Add limit reason to summary if needed
                if limit_reason:
                    genome.summary += f"\n\n⚠️ {limit_reason}，建议进入编译阶段。"
            else:
                genome.ready_to_compile = data.get("ready_to_compile", False)
            
            # Create snapshot
            if GenomeSnapshot:
                snapshot = GenomeSnapshot(
                    round=new_round,
                    genome_version=genome.genome_version,
                    summary=genome.summary,
                    assumptions_count=len(genome.assumptions),
                    constraints_count=len(genome.constraints),
                    user_stories_count=len(genome.user_stories),
                    questions_asked=[q.question for q in questions],
                    user_answers=[],
                    timestamp=datetime.now(),
                )
                genome.history.append(snapshot)
        
        # Prepare understanding summary with limit info if needed
        understanding_summary = data.get("understanding_summary", "")
        if force_ready and limit_reason:
            understanding_summary += f"\n\n⚠️ **{limit_reason}**，建议进入编译阶段。"
        
        # Override ready_to_compile if limit reached
        final_ready_to_compile = force_ready or data.get("ready_to_compile", False)
        
        # Get draft_spec from LLM response
        draft_spec = data.get("draft_spec")
        
        # Fallback: Generate draft_spec from genome if ready_to_compile but draft_spec is missing/incomplete
        if final_ready_to_compile and genome:
            needs_fallback = False
            
            # Check if draft_spec is missing or incomplete
            if not draft_spec:
                needs_fallback = True
            else:
                # Check if critical fields are missing or empty
                title = draft_spec.get("title", "").strip()
                goal = draft_spec.get("goal", "").strip()
                if not title or not goal:
                    needs_fallback = True
            
            if needs_fallback:
                # Generate fallback draft_spec from genome
                fallback_draft_spec = {}
                
                # Generate title: prefer first goal, then summary-derived, then safe default
                if genome.goals and len(genome.goals) > 0:
                    # Use first goal as title (truncate if too long)
                    title_candidate = genome.goals[0].strip()
                    if len(title_candidate) > 50:
                        title_candidate = title_candidate[:47] + "..."
                    fallback_draft_spec["title"] = title_candidate
                elif genome.summary:
                    # Derive from summary (first sentence or first 50 chars)
                    summary_lines = genome.summary.strip().split('\n')
                    first_line = summary_lines[0].strip() if summary_lines else ""
                    if first_line:
                        if len(first_line) > 50:
                            fallback_draft_spec["title"] = first_line[:47] + "..."
                        else:
                            fallback_draft_spec["title"] = first_line
                    else:
                        fallback_draft_spec["title"] = "未命名功能"
                else:
                    fallback_draft_spec["title"] = "未命名功能"
                
                # Generate goal: use all genome goals (join if multiple), then summary
                if genome.goals and len(genome.goals) > 0:
                    # Combine all goals: if single goal, use as-is; if multiple, join with newlines
                    if len(genome.goals) == 1:
                        fallback_draft_spec["goal"] = genome.goals[0].strip()
                    else:
                        # Join multiple goals with newlines
                        fallback_draft_spec["goal"] = "\n".join([g.strip() for g in genome.goals if g.strip()])
                elif genome.summary:
                    # Use summary as goal if no explicit goals
                    fallback_draft_spec["goal"] = genome.summary.strip()[:200]  # Limit length
                else:
                    fallback_draft_spec["goal"] = ""
                
                # Generate acceptance_criteria from user stories and constraints (optional)
                acceptance_criteria = []
                
                # Add criteria from user stories
                if genome.user_stories:
                    for us in genome.user_stories[:5]:  # Limit to first 5
                        criteria_text = f"作为{us.as_a}，我希望{us.i_want}，以便{us.so_that}"
                        acceptance_criteria.append({
                            "id": f"AC-{len(acceptance_criteria) + 1}",
                            "criteria": criteria_text
                        })
                
                # Add criteria from constraints if no user stories
                if not acceptance_criteria and genome.constraints:
                    for constraint in genome.constraints[:3]:  # Limit to first 3
                        acceptance_criteria.append({
                            "id": f"AC-{len(acceptance_criteria) + 1}",
                            "criteria": constraint.content
                        })
                
                fallback_draft_spec["acceptance_criteria"] = acceptance_criteria
                
                # Add non_goals if available
                if genome.non_goals:
                    fallback_draft_spec["non_goals"] = genome.non_goals
                
                # Merge with existing draft_spec if it exists (preserve any fields that were present)
                if draft_spec:
                    # Merge: use fallback values only if original is missing/empty
                    if draft_spec.get("title", "").strip():
                        fallback_draft_spec["title"] = draft_spec["title"]
                    if draft_spec.get("goal", "").strip():
                        fallback_draft_spec["goal"] = draft_spec["goal"]
                    # Preserve other fields from original
                    for key, value in draft_spec.items():
                        if key not in ["title", "goal", "acceptance_criteria"]:
                            fallback_draft_spec[key] = value
                    # Merge acceptance_criteria if original has some
                    if draft_spec.get("acceptance_criteria") and len(draft_spec["acceptance_criteria"]) > 0:
                        fallback_draft_spec["acceptance_criteria"] = draft_spec["acceptance_criteria"]
                
                draft_spec = fallback_draft_spec
                
                # Log fallback usage for traceability
                if changes:
                    changes.updated_fields.append("⚠️ draft_spec已从genome自动生成（LLM未提供完整draft_spec）")
        
        return RefineResult(
            round=new_round,
            understanding_summary=understanding_summary,
            inferred_assumptions=data.get("inferred_assumptions", []),
            questions=questions,
            ready_to_compile=final_ready_to_compile,
            draft_spec=draft_spec,
            genome=genome,
            changes=changes,
        )

    def apply_feedback(
        self,
        feedback: str,
        context: RefineContext,
    ) -> RefineResult:
        """
        Apply user feedback and continue refinement.
        
        Args:
            feedback: User's feedback/answer
            context: Current refinement context
            
        Returns:
            Updated RefineResult
        """
        # Add feedback to conversation history
        context.conversation_history.append({
            "role": "user",
            "content": feedback
        })
        
        # Continue refinement
        return self.refine("", context)

    def refine_from_spec(
        self,
        spec: CanonicalSpec,
        context: Optional[RefineContext] = None,
    ) -> RefineResult:
        """
        Initialize refinement from an existing spec.
        Builds initial Genome from spec data.
        
        Args:
            spec: Existing CanonicalSpec
            context: Optional refinement context
            
        Returns:
            RefineResult with initialized Genome
        """
        if context is None:
            context = RefineContext(
                round=0,
                feature_id=spec.feature.feature_id,
            )
        
        # Build initial genome from spec
        genome = None
        if RequirementGenome:
            # Extract goals and non-goals
            goals = []
            if spec.spec.goal:
                goals.append(spec.spec.goal)
            
            non_goals = spec.spec.non_goals or []
            
            # Extract assumptions from planning
            assumptions = []
            if spec.planning and spec.planning.known_assumptions:
                for i, assumption_text in enumerate(spec.planning.known_assumptions):
                    assumptions.append(Assumption(
                        id=f"A-{i+1}",
                        content=assumption_text,
                        source_round=0,
                        confirmed=True,  # Already in spec, considered confirmed
                    ))
            
            # Extract constraints
            constraints = []
            if spec.planning and spec.planning.constraints:
                for i, constraint_text in enumerate(spec.planning.constraints):
                    constraints.append(Constraint(
                        id=f"C-{i+1}",
                        content=constraint_text,
                        source_round=0,
                        type="general",
                    ))
            
            # Create genome
            genome = RequirementGenome(
                genome_version=f"G-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                round=context.round,
                summary=f"已有功能：{spec.feature.title or spec.feature.feature_id}",
                goals=goals,
                non_goals=non_goals,
                assumptions=assumptions,
                constraints=constraints,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            
            # Store genome in context
            if context.additional_context is None:
                context.additional_context = {}
            context.additional_context['genome'] = genome.model_dump()
        
        # Now call refine with empty input to generate questions
        # The genome will be used from context
        return self.refine("", context)

    def generate_clarify_questions(
        self,
        spec: CanonicalSpec,
        missing_fields: List[MissingField],
        context: Optional[RefineContext] = None,
    ) -> List[ClarifyQuestion]:
        """
        Generate contextual clarification questions for missing fields.
        
        Args:
            spec: Current spec
            missing_fields: List of missing fields
            context: Optional refinement context
            
        Returns:
            List of ClarifyQuestion objects
        """
        if not missing_fields:
            return []
        
        # Build context summary
        spec_context = f"""
目标: {spec.spec.goal or '(未定义)'}
标题: {spec.feature.title or '(未定义)'}
验收标准数量: {len(spec.spec.acceptance_criteria)}
"""
        
        # Format missing fields
        fields_text = "\n".join([
            f"- {mf.path}: {mf.reason}"
            for mf in missing_fields
        ])
        
        # Build prompt
        user_message = self.CLARIFY_SYSTEM_PROMPT.format(
            context=spec_context,
            missing_fields=fields_text
        )
        
        # Call LLM
        messages = [
            {"role": "system", "content": self.CLARIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        response = self._call_llm(messages)
        
        # Parse response
        try:
            questions_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback to default questions
            questions_data = [
                {
                    "id": f"Q{i+1}",
                    "field_path": mf.path,
                    "question": f"请提供 {mf.path} 的信息: {mf.reason}",
                    "why_asking": "此信息是必需的",
                    "suggestions": []
                }
                for i, mf in enumerate(missing_fields)
            ]
        
        # Convert to ClarifyQuestion objects
        questions = []
        for q_data in questions_data:
            if isinstance(q_data, dict):
                questions.append(ClarifyQuestion(
                    id=q_data.get("id", ""),
                    field_path=q_data.get("field_path", ""),
                    question=q_data.get("question", ""),
                    asks_for=q_data.get("field_path"),
                ))
        
        return questions

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the LLM API.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            LLM response content
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        return response.choices[0].message.content or ""
