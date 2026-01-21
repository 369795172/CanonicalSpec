"""
Step Snapshot and Evidence data models.

This module defines the data structures for pipeline step snapshots,
following the schema defined in 03_orchestrator_steps_io.md.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class StepName(str, Enum):
    """Names of pipeline steps."""
    INGEST = "ingest"
    COMPILE = "compile"
    VALIDATE_GATES = "validate_gates"
    CLARIFY_QUESTIONS = "clarify_questions"
    APPLY_ANSWERS = "apply_answers"
    PLAN_TASKS = "plan_tasks"
    GENERATE_VV = "generate_vv"
    MANUAL_REVIEW = "manual_review"
    PUBLISH = "publish"


class EvidenceType(str, Enum):
    """Type of evidence."""
    QUOTE = "quote"
    DOC = "doc"
    REPO = "repo"
    FILE = "file"
    API_RESULT = "api_result"
    LOG = "log"


class Step(BaseModel):
    """Information about a pipeline step."""
    name: StepName = Field(..., description="Step name")
    seq: int = Field(..., ge=1, description="Step sequence number")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Start time")
    ended_at: Optional[datetime] = Field(None, description="End time")


class StepInput(BaseModel):
    """Inputs to a step."""
    canonical_spec_ref: Optional[str] = Field(None, description="Reference to input spec version")
    context_ref: Optional[str] = Field(None, description="Reference to context")
    user_answer_ref: Optional[str] = Field(None, description="Reference to user answer")
    additional: Dict[str, Any] = Field(default_factory=dict, description="Additional inputs")


class StepOutput(BaseModel):
    """Outputs from a step."""
    gate_result: Optional[Dict[str, Any]] = Field(None, description="Gate result if applicable")
    spec_version_out: Optional[str] = Field(None, description="Output spec version if modified")
    questions: Optional[List[Dict[str, Any]]] = Field(None, description="Clarify questions if applicable")
    review_decision: Optional[str] = Field(None, description="Review decision if applicable")
    publish_result: Optional[Dict[str, Any]] = Field(None, description="Publish result if applicable")
    additional: Dict[str, Any] = Field(default_factory=dict, description="Additional outputs")


class StepDecision(BaseModel):
    """A decision made during a step."""
    decision: str = Field(..., description="The decision made")
    reason: str = Field(..., description="Reason for the decision")
    next_step: Optional[str] = Field(None, description="Next step to execute")


class EvidenceLink(BaseModel):
    """Link to evidence."""
    type: EvidenceType = Field(..., description="Type of evidence")
    evidence_id: str = Field(..., description="Evidence identifier")


class StepError(BaseModel):
    """An error that occurred during a step."""
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    retryable: bool = Field(False, description="Whether the error is retryable")
    retry_count: int = Field(0, ge=0, description="Number of retries attempted")


class StepMeta(BaseModel):
    """Metadata for a step snapshot."""
    engine_version: str = Field("orchestrator-0.1", description="Engine version")
    llm_model: Optional[str] = Field(None, description="LLM model used")
    extensions: Dict[str, Any] = Field(default_factory=dict, description="Extension data")


class StepSnapshot(BaseModel):
    """
    Complete snapshot of a pipeline step execution.
    
    This is the audit trail for every step in the pipeline,
    enabling replay and debugging.
    """
    run_id: str = Field(..., description="Run identifier, format: R-YYYYMMDD-NNNN")
    feature_id: str = Field(..., description="Feature identifier")
    spec_version_in: str = Field(..., description="Input spec version")
    spec_version_out: Optional[str] = Field(None, description="Output spec version")
    step: Step = Field(..., description="Step information")
    inputs: StepInput = Field(default_factory=StepInput, description="Step inputs")
    outputs: StepOutput = Field(default_factory=StepOutput, description="Step outputs")
    decisions: List[StepDecision] = Field(default_factory=list, description="Decisions made")
    evidence_links: List[EvidenceLink] = Field(default_factory=list, description="Links to evidence")
    errors: List[StepError] = Field(default_factory=list, description="Errors encountered")
    meta: StepMeta = Field(default_factory=StepMeta, description="Metadata")

    @field_validator("run_id")
    @classmethod
    def validate_run_id_format(cls, v: str) -> str:
        if not re.match(r"^R-\d{8}-\d{4}$", v):
            raise ValueError(f"Invalid run_id format: {v}. Expected: R-YYYYMMDD-NNNN")
        return v

    @field_validator("feature_id")
    @classmethod
    def validate_feature_id_format(cls, v: str) -> str:
        if not re.match(r"^F-\d{4}-\d{3}$", v):
            raise ValueError(f"Invalid feature_id format: {v}. Expected: F-YYYY-NNN")
        return v

    @field_validator("spec_version_in")
    @classmethod
    def validate_spec_version_in_format(cls, v: str) -> str:
        if not re.match(r"^S-\d{8}-\d{4}$", v):
            raise ValueError(f"Invalid spec_version_in format: {v}. Expected: S-YYYYMMDD-NNNN")
        return v

    @field_validator("spec_version_out")
    @classmethod
    def validate_spec_version_out_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^S-\d{8}-\d{4}$", v):
            raise ValueError(f"Invalid spec_version_out format: {v}. Expected: S-YYYYMMDD-NNNN")
        return v

    def mark_completed(self) -> None:
        """Mark the step as completed by setting the end time."""
        self.step.ended_at = datetime.utcnow()

    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate the duration of the step in milliseconds."""
        if self.step.ended_at is None:
            return None
        delta = self.step.ended_at - self.step.started_at
        return int(delta.total_seconds() * 1000)


class EvidenceSource(BaseModel):
    """Source of evidence."""
    ref: str = Field(..., description="Reference to the source")
    hash: Optional[str] = Field(None, description="Content hash for verification")


class EvidenceContent(BaseModel):
    """Content of evidence."""
    excerpt: str = Field(..., max_length=500, description="Short excerpt")
    note: Optional[str] = Field(None, description="Note about how this evidence is used")


class EvidenceLinkedTo(BaseModel):
    """What the evidence is linked to."""
    spec_path: Optional[str] = Field(None, description="Path in the spec")
    step: Optional[str] = Field(None, description="Step name")


class Evidence(BaseModel):
    """
    Evidence artifact for audit and traceability.
    
    Links source materials to spec fields and pipeline steps.
    """
    evidence_id: str = Field(..., description="Evidence identifier, format: E-NNNN")
    type: EvidenceType = Field(..., description="Type of evidence")
    source: EvidenceSource = Field(..., description="Source of the evidence")
    content: EvidenceContent = Field(..., description="Evidence content")
    linked_to: List[EvidenceLinkedTo] = Field(default_factory=list, description="What this links to")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id_format(cls, v: str) -> str:
        if not re.match(r"^E-\d+$", v):
            raise ValueError(f"Invalid evidence_id format: {v}. Expected: E-NNNN")
        return v
