"""
Requirement Genome Models

Data models for requirement evolution tracking.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Assumption(BaseModel):
    """带来源的假设"""
    id: str = Field(..., description="Assumption ID (A-1, A-2, ...)")
    content: str = Field(..., description="Assumption content")
    source_round: int = Field(..., description="Round when this was added")
    confirmed: bool = Field(False, description="Whether confirmed by user")


class Constraint(BaseModel):
    """带来源的约束"""
    id: str = Field(..., description="Constraint ID (C-1, C-2, ...)")
    content: str = Field(..., description="Constraint content")
    source_round: int = Field(..., description="Round when this was added")
    type: str = Field("general", description="Type: technical/business/time/resource")


class UserStory(BaseModel):
    """用户故事"""
    id: str = Field(..., description="User Story ID (US-1, US-2, ...)")
    as_a: str = Field(..., description="As a [role]")
    i_want: str = Field(..., description="I want [feature]")
    so_that: str = Field(..., description="So that [benefit]")
    source_round: int = Field(..., description="Round when this was added")
    priority: str = Field("medium", description="Priority: high/medium/low")


class Decision(BaseModel):
    """已决策信息"""
    id: str = Field(..., description="Decision ID (D-1, D-2, ...)")
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="User's answer")
    round: int = Field(..., description="Round when decided")
    impact: str = Field("", description="Impact on requirement")


class GenomeSnapshot(BaseModel):
    """轮次快照"""
    round: int
    genome_version: str
    summary: str
    assumptions_count: int
    constraints_count: int
    user_stories_count: int
    questions_asked: List[str] = Field(default_factory=list)
    user_answers: List[str] = Field(default_factory=list)
    timestamp: datetime


class GenomeChanges(BaseModel):
    """本轮变更摘要"""
    new_assumptions: List[str] = Field(default_factory=list, description="新增假设列表")
    new_constraints: List[str] = Field(default_factory=list, description="新增约束列表")
    new_user_stories: List[str] = Field(default_factory=list, description="新增用户故事列表")
    updated_fields: List[str] = Field(default_factory=list, description="更新的字段列表")
    decisions_made: List[str] = Field(default_factory=list, description="本轮决策列表")


class RequirementGenome(BaseModel):
    """需求基因组 - 累积式需求状态"""
    
    # Version info
    genome_version: str = Field(..., description="Genome version (G-YYYYMMDD-NNNN)")
    round: int = Field(0, description="Current round number")
    
    # Accumulated understanding
    summary: str = Field("", description="AI accumulated summary")
    goals: List[str] = Field(default_factory=list, description="Goals list")
    non_goals: List[str] = Field(default_factory=list, description="Non-goals list")
    
    # Structured info
    assumptions: List[Assumption] = Field(default_factory=list)
    constraints: List[Constraint] = Field(default_factory=list)
    user_stories: List[UserStory] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    
    # Clarification state
    open_questions: List[Dict[str, Any]] = Field(default_factory=list)
    ready_to_compile: bool = Field(False)
    
    # Meta info
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # History
    history: List[GenomeSnapshot] = Field(default_factory=list)
