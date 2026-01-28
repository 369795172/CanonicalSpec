"""
Orchestrator - Pipeline orchestration for the Canonical system.

Coordinates the flow through all pipeline steps:
ingest -> compile -> validate_gates -> clarify_questions -> apply_answers -> 
plan_tasks -> generate_vv -> manual_review -> publish
"""

from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from canonical.models.spec import (
    CanonicalSpec,
    FeatureStatus,
    MissingField,
)
from canonical.models.gate import GateResult
from canonical.models.snapshot import (
    StepSnapshot,
    Step,
    StepName,
    StepInput,
    StepOutput,
    StepDecision,
    StepMeta,
)
from canonical.engine.gate import GateEngine
from canonical.engine.compiler import LLMCompiler
from canonical.engine.refiner import RequirementRefiner
from canonical.models.refine import RefineResult, RefineContext
from canonical.store.spec_store import SpecStore
from canonical.store.snapshot_store import SnapshotStore


class Orchestrator:
    """
    Pipeline Orchestrator for the Canonical system.
    
    Manages the execution of pipeline steps and maintains state.
    """
    
    def __init__(
        self,
        spec_store: Optional[SpecStore] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        gate_engine: Optional[GateEngine] = None,
        compiler: Optional[LLMCompiler] = None,
        refiner: Optional[RequirementRefiner] = None,
    ):
        """
        Initialize the Orchestrator.
        
        Args:
            spec_store: SpecStore instance
            snapshot_store: SnapshotStore instance
            gate_engine: GateEngine instance
            compiler: LLMCompiler instance
            refiner: RequirementRefiner instance
        """
        self.spec_store = spec_store or SpecStore()
        self.snapshot_store = snapshot_store or SnapshotStore()
        self.gate_engine = gate_engine or GateEngine()
        self._compiler = compiler  # May be None if not configured
        self._refiner = refiner  # May be None if not configured
        
        self._current_run_id: Optional[str] = None
        self._step_seq = 0

    @property
    def compiler(self) -> LLMCompiler:
        """Get or create the LLM compiler."""
        if self._compiler is None:
            self._compiler = LLMCompiler()
        return self._compiler

    @property
    def refiner(self) -> Optional[RequirementRefiner]:
        """Get or create the Requirement Refiner."""
        if self._refiner is None:
            try:
                self._refiner = RequirementRefiner()
            except ValueError:
                # LLM not configured, refiner will be None
                self._refiner = None
        return self._refiner

    def run(
        self,
        user_input: str,
        feature_id: Optional[str] = None,
        refine_result: Optional[RefineResult] = None,
    ) -> Tuple[CanonicalSpec, GateResult]:
        """
        Run the initial pipeline: ingest -> (refine) -> compile -> validate_gates.
        
        Args:
            user_input: Raw user input (or refined input if refine_result is provided)
            feature_id: Optional feature ID
            refine_result: Optional refine result from previous refinement step
            
        Returns:
            Tuple of (CanonicalSpec, GateResult)
        """
        # Start new run
        self._current_run_id = self.snapshot_store.generate_run_id()
        self._step_seq = 0
        
        # Step 1: Ingest
        ingest_result = self._step_ingest(user_input, feature_id)
        
        # Step 2: Compile (use draft_spec from refine_result if available)
        if refine_result and refine_result.ready_to_compile and refine_result.draft_spec:
            # Use refined draft spec
            spec = self._step_compile_from_draft(ingest_result, refine_result.draft_spec)
        else:
            # Normal compilation
            spec = self._step_compile(ingest_result)
        
        # Step 3: Validate Gates
        gate_result = self._step_validate_gates(spec)
        
        # If Gate fails and refiner is available, replace static questions with contextual ones
        if not gate_result.overall_pass and self.refiner:
            # Collect all missing fields
            all_missing_fields = []
            all_missing_fields.extend(gate_result.gate_s.missing_fields)
            all_missing_fields.extend(gate_result.gate_t.missing_fields)
            all_missing_fields.extend(gate_result.gate_v.missing_fields)
            
            if all_missing_fields:
                # Generate contextual questions using refiner
                refine_context = RefineContext(
                    round=0,
                    feature_id=spec.feature.feature_id,
                )
                contextual_questions = self.refiner.generate_clarify_questions(
                    spec, all_missing_fields, refine_context
                )
                
                # Replace static questions with contextual ones
                if contextual_questions:
                    gate_result.clarify_questions = contextual_questions
        
        # Update spec status based on gate result
        if gate_result.overall_pass:
            spec.feature.status = FeatureStatus.EXECUTABLE_READY
        else:
            spec.feature.status = FeatureStatus.CLARIFYING
        
        # Update the existing spec version with new status (don't create new version)
        # The spec was already saved in _step_compile, so we update in place
        spec_file = self.spec_store.base_dir / spec.feature.feature_id / f"{spec.meta.spec_version}.json"
        if spec_file.exists():
            import json
            with open(spec_file, 'w', encoding='utf-8') as f:
                json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return spec, gate_result

    def answer(
        self,
        feature_id: str,
        answers: Dict[str, str],
    ) -> Tuple[CanonicalSpec, GateResult]:
        """
        Apply answers and re-validate.
        
        Args:
            feature_id: Feature ID
            answers: Dict mapping field paths to answers
            
        Returns:
            Tuple of (updated CanonicalSpec, GateResult)
        """
        # Load current spec
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        # Start new run or continue
        if self._current_run_id is None:
            self._current_run_id = self.snapshot_store.generate_run_id()
            self._step_seq = 0
        
        # Step: Apply Answers
        spec = self._step_apply_answers(spec, answers)
        
        # Step: Re-compile if needed (apply answers might need LLM refinement)
        # For now, skip re-compile and go directly to validation
        
        # Step: Validate Gates
        gate_result = self._step_validate_gates(spec)
        
        # If Gate fails and refiner is available, replace static questions with contextual ones
        if not gate_result.overall_pass and self.refiner:
            # Collect all missing fields
            all_missing_fields = []
            all_missing_fields.extend(gate_result.gate_s.missing_fields)
            all_missing_fields.extend(gate_result.gate_t.missing_fields)
            all_missing_fields.extend(gate_result.gate_v.missing_fields)
            
            if all_missing_fields:
                # Generate contextual questions using refiner
                refine_context = RefineContext(
                    round=0,
                    feature_id=spec.feature.feature_id,
                )
                contextual_questions = self.refiner.generate_clarify_questions(
                    spec, all_missing_fields, refine_context
                )
                
                # Replace static questions with contextual ones
                if contextual_questions:
                    gate_result.clarify_questions = contextual_questions
        
        # Update status
        if gate_result.overall_pass:
            spec.feature.status = FeatureStatus.EXECUTABLE_READY
        else:
            spec.feature.status = FeatureStatus.CLARIFYING
        
        # Update the existing spec version with new status (don't create new version)
        # The spec was already saved in _step_apply_answers
        spec_file = self.spec_store.base_dir / spec.feature.feature_id / f"{spec.meta.spec_version}.json"
        if spec_file.exists():
            import json
            with open(spec_file, 'w', encoding='utf-8') as f:
                json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return spec, gate_result

    def plan_tasks(self, feature_id: str) -> Tuple[CanonicalSpec, GateResult]:
        """
        Generate task planning for a feature.
        
        Args:
            feature_id: Feature ID
            
        Returns:
            Tuple of (updated CanonicalSpec, GateResult)
        """
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        if self._current_run_id is None:
            self._current_run_id = self.snapshot_store.generate_run_id()
            self._step_seq = 0
        
        # Step: Plan Tasks
        spec = self._step_plan_tasks(spec)
        
        # Step: Validate Gates
        gate_result = self._step_validate_gates(spec)
        
        # Spec was already saved in _step_plan_tasks, no need to save again
        
        return spec, gate_result

    def generate_vv(self, feature_id: str) -> Tuple[CanonicalSpec, GateResult]:
        """
        Generate V&V items for a feature.
        
        Args:
            feature_id: Feature ID
            
        Returns:
            Tuple of (updated CanonicalSpec, GateResult)
        """
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        if self._current_run_id is None:
            self._current_run_id = self.snapshot_store.generate_run_id()
            self._step_seq = 0
        
        # Step: Generate VV
        spec = self._step_generate_vv(spec)
        
        # Step: Validate Gates
        gate_result = self._step_validate_gates(spec)
        
        # Update status if all gates pass
        if gate_result.overall_pass:
            spec.feature.status = FeatureStatus.EXECUTABLE_READY
            # Update the existing spec version with new status
            spec_file = self.spec_store.base_dir / spec.feature.feature_id / f"{spec.meta.spec_version}.json"
            if spec_file.exists():
                import json
                with open(spec_file, 'w', encoding='utf-8') as f:
                    json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        # Spec was already saved in _step_generate_vv, no need to save again
        
        return spec, gate_result

    def review(
        self,
        feature_id: str,
        decision: str,
        rationale: Optional[str] = None,
    ) -> CanonicalSpec:
        """
        Apply manual review decision.
        
        Args:
            feature_id: Feature ID
            decision: Review decision (go/hold/drop)
            rationale: Optional rationale
            
        Returns:
            Updated CanonicalSpec
        """
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        if self._current_run_id is None:
            self._current_run_id = self.snapshot_store.generate_run_id()
            self._step_seq = 0
        
        # Step: Manual Review (read-only step, doesn't generate new version)
        spec = self._step_manual_review(spec, decision, rationale)
        
        # Update the existing spec file in place (manual_review is read-only, no new version)
        spec_file = self.spec_store.base_dir / feature_id / f"{spec.meta.spec_version}.json"
        if spec_file.exists():
            import json
            with open(spec_file, 'w', encoding='utf-8') as f:
                json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return spec

    def validate(self, feature_id: str) -> GateResult:
        """
        Validate a feature without modifying it.
        
        Args:
            feature_id: Feature ID
            
        Returns:
            GateResult
        """
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        return self.gate_engine.validate(spec)

    def compile_to_existing(
        self,
        feature_id: str,
        refine_result: RefineResult,
    ) -> Tuple[CanonicalSpec, GateResult]:
        """
        Compile RefineResult back to an existing feature spec.
        Updates the existing feature instead of creating a new one.
        
        Args:
            feature_id: Existing feature ID
            refine_result: RefineResult from refinement process
            
        Returns:
            Tuple of (updated CanonicalSpec, GateResult)
        """
        # Load existing spec
        spec = self.spec_store.load(feature_id)
        if not spec:
            raise ValueError(f"Feature {feature_id} not found")
        
        # Start new run or continue
        if self._current_run_id is None:
            self._current_run_id = self.snapshot_store.generate_run_id()
            self._step_seq = 0
        
        old_version = spec.meta.spec_version
        
        # Update spec from refine_result
        if refine_result.draft_spec:
            # Update goal
            if refine_result.draft_spec.get("goal"):
                spec.spec.goal = refine_result.draft_spec["goal"]
            
            # Update acceptance criteria
            if refine_result.draft_spec.get("acceptance_criteria"):
                from canonical.models.spec import AcceptanceCriteria
                acceptance_criteria = []
                for i, ac_data in enumerate(refine_result.draft_spec["acceptance_criteria"]):
                    if isinstance(ac_data, dict):
                        ac_id = ac_data.get("id", f"AC-{i+1}")
                        if not ac_id.startswith("AC-"):
                            ac_id = f"AC-{i+1}"
                        acceptance_criteria.append(AcceptanceCriteria(
                            id=ac_id,
                            criteria=ac_data.get("criteria", ""),
                        ))
                    elif isinstance(ac_data, str):
                        acceptance_criteria.append(AcceptanceCriteria(
                            id=f"AC-{i+1}",
                            criteria=ac_data,
                        ))
                spec.spec.acceptance_criteria = acceptance_criteria
        
        # Update assumptions and constraints from genome if available
        if refine_result.genome:
            # Update assumptions
            if refine_result.genome.assumptions:
                if spec.planning is None:
                    from canonical.models.spec import Planning
                    spec.planning = Planning()
                spec.planning.known_assumptions = [
                    a.content for a in refine_result.genome.assumptions
                ]
            
            # Update constraints
            if refine_result.genome.constraints:
                if spec.planning is None:
                    from canonical.models.spec import Planning
                    spec.planning = Planning()
                spec.planning.constraints = [
                    c.content for c in refine_result.genome.constraints
                ]
        
        # Save updated spec
        new_version = self.spec_store.save(spec)
        updated_spec = self.spec_store.load(feature_id, new_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=feature_id,
            spec_version_in=old_version,
            spec_version_out=new_version,
            step=Step(name=StepName.COMPILE, seq=self._step_seq + 1),
            inputs=StepInput(
                canonical_spec_ref=old_version,
                additional={"refine_result": refine_result.model_dump() if hasattr(refine_result, 'model_dump') else str(refine_result)},
            ),
            outputs=StepOutput(spec_version_out=new_version),
            decisions=[StepDecision(
                decision="compiled_from_refine",
                reason="Spec updated from refinement result",
                next_step="validate_gates",
            )],
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        # Validate gates
        gate_result = self._step_validate_gates(updated_spec)
        
        # Update status
        if gate_result.overall_pass:
            updated_spec.feature.status = FeatureStatus.EXECUTABLE_READY
        else:
            updated_spec.feature.status = FeatureStatus.CLARIFYING
        
        # Update spec file
        spec_file = self.spec_store.base_dir / feature_id / f"{new_version}.json"
        if spec_file.exists():
            import json
            with open(spec_file, 'w', encoding='utf-8') as f:
                json.dump(updated_spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return updated_spec, gate_result

    # Private step methods

    def _step_ingest(self, user_input: str, feature_id: Optional[str]) -> Dict[str, Any]:
        """Execute the ingest step."""
        self._step_seq += 1
        
        # Create a temporary spec version for snapshot tracking
        temp_version = f"S-{datetime.utcnow().strftime('%Y%m%d')}-0000"
        
        result = {
            "raw_input": user_input,
            "feature_id": feature_id,
            "input_length": len(user_input),
        }
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=feature_id or "F-0000-000",
            spec_version_in=temp_version,
            step=Step(name=StepName.INGEST, seq=self._step_seq),
            inputs=StepInput(additional={"raw_input": user_input[:500]}),
            outputs=StepOutput(additional=result),
            decisions=[StepDecision(
                decision="proceed",
                reason="Input received",
                next_step="compile",
            )],
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return result

    def _step_compile(self, ingest_result: Dict[str, Any]) -> CanonicalSpec:
        """Execute the compile step."""
        self._step_seq += 1
        
        raw_input = ingest_result.get("raw_input", "")
        feature_id = ingest_result.get("feature_id")
        
        # If no feature_id, generate one
        if not feature_id:
            feature_id = self.spec_store.generate_feature_id()
        
        # Compile using LLM
        spec = self.compiler.compile(raw_input, feature_id)
        
        # Save to get version
        spec_version = self.spec_store.save(spec)
        spec = self.spec_store.load(feature_id, spec_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=feature_id,
            spec_version_in=f"S-{datetime.utcnow().strftime('%Y%m%d')}-0000",
            spec_version_out=spec_version,
            step=Step(name=StepName.COMPILE, seq=self._step_seq),
            inputs=StepInput(additional=ingest_result),
            outputs=StepOutput(spec_version_out=spec_version),
            decisions=[StepDecision(
                decision="compiled",
                reason="Spec created from input",
                next_step="validate_gates",
            )],
            meta=StepMeta(llm_model=self.compiler.model),
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return spec

    def _step_compile_from_draft(
        self,
        ingest_result: Dict[str, Any],
        draft_spec: Dict[str, Any],
    ) -> CanonicalSpec:
        """Execute the compile step using draft spec from refinement."""
        self._step_seq += 1
        
        feature_id = ingest_result.get("feature_id")
        
        # If no feature_id, generate one
        if not feature_id:
            feature_id = self.spec_store.generate_feature_id()
        
        # Create spec from draft_spec
        from canonical.models.spec import (
            Feature,
            Spec,
            AcceptanceCriteria,
            Planning,
            Quality,
            Decision,
            Meta,
        )
        
        # Build acceptance criteria
        acceptance_criteria = []
        for i, ac_data in enumerate(draft_spec.get("acceptance_criteria", [])):
            if isinstance(ac_data, dict):
                ac_id = ac_data.get("id", f"AC-{i+1}")
                if not ac_id.startswith("AC-"):
                    ac_id = f"AC-{i+1}"
                acceptance_criteria.append(AcceptanceCriteria(
                    id=ac_id,
                    criteria=ac_data.get("criteria", ""),
                ))
            elif isinstance(ac_data, str):
                acceptance_criteria.append(AcceptanceCriteria(
                    id=f"AC-{i+1}",
                    criteria=ac_data,
                ))
        
        # Create spec
        spec = CanonicalSpec(
            feature=Feature(
                feature_id=feature_id,
                title=draft_spec.get("title", "Untitled"),
                status=FeatureStatus.DRAFT,
            ),
            spec=Spec(
                goal=draft_spec.get("goal", ""),
                non_goals=draft_spec.get("non_goals", []),
                acceptance_criteria=acceptance_criteria,
            ),
            planning=Planning(),
            quality=Quality(),
            decision=Decision(),
            meta=Meta(),
        )
        
        # Save to get version
        spec_version = self.spec_store.save(spec)
        spec = self.spec_store.load(feature_id, spec_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=feature_id,
            spec_version_in=f"S-{datetime.utcnow().strftime('%Y%m%d')}-0000",
            spec_version_out=spec_version,
            step=Step(name=StepName.COMPILE, seq=self._step_seq),
            inputs=StepInput(additional={**ingest_result, "draft_spec": draft_spec}),
            outputs=StepOutput(spec_version_out=spec_version),
            decisions=[StepDecision(
                decision="compiled",
                reason="Spec created from refined draft",
                next_step="validate_gates",
            )],
            meta=StepMeta(llm_model=self.compiler.model),
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return spec

    def _step_validate_gates(self, spec: CanonicalSpec) -> GateResult:
        """Execute the validate_gates step."""
        self._step_seq += 1
        
        gate_result = self.gate_engine.validate(spec)
        
        # Determine next action
        if gate_result.overall_pass:
            next_step = "manual_review"
            decision = "gates_passed"
        elif not gate_result.gate_s.is_passed:
            next_step = "clarify_questions"
            decision = "gate_s_failed"
        elif not gate_result.gate_t.is_passed:
            next_step = "plan_tasks" if len(spec.planning.tasks) == 0 else "clarify_questions"
            decision = "gate_t_failed"
        else:
            next_step = "generate_vv" if len(spec.planning.vv) == 0 else "clarify_questions"
            decision = "gate_v_failed"
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=spec.feature.feature_id,
            spec_version_in=spec.meta.spec_version,
            step=Step(name=StepName.VALIDATE_GATES, seq=self._step_seq),
            inputs=StepInput(canonical_spec_ref=spec.meta.spec_version),
            outputs=StepOutput(gate_result=gate_result.model_dump()),
            decisions=[StepDecision(
                decision=decision,
                reason=f"Score: {gate_result.completeness_score:.2f}",
                next_step=next_step,
            )],
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return gate_result

    def _step_apply_answers(
        self,
        spec: CanonicalSpec,
        answers: Dict[str, str],
    ) -> CanonicalSpec:
        """Execute the apply_answers step."""
        self._step_seq += 1
        
        old_version = spec.meta.spec_version
        
        # Apply answers using compiler
        updated_spec = self.compiler.apply_answers(spec, answers)
        
        # Save to get new version
        new_version = self.spec_store.save(updated_spec)
        updated_spec = self.spec_store.load(spec.feature.feature_id, new_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=spec.feature.feature_id,
            spec_version_in=old_version,
            spec_version_out=new_version,
            step=Step(name=StepName.APPLY_ANSWERS, seq=self._step_seq),
            inputs=StepInput(
                canonical_spec_ref=old_version,
                additional={"answers": answers},
            ),
            outputs=StepOutput(spec_version_out=new_version),
            decisions=[StepDecision(
                decision="answers_applied",
                reason=f"Applied {len(answers)} answers",
                next_step="validate_gates",
            )],
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return updated_spec

    def _step_plan_tasks(self, spec: CanonicalSpec) -> CanonicalSpec:
        """Execute the plan_tasks step."""
        self._step_seq += 1
        
        old_version = spec.meta.spec_version
        
        # Generate tasks using compiler
        updated_spec = self.compiler.plan_tasks(spec)
        
        # Save to get new version
        new_version = self.spec_store.save(updated_spec)
        updated_spec = self.spec_store.load(spec.feature.feature_id, new_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=spec.feature.feature_id,
            spec_version_in=old_version,
            spec_version_out=new_version,
            step=Step(name=StepName.PLAN_TASKS, seq=self._step_seq),
            inputs=StepInput(canonical_spec_ref=old_version),
            outputs=StepOutput(spec_version_out=new_version),
            decisions=[StepDecision(
                decision="tasks_planned",
                reason=f"Generated {len(updated_spec.planning.tasks)} tasks",
                next_step="generate_vv",
            )],
            meta=StepMeta(llm_model=self.compiler.model),
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return updated_spec

    def _step_generate_vv(self, spec: CanonicalSpec) -> CanonicalSpec:
        """Execute the generate_vv step."""
        self._step_seq += 1
        
        old_version = spec.meta.spec_version
        
        # Generate VV using compiler
        updated_spec = self.compiler.generate_vv(spec)
        
        # Save to get new version
        new_version = self.spec_store.save(updated_spec)
        updated_spec = self.spec_store.load(spec.feature.feature_id, new_version)
        
        # Create snapshot
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=spec.feature.feature_id,
            spec_version_in=old_version,
            spec_version_out=new_version,
            step=Step(name=StepName.GENERATE_VV, seq=self._step_seq),
            inputs=StepInput(canonical_spec_ref=old_version),
            outputs=StepOutput(spec_version_out=new_version),
            decisions=[StepDecision(
                decision="vv_generated",
                reason=f"Generated {len(updated_spec.planning.vv)} V&V items",
                next_step="validate_gates",
            )],
            meta=StepMeta(llm_model=self.compiler.model),
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return updated_spec

    def _step_manual_review(
        self,
        spec: CanonicalSpec,
        decision: str,
        rationale: Optional[str],
    ) -> CanonicalSpec:
        """Execute the manual_review step."""
        self._step_seq += 1
        
        # Update spec based on decision
        if decision == "go":
            spec.feature.status = FeatureStatus.EXECUTABLE_READY
            spec.decision.recommendation = "go"
            next_step = "publish"
        elif decision == "hold":
            spec.feature.status = FeatureStatus.HOLD
            spec.decision.recommendation = "hold"
            next_step = None
        elif decision == "drop":
            spec.feature.status = FeatureStatus.DROP
            spec.decision.recommendation = "drop"
            next_step = None
        else:
            raise ValueError(f"Invalid decision: {decision}. Expected: go, hold, drop")
        
        if rationale:
            spec.decision.rationale.append(rationale)
        
        # Create snapshot (manual review doesn't generate new version)
        snapshot = StepSnapshot(
            run_id=self._current_run_id,
            feature_id=spec.feature.feature_id,
            spec_version_in=spec.meta.spec_version,
            step=Step(name=StepName.MANUAL_REVIEW, seq=self._step_seq),
            inputs=StepInput(canonical_spec_ref=spec.meta.spec_version),
            outputs=StepOutput(review_decision=decision),
            decisions=[StepDecision(
                decision=f"review_{decision}",
                reason=rationale or f"Manual review decision: {decision}",
                next_step=next_step,
            )],
        )
        snapshot.mark_completed()
        self.snapshot_store.save(snapshot)
        
        return spec
