"""
Canonical API Server
FastAPI server for canonical frontend
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from typing import List, Optional
import json
from pathlib import Path

from canonical.config import config
from canonical.models.spec import CanonicalSpec, FeatureStatus
from canonical.models.refine import RefineResult, RefineContext
from canonical.engine.orchestrator import Orchestrator
from canonical.engine.refiner import RequirementRefiner
from canonical.store.spec_store import SpecStore
from canonical.services.ai_client import AIClient
from canonical.adapters.feishu import FeishuReader

app = FastAPI(
    title="Canonical Spec API",
    description="API server for Canonical Spec Manager frontend",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize stores
spec_store = SpecStore(base_dir=config.data_dir / "specs")
orchestrator = Orchestrator(spec_store=spec_store)

# Initialize AI client for audio transcription (optional)
ai_client: Optional[AIClient] = None

# Initialize Requirement Refiner (optional, requires LLM config)
refiner: Optional[RequirementRefiner] = None


@app.on_event("startup")
async def startup():
    """Initialize AI client and refiner on startup if configured."""
    global ai_client, refiner
    if config.ai_builder_token:
        try:
            ai_client = AIClient(
                token=config.ai_builder_token,
                base_url=config.ai_builder_base_url
            )
        except Exception as e:
            print(f"Warning: Failed to initialize AI client: {e}")
            ai_client = None
    
    # Initialize refiner if LLM is configured
    if config.llm_api_key:
        try:
            refiner = RequirementRefiner()
        except Exception as e:
            print(f"Warning: Failed to initialize Requirement Refiner: {e}")
            refiner = None


@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Canonical Spec API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/api/v1/system/health")
async def health():
    """Health check"""
    return {"status": "ok"}


@app.get("/api/v1/features")
async def list_features():
    """List all features"""
    try:
        features = []
        specs_dir = spec_store.base_dir
        
        if not specs_dir.exists():
            return {"features": []}
        
        # Iterate through all feature directories
        for feature_dir in specs_dir.iterdir():
            if not feature_dir.is_dir():
                continue
            
            feature_id = feature_dir.name
            if not feature_id.startswith("F-"):
                continue
            
            # Get the latest spec version
            spec_files = sorted(feature_dir.glob("S-*.json"), reverse=True)
            if not spec_files:
                continue
            
            latest_spec_file = spec_files[0]
            try:
                with open(latest_spec_file, 'r', encoding='utf-8') as f:
                    spec_data = json.load(f)
                    spec = CanonicalSpec.model_validate(spec_data)
                    
                    features.append({
                        "feature_id": spec.feature.feature_id,
                        "title": spec.feature.title or "",
                        "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
                        "spec": spec.model_dump(mode='json'),
                    })
            except Exception as e:
                print(f"Error loading spec {latest_spec_file}: {e}")
                continue
        
        return {"features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/features/{feature_id}")
async def get_feature(feature_id: str):
    """Get feature details"""
    try:
        feature_dir = spec_store.base_dir / feature_id
        if not feature_dir.exists():
            raise HTTPException(status_code=404, detail="Feature not found")
        
        # Get the latest spec version
        spec_files = sorted(feature_dir.glob("S-*.json"), reverse=True)
        if not spec_files:
            raise HTTPException(status_code=404, detail="Spec not found")
        
        latest_spec_file = spec_files[0]
        with open(latest_spec_file, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)
            spec = CanonicalSpec.model_validate(spec_data)
        
        # Validate gates to get current gate_result
        from canonical.engine.gate import GateEngine
        gate_engine = GateEngine()
        gate_result = gate_engine.validate(spec)
        
        return {
            "feature_id": spec.feature.feature_id,
            "feature": {
                "feature_id": spec.feature.feature_id,
                "title": spec.feature.title or "",
                "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
            },
            "spec": spec.model_dump(mode='json'),
            "gate_result": {
                "overall_pass": gate_result.overall_pass,
                "completeness_score": gate_result.completeness_score,
                "next_action": gate_result.next_action,
                "clarify_questions": [q.model_dump() for q in gate_result.clarify_questions],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/run")
async def run_pipeline(input: dict):
    """Run canonical pipeline"""
    try:
        input_text = input.get("input", "")
        refine_result_data = input.get("refine_result")
        
        if not input_text:
            raise HTTPException(status_code=400, detail="Input text is required")
        
        # Parse refine_result if provided
        refine_result = None
        if refine_result_data:
            try:
                refine_result = RefineResult.model_validate(refine_result_data)
            except Exception as e:
                print(f"Warning: Failed to parse refine_result: {e}")
        
        # Run the orchestrator pipeline (already saves the spec internally)
        spec, gate_result = orchestrator.run(input_text, refine_result=refine_result)
        
        return {
            "feature_id": spec.feature.feature_id,
            "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
            "message": "Feature created successfully",
            "gate_result": {
                "overall_pass": gate_result.overall_pass,
                "completeness_score": gate_result.completeness_score,
                "next_action": gate_result.next_action,
                "clarify_questions": [q.model_dump() for q in gate_result.clarify_questions],
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/features/{feature_id}/answer")
async def answer_feature(feature_id: str, body: dict):
    """Apply answers and re-validate"""
    try:
        answers = body.get("answers", {})
        if not answers:
            raise HTTPException(status_code=400, detail="Answers are required")
        
        # Apply answers and re-validate
        spec, gate_result = orchestrator.answer(feature_id, answers)
        
        return {
            "feature_id": spec.feature.feature_id,
            "feature": {
                "feature_id": spec.feature.feature_id,
                "title": spec.feature.title or "",
                "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
            },
            "spec": spec.model_dump(mode='json'),
            "gate_result": {
                "overall_pass": gate_result.overall_pass,
                "completeness_score": gate_result.completeness_score,
                "next_action": gate_result.next_action,
                "clarify_questions": [q.model_dump() for q in gate_result.clarify_questions],
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/refine")
async def refine_requirement(body: dict):
    """
    Refine a requirement using LLM analysis.
    
    Request body:
    {
        "input": "user input text",
        "context": {
            "conversation_history": [...],
            "round": 0,
            "feature_id": "...",
            "additional_context": {}
        }
    }
    """
    try:
        if not refiner:
            raise HTTPException(
                status_code=503,
                detail="Requirement Refiner not available. Please configure CANONICAL_LLM_API_KEY."
            )
        
        input_text = body.get("input", "")
        context_data = body.get("context")
        
        if not input_text:
            raise HTTPException(status_code=400, detail="Input text is required")
        
        # Parse context if provided
        context = None
        if context_data:
            try:
                context = RefineContext.model_validate(context_data)
            except Exception as e:
                print(f"Warning: Failed to parse context: {e}")
                context = None
        
        # Refine requirement
        refine_result = refiner.refine(input_text, context)
        
        return refine_result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/refine/feedback")
async def refine_feedback(body: dict):
    """
    Apply feedback to continue refinement conversation.
    
    Request body:
    {
        "feedback": "user feedback/answer",
        "context": {
            "conversation_history": [...],
            "round": 1,
            "feature_id": "...",
            "additional_context": {}
        }
    }
    """
    try:
        if not refiner:
            raise HTTPException(
                status_code=503,
                detail="Requirement Refiner not available. Please configure CANONICAL_LLM_API_KEY."
            )
        
        feedback_text = body.get("feedback", "")
        context_data = body.get("context")
        
        if not feedback_text:
            raise HTTPException(status_code=400, detail="Feedback text is required")
        
        if not context_data:
            raise HTTPException(status_code=400, detail="Context is required")
        
        # Parse context
        try:
            context = RefineContext.model_validate(context_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid context: {str(e)}")
        
        # Apply feedback
        refine_result = refiner.apply_feedback(feedback_text, context)
        
        return refine_result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/features/{feature_id}/refine")
async def refine_existing_feature(feature_id: str, body: dict):
    """
    Start refinement flow for an existing feature.
    Initializes Genome from existing spec and returns RefineResult.
    
    Request body:
    {
        "input": "optional user input",
        "context": {
            "conversation_history": [...],
            "round": 0,
            "feature_id": "...",
            "additional_context": {}
        }
    }
    """
    try:
        if not refiner:
            raise HTTPException(
                status_code=503,
                detail="Requirement Refiner not available. Please configure CANONICAL_LLM_API_KEY."
            )
        
        # Load existing spec
        feature_dir = spec_store.base_dir / feature_id
        if not feature_dir.exists():
            raise HTTPException(status_code=404, detail="Feature not found")
        
        spec_files = sorted(feature_dir.glob("S-*.json"), reverse=True)
        if not spec_files:
            raise HTTPException(status_code=404, detail="Spec not found")
        
        latest_spec_file = spec_files[0]
        with open(latest_spec_file, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)
            spec = CanonicalSpec.model_validate(spec_data)
        
        # Parse context if provided
        context_data = body.get("context")
        context = None
        if context_data:
            try:
                context = RefineContext.model_validate(context_data)
                context.feature_id = feature_id
            except Exception as e:
                print(f"Warning: Failed to parse context: {e}")
                context = None
        
        if context is None:
            context = RefineContext(
                round=0,
                feature_id=feature_id,
            )
        
        # Initialize refinement from spec
        input_text = body.get("input", "")
        if input_text:
            # User provided new input, use refine with context
            refine_result = refiner.refine(input_text, context)
        else:
            # No new input, initialize from spec
            refine_result = refiner.refine_from_spec(spec, context)
        
        return refine_result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/features/{feature_id}/compile")
async def compile_refined_feature(feature_id: str, body: dict):
    """
    Compile RefineResult back to existing feature spec.
    Updates the feature instead of creating a new one.
    
    Request body:
    {
        "refine_result": {
            "round": 2,
            "understanding_summary": "...",
            "ready_to_compile": true,
            "draft_spec": {...},
            "genome": {...}
        }
    }
    """
    try:
        refine_result_data = body.get("refine_result")
        if not refine_result_data:
            raise HTTPException(status_code=400, detail="refine_result is required")
        
        # Parse refine_result
        try:
            refine_result = RefineResult.model_validate(refine_result_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid refine_result: {str(e)}")
        
        # Compile to existing feature
        spec, gate_result = orchestrator.compile_to_existing(feature_id, refine_result)
        
        return {
            "feature_id": spec.feature.feature_id,
            "feature": {
                "feature_id": spec.feature.feature_id,
                "title": spec.feature.title or "",
                "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
            },
            "spec": spec.model_dump(mode='json'),
            "gate_result": {
                "overall_pass": gate_result.overall_pass,
                "completeness_score": gate_result.completeness_score,
                "next_action": gate_result.next_action,
                "clarify_questions": [q.model_dump() for q in gate_result.clarify_questions],
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/features/{feature_id}/document")
async def generate_feature_document(feature_id: str):
    """
    Generate a Markdown document for a feature spec.
    
    Returns the Canonical Spec formatted as a Markdown document.
    """
    try:
        # Load the spec
        spec = spec_store.load(feature_id)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        
        # Generate Markdown document
        markdown_content = _format_spec_as_markdown(spec)
        
        # Return as Markdown file
        return Response(
            content=markdown_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{feature_id}_spec.md"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate document: {str(e)}")


def _format_spec_as_markdown(spec: CanonicalSpec) -> str:
    """
    Format a CanonicalSpec as a Markdown document following the Canonical Spec MVP Schema.
    
    This follows the structure defined in docs/mvp_contracts/01_canonical_spec_mvp_schema.md
    """
    lines = []
    
    # Header - Feature Metadata
    lines.append(f"# {spec.feature.title or spec.feature.feature_id}")
    lines.append("")
    lines.append("## Feature Metadata")
    lines.append("")
    lines.append(f"- **Feature ID**: `{spec.feature.feature_id}`")
    lines.append(f"- **Title**: {spec.feature.title or '*No title*'}")
    lines.append(f"- **Status**: `{spec.feature.status.value}`")
    lines.append(f"- **Schema Version**: `{spec.schema_version}`")
    lines.append(f"- **Spec Version**: `{spec.meta.spec_version or 'N/A'}`")
    lines.append(f"- **Created**: {spec.feature.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"- **Updated**: {spec.feature.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    
    # Project Context Reference
    if spec.project_context_ref:
        ctx = spec.project_context_ref
        if ctx.project_id or ctx.project_record_id or ctx.mentor_user_id or ctx.intern_user_id:
            lines.append("## Project Context Reference")
            lines.append("")
            if ctx.project_id:
                lines.append(f"- **Project ID**: `{ctx.project_id}`")
            if ctx.context_version:
                lines.append(f"- **Context Version**: `{ctx.context_version}`")
            if ctx.project_record_id:
                lines.append(f"- **Project Record ID**: `{ctx.project_record_id}`")
            if ctx.mentor_user_id:
                lines.append(f"- **Mentor User ID**: `{ctx.mentor_user_id}`")
            if ctx.intern_user_id:
                lines.append(f"- **Intern User ID**: `{ctx.intern_user_id}`")
            lines.append("")
    
    # Spec Section
    lines.append("## Spec")
    lines.append("")
    
    # Goal (Required)
    lines.append("### Goal")
    lines.append("")
    if spec.spec.goal:
        lines.append(spec.spec.goal)
    else:
        lines.append("*No goal specified*")
    lines.append("")
    
    # Background (Optional)
    if spec.spec.background:
        lines.append("### Background")
        lines.append("")
        lines.append(spec.spec.background)
        lines.append("")
    
    # Non-Goals (Required, but can be empty array)
    lines.append("### Non-Goals")
    lines.append("")
    if spec.spec.non_goals:
        for non_goal in spec.spec.non_goals:
            lines.append(f"- {non_goal}")
    else:
        lines.append("*None specified*")
    lines.append("")
    
    # Acceptance Criteria (Required)
    lines.append("### Acceptance Criteria")
    lines.append("")
    if spec.spec.acceptance_criteria:
        for ac in spec.spec.acceptance_criteria:
            lines.append(f"#### {ac.id}")
            lines.append("")
            lines.append(f"**Criteria**: {ac.criteria}")
            if ac.test_hint:
                lines.append("")
                lines.append(f"**Test Hint**: {ac.test_hint}")
            lines.append("")
    else:
        lines.append("*No acceptance criteria specified*")
        lines.append("")
    
    # Planning Section
    lines.append("## Planning")
    lines.append("")
    
    # MVP Definition (Optional)
    if spec.planning and spec.planning.mvp_definition:
        mvp = spec.planning.mvp_definition
        lines.append("### MVP Definition")
        lines.append("")
        if mvp.mvp_goal:
            lines.append(f"**MVP Goal**: {mvp.mvp_goal}")
            lines.append("")
        if mvp.mvp_cut_lines:
            lines.append("**MVP Cut Lines**:")
            lines.append("")
            for cut_line in mvp.mvp_cut_lines:
                lines.append(f"- {cut_line}")
            lines.append("")
        if mvp.mvp_risks:
            lines.append("**MVP Risks**:")
            lines.append("")
            for risk in mvp.mvp_risks:
                lines.append(f"- {risk}")
            lines.append("")
    
    # Known Assumptions
    if spec.planning and spec.planning.known_assumptions:
        lines.append("### Known Assumptions")
        lines.append("")
        for assumption in spec.planning.known_assumptions:
            lines.append(f"- {assumption}")
        lines.append("")
    
    # Constraints
    if spec.planning and spec.planning.constraints:
        lines.append("### Constraints")
        lines.append("")
        for constraint in spec.planning.constraints:
            lines.append(f"- {constraint}")
        lines.append("")
    
    # Tasks
    if spec.planning:
        lines.append("### Tasks")
        lines.append("")
        if spec.planning.tasks:
            for task in spec.planning.tasks:
                lines.append(f"#### {task.task_id}: {task.title}")
                lines.append("")
                lines.append(f"- **Type**: `{task.type.value}`")
                lines.append(f"- **Scope**: {task.scope}")
                if task.owner_role:
                    lines.append(f"- **Owner Role**: `{task.owner_role}`")
                if task.estimate:
                    lines.append(f"- **Estimate**: {task.estimate.value} {task.estimate.unit}(s)")
                if task.deliverables:
                    lines.append("- **Deliverables**:")
                    for deliverable in task.deliverables:
                        lines.append(f"  - {deliverable}")
                if task.dependencies:
                    lines.append(f"- **Dependencies**: {', '.join(task.dependencies)}")
                if task.affected_components:
                    lines.append("- **Affected Components**:")
                    for component in task.affected_components:
                        lines.append(f"  - {component}")
                lines.append("")
        else:
            lines.append("*No tasks specified*")
            lines.append("")
        
        # V&V Items
        lines.append("### Verification & Validation")
        lines.append("")
        if spec.planning.vv:
            for vv in spec.planning.vv:
                lines.append(f"#### {vv.vv_id} (for {vv.task_id})")
                lines.append("")
                lines.append(f"- **Type**: `{vv.type.value}`")
                lines.append(f"- **Procedure**: {vv.procedure}")
                lines.append(f"- **Expected Result**: {vv.expected_result}")
                if vv.evidence_required:
                    lines.append("- **Evidence Required**:")
                    for evidence in vv.evidence_required:
                        lines.append(f"  - {evidence}")
                lines.append("")
        else:
            lines.append("*No V&V items specified*")
            lines.append("")
    
    # Quality Assessment
    lines.append("## Quality Assessment")
    lines.append("")
    lines.append(f"- **Completeness Score**: {spec.quality.completeness_score:.2%}")
    if spec.quality.missing_fields:
        lines.append("- **Missing Fields**:")
        for field in spec.quality.missing_fields:
            lines.append(f"  - **{field.path}**: {field.reason}")
    else:
        lines.append("- **Missing Fields**: *None*")
    lines.append("")
    
    # Decision
    lines.append("## Decision")
    lines.append("")
    lines.append(f"- **Recommendation**: `{spec.decision.recommendation}`")
    if spec.decision.rationale:
        lines.append("- **Rationale**:")
        for reason in spec.decision.rationale:
            lines.append(f"  - {reason}")
    else:
        lines.append("- **Rationale**: *None provided*")
    lines.append("")
    
    # Metadata
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **Spec Version**: `{spec.meta.spec_version or 'N/A'}`")
    if spec.meta.source_artifacts:
        lines.append("- **Source Artifacts**:")
        for artifact in spec.meta.source_artifacts:
            lines.append(f"  - **{artifact.type.value}**: {artifact.ref}")
    else:
        lines.append("- **Source Artifacts**: *None*")
    if spec.meta.extensions:
        lines.append(f"- **Extensions**: {len(spec.meta.extensions)} extension(s)")
    lines.append("")
    
    return "\n".join(lines)


@app.post("/api/v1/feishu/read")
async def feishu_read(body: dict):
    """
    Read Feishu document content.

    Request body:
    {
        "url": "https://xxx.feishu.cn/docx/XXXX" (optional),
        "document_token": "document_id" (optional),
        "wiki_token": "node_token" (optional, requires wiki_space_id),
        "wiki_space_id": "space_id" (optional, required when wiki_token)

    At least one of: url, document_token, or (wiki_token + wiki_space_id).
    """
    try:
        url = body.get("url")
        document_token = body.get("document_token")
        wiki_token = body.get("wiki_token")
        wiki_space_id = body.get("wiki_space_id")

        if not url and not document_token and not (wiki_token and wiki_space_id):
            raise HTTPException(
                status_code=400,
                detail="Provide at least one of: url, document_token, or (wiki_token + wiki_space_id)",
            )

        reader = FeishuReader()
        result = reader.read(
            url=url,
            document_token=document_token,
            wiki_token=wiki_token,
            wiki_space_id=wiki_space_id,
        )

        if result.get("debug"):
            code = result["debug"].get("code", 500)
            msg = result["debug"].get("msg", "Unknown error")
            if code == 403:
                raise HTTPException(status_code=403, detail=msg)
            if code == 404:
                raise HTTPException(status_code=404, detail=msg)
            if code == 429:
                raise HTTPException(status_code=429, detail=msg)
            raise HTTPException(status_code=502, detail=msg)

        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Transcribe audio to text using AI Builder Space API.
    
    Requires CANONICAL_AI_BUILDER_TOKEN environment variable to be set.
    """
    try:
        # Check if AI client is configured
        if not ai_client:
            return {
                "text": "",
                "message": "Transcription service not configured. Please set CANONICAL_AI_BUILDER_TOKEN environment variable to enable voice input."
            }
        
        # Read audio file
        audio_data = await audio_file.read()
        
        # Transcribe using AI Builder Space API
        result = await ai_client.transcribe_audio(audio_data)
        
        return {
            "text": result.get("text", ""),
            "language": result.get("detected_language"),
            "confidence": result.get("confidence")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
