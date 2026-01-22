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
from canonical.engine.orchestrator import Orchestrator
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


@app.on_event("startup")
async def startup():
    """Initialize AI client on startup if token is configured."""
    global ai_client
    if config.ai_builder_token:
        try:
            ai_client = AIClient(
                token=config.ai_builder_token,
                base_url=config.ai_builder_base_url
            )
        except Exception as e:
            print(f"Warning: Failed to initialize AI client: {e}")
            ai_client = None


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
        
        return {
            "feature_id": spec.feature.feature_id,
            "feature": {
                "feature_id": spec.feature.feature_id,
                "title": spec.feature.title or "",
                "status": spec.feature.status.value if isinstance(spec.feature.status, FeatureStatus) else spec.feature.status,
            },
            "spec": spec.model_dump(mode='json'),
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
        if not input_text:
            raise HTTPException(status_code=400, detail="Input text is required")
        
        # Run the orchestrator pipeline (already saves the spec internally)
        spec, gate_result = orchestrator.run(input_text)
        
        return {
            "feature_id": spec.feature.feature_id,
            "status": "success",
            "message": "Feature created successfully",
            "gate_result": {
                "overall_pass": gate_result.overall_pass,
                "completeness_score": gate_result.completeness_score,
                "next_action": gate_result.next_action,
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
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
