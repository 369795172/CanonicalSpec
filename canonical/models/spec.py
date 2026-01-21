"""
Canonical Spec data models.

This module defines the core data structures for the Canonical system,
following the MVP schema defined in 01_canonical_spec_mvp_schema.md.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re


class FeatureStatus(str, Enum):
    """Status of a feature in the pipeline."""
    DRAFT = "draft"
    CLARIFYING = "clarifying"
    EXECUTABLE_READY = "executable_ready"
    PUBLISHED = "published"
    HOLD = "hold"
    DROP = "drop"


class TaskType(str, Enum):
    """Type of task."""
    DEV = "dev"
    TEST = "test"
    DOC = "doc"
    OPS = "ops"
    DESIGN = "design"
    RESEARCH = "research"


class VVType(str, Enum):
    """Type of verification/validation."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    MANUAL = "manual"
    BENCHMARK = "benchmark"


class EvidenceType(str, Enum):
    """Type of evidence artifact."""
    DOC = "doc"
    CHAT = "chat"
    REPO = "repo"
    FILE = "file"


class AcceptanceCriteria(BaseModel):
    """A single acceptance criterion."""
    id: str = Field(..., description="Unique identifier, format: AC-N")
    criteria: str = Field(..., description="The acceptance criterion text")
    test_hint: Optional[str] = Field(None, description="Optional hint for testing")

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        if not re.match(r"^AC-\d+$", v):
            raise ValueError(f"Invalid AC id format: {v}. Expected: AC-N")
        return v


class Estimate(BaseModel):
    """Task estimation."""
    unit: str = Field(..., description="Unit of estimation: hour or day")
    value: float = Field(..., gt=0, description="Estimation value")

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        if v not in ["hour", "day"]:
            raise ValueError(f"Invalid unit: {v}. Expected: hour or day")
        return v


class Task(BaseModel):
    """A single task in the planning."""
    task_id: str = Field(..., description="Unique identifier, format: T-N")
    title: str = Field(..., min_length=1, description="Task title")
    type: TaskType = Field(..., description="Type of task")
    scope: str = Field(..., min_length=1, description="Task scope/what to do")
    deliverables: List[str] = Field(default_factory=list, description="List of deliverables")
    owner_role: Optional[str] = Field(None, description="Owner role: dev, qa, pm, ops")
    estimate: Optional[Estimate] = Field(None, description="Task estimate")
    dependencies: List[str] = Field(default_factory=list, description="List of task_ids this depends on")
    affected_components: List[str] = Field(default_factory=list, description="Affected file paths/components")

    @field_validator("task_id")
    @classmethod
    def validate_task_id_format(cls, v: str) -> str:
        if not re.match(r"^T-\d+$", v):
            raise ValueError(f"Invalid task_id format: {v}. Expected: T-N")
        return v


class VV(BaseModel):
    """Verification and Validation item."""
    vv_id: str = Field(..., description="Unique identifier, format: VV-N")
    task_id: str = Field(..., description="Reference to task_id")
    type: VVType = Field(..., description="Type of verification")
    procedure: str = Field(..., min_length=1, description="Verification procedure")
    expected_result: str = Field(..., min_length=1, description="Expected result")
    evidence_required: List[str] = Field(default_factory=list, description="Required evidence types")

    @field_validator("vv_id")
    @classmethod
    def validate_vv_id_format(cls, v: str) -> str:
        if not re.match(r"^VV-\d+$", v):
            raise ValueError(f"Invalid vv_id format: {v}. Expected: VV-N")
        return v

    @field_validator("task_id")
    @classmethod
    def validate_task_id_format(cls, v: str) -> str:
        if not re.match(r"^T-\d+$", v):
            raise ValueError(f"Invalid task_id format: {v}. Expected: T-N")
        return v


class MVPDefinition(BaseModel):
    """MVP definition within planning."""
    mvp_goal: Optional[str] = Field(None, description="What MVP validates")
    mvp_cut_lines: List[str] = Field(default_factory=list, description="What's cut for MVP")
    mvp_risks: List[str] = Field(default_factory=list, description="Risks to watch in MVP")


class Planning(BaseModel):
    """Planning section of the spec."""
    mvp_definition: Optional[MVPDefinition] = Field(None, description="MVP definition")
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    vv: List[VV] = Field(default_factory=list, description="List of V&V items")


