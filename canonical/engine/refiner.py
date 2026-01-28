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
    )
except ImportError:
    RequirementGenome = None
    GenomeChanges = None
    GenomeSnapshot = None
    Assumption = None


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
3. **生成摘要**：用 2-3 句话总结你的理解，让用户确认或修正
4. **提问细化**：只问最关键的 1-2 个问题，每个问题解释为什么需要这个信息，并提供可能的答案建议

## 输出格式（JSON）

{
  "understanding_summary": "你对需求的理解摘要（2-3句话，Markdown格式）",
  "inferred_assumptions": ["假设1", "假设2"],
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
            messages.append({
                "role": entry.get("role", "user"),
                "content": entry.get("content", "")
            })
        
        # Add current user input
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
        
        if RequirementGenome and GenomeChanges:
            # Get existing genome from context
            existing_genome = None
            if context.additional_context and context.additional_context.get('genome'):
                try:
                    existing_genome = RequirementGenome.model_validate(context.additional_context['genome'])
                except Exception:
                    pass
            
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
                genome.goals = existing_genome.goals
                genome.non_goals = existing_genome.non_goals
                genome.assumptions = existing_genome.assumptions.copy()
                genome.constraints = existing_genome.constraints
                genome.user_stories = existing_genome.user_stories
                genome.decisions = existing_genome.decisions
                genome.history = existing_genome.history.copy()
            
            # Add new assumptions from inferred_assumptions
            changes = GenomeChanges()
            for assumption_text in data.get("inferred_assumptions", []):
                if assumption_text and not any(a.content == assumption_text for a in genome.assumptions):
                    genome.assumptions.append(Assumption(
                        id=f"A-{len(genome.assumptions) + 1}",
                        content=assumption_text,
                        source_round=new_round,
                        confirmed=False,
                    ))
                    changes.new_assumptions.append(assumption_text)
            
            # Update open questions
            genome.open_questions = [q.model_dump() for q in questions]
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
        
        return RefineResult(
            round=new_round,
            understanding_summary=data.get("understanding_summary", ""),
            inferred_assumptions=data.get("inferred_assumptions", []),
            questions=questions,
            ready_to_compile=data.get("ready_to_compile", False),
            draft_spec=data.get("draft_spec"),
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
