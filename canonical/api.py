"""
Canonical API Server
FastAPI server for canonical frontend
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