class MissingField(BaseModel):
    """A missing field identified during gate validation."""
    path: str = Field(..., description="JSON path to the missing field")
    reason: str = Field(..., description="Reason why this field is needed")


class Quality(BaseModel):
    """Quality assessment of the spec."""
    completeness_score: float = Field(0.0, ge=0.0, le=1.0, description="Completeness score 0.0-1.0")
    missing_fields: List[MissingField] = Field(default_factory=list, description="List of missing fields")


class Decision(BaseModel):
    """Decision recommendation."""
    recommendation: str = Field("hold", description="Recommendation: go, hold, or drop")
    rationale: List[str] = Field(default_factory=list, description="List of reasons")

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        if v not in ["go", "hold", "drop"]:
            raise ValueError(f"Invalid recommendation: {v}. Expected: go, hold, or drop")
        return v


class SourceArtifact(BaseModel):
    """Source artifact reference."""
    type: EvidenceType = Field(..., description="Type of source")
    ref: str = Field(..., description="Reference to the source")


class Meta(BaseModel):
    """Metadata for the spec."""
    spec_version: Optional[str] = Field(None, description="Version identifier, format: S-YYYYMMDD-NNNN")
    source_artifacts: List[SourceArtifact] = Field(default_factory=list, description="Source artifacts")
    extensions: Dict[str, Any] = Field(default_factory=dict, description="Extension data")

    @field_validator("spec_version")
    @classmethod
    def validate_spec_version_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^S-\d{8}-\d{4}$", v):
            raise ValueError(f"Invalid spec_version format: {v}. Expected: S-YYYYMMDD-NNNN")
        return v


class ProjectContextRef(BaseModel):
    """Reference to project context."""
    project_id: Optional[str] = Field(None, description="Project identifier")
    context_version: Optional[str] = Field(None, description="Context version")
    project_record_id: Optional[str] = Field(None, description="Feishu project record ID")
    mentor_user_id: Optional[str] = Field(None, description="Mentor user ID in Feishu")
    intern_user_id: Optional[str] = Field(None, description="Intern user ID in Feishu")


class Spec(BaseModel):
    """The core specification content."""
    goal: str = Field("", description="Core problem/user value to solve")
    non_goals: List[str] = Field(default_factory=list, description="What is explicitly not in scope")
    background: Optional[str] = Field(None, description="Optional background information")
    acceptance_criteria: List[AcceptanceCriteria] = Field(default_factory=list, description="Acceptance criteria")


class Feature(BaseModel):
    """Feature metadata."""
    feature_id: str = Field(..., description="Unique identifier, format: F-YYYY-NNN")
    title: str = Field("", description="Short title")
    status: FeatureStatus = Field(FeatureStatus.DRAFT, description="Current status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

    @field_validator("feature_id")
    @classmethod
    def validate_feature_id_format(cls, v: str) -> str:
        if not re.match(r"^F-\d{4}-\d{3}$", v):
            raise ValueError(f"Invalid feature_id format: {v}. Expected: F-YYYY-NNN")
        return v


class CanonicalSpec(BaseModel):
    """
    The complete Canonical Spec - the single source of truth.
    
    This is the core data structure that flows through the entire pipeline,
    from initial input to final publish.
    """
    schema_version: str = Field("1.0", description="Schema version")
    feature: Feature = Field(..., description="Feature metadata")
    project_context_ref: Optional[ProjectContextRef] = Field(None, description="Project context reference")
    spec: Spec = Field(default_factory=Spec, description="Core specification")
    planning: Planning = Field(default_factory=Planning, description="Planning section")
    quality: Quality = Field(default_factory=Quality, description="Quality assessment")
    decision: Decision = Field(default_factory=Decision, description="Decision section")
    meta: Meta = Field(default_factory=Meta, description="Metadata")

    def model_post_init(self, __context: Any) -> None:
        """Update the updated_at timestamp."""
        self.feature.updated_at = datetime.utcnow()

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a task by its ID."""
        for task in self.planning.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_vv_for_task(self, task_id: str) -> List[VV]:
        """Get all V&V items for a task."""
        return [vv for vv in self.planning.vv if vv.task_id == task_id]

    def has_all_tasks_covered_by_vv(self) -> bool:
        """Check if all tasks have at least one V&V item."""
        if not self.planning.tasks:
            return True
        for task in self.planning.tasks:
            if not self.get_vv_for_task(task.task_id):
                return False
        return True
