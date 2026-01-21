"""
Gate Result data models.

This module defines the data structures for Gate validation results,
following the Gate model defined in 02_gate_model.md.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from canonical.models.spec import MissingField


class GateStatus(BaseModel):
    """Status of a single gate."""
    is_passed: bool = Field(False, description="Whether the gate passed")
    missing_fields: List[MissingField] = Field(default_factory=list, description="Missing fields causing failure")
    reasons: List[str] = Field(default_factory=list, description="Reasons for pass/fail")


class ClarifyQuestion(BaseModel):
    """A question to clarify missing information."""
    id: str = Field(..., description="Question identifier")
    field_path: str = Field(..., description="Path to the field being asked about")
    question: str = Field(..., description="The question text")
    asks_for: Optional[str] = Field(None, description="What information this question asks for")


class WeightedDetails(BaseModel):
    """Weighted scoring details for completeness calculation."""
    goal_quality: float = Field(0.0, ge=0.0, le=1.0, description="Goal quality score")
    acceptance_criteria_quality: float = Field(0.0, ge=0.0, le=1.0, description="AC quality score")
    tasks_quality: float = Field(0.0, ge=0.0, le=1.0, description="Tasks quality score")
    vv_quality: float = Field(0.0, ge=0.0, le=1.0, description="V&V quality score")


class GateResult(BaseModel):
    """
    Complete result of gate validation.
    
    Contains the status of all three gates (S, T, V), completeness score,
    and any clarify questions that need to be answered.
    """
    gate_s: GateStatus = Field(default_factory=GateStatus, description="Gate S (Spec) status")
    gate_t: GateStatus = Field(default_factory=GateStatus, description="Gate T (Tasks) status")
    gate_v: GateStatus = Field(default_factory=GateStatus, description="Gate V (V&V) status")
    completeness_score: float = Field(0.0, ge=0.0, le=1.0, description="Overall completeness score")
    weighted_details: WeightedDetails = Field(default_factory=WeightedDetails, description="Scoring details")
    overall_pass: bool = Field(False, description="Whether all gates passed")
    next_action: str = Field("clarify", description="Recommended next action")
    clarify_questions: List[ClarifyQuestion] = Field(default_factory=list, description="Questions for clarification")

    @property
    def all_gates_passed(self) -> bool:
        """Check if all gates passed."""
        return self.gate_s.is_passed and self.gate_t.is_passed and self.gate_v.is_passed

    @property
    def all_missing_fields(self) -> List[MissingField]:
        """Get all missing fields from all gates."""
        fields = []
        fields.extend(self.gate_s.missing_fields)
        fields.extend(self.gate_t.missing_fields)
        fields.extend(self.gate_v.missing_fields)
        return fields

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary of the gate result."""
        return {
            "gate_s": "PASS" if self.gate_s.is_passed else "FAIL",
            "gate_t": "PASS" if self.gate_t.is_passed else "FAIL",
            "gate_v": "PASS" if self.gate_v.is_passed else "FAIL",
            "completeness_score": f"{self.completeness_score:.2f}",
            "overall_pass": self.overall_pass,
            "next_action": self.next_action,
            "missing_fields_count": len(self.all_missing_fields),
        }
