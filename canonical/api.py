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
from canonical.adapters.feishu import FeishuPublisher, MappingConfig
from fastapi.responses import Response

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


@app.post("/api/v1/features/{feature_id}/publish")
async def publish_feature(feature_id: str):
    """
    Publish a feature to Feishu Bitable.
    
    Requires:
    - Feature status must be executable_ready
    - Feishu credentials configured (CANONICAL_FEISHU_APP_ID, CANONICAL_FEISHU_APP_SECRET)
    - project_context_ref.project_record_id must be set in spec
    """
    try:
        # Load spec
        spec = spec_store.load(feature_id)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        
        # Check status
        if spec.feature.status != FeatureStatus.EXECUTABLE_READY:
            raise HTTPException(
                status_code=400,
                detail=f"Feature status must be executable_ready, current: {spec.feature.status.value}. Use review endpoint first."
            )
        
        # Publish to Feishu
        publisher = FeishuPublisher()
        result = publisher.publish(spec)
        
        return {
            "feature_id": feature_id,
            "operation": result["operation"],
            "external_id": result["external_id"],
            "status": result["status"],
            "spec_version": result["spec_version"],
            "message": "发布成功" if result["operation"] != "noop" else "此版本已发布过，无需重复发布"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")


@app.get("/api/v1/features/{feature_id}/document")
async def get_feature_document(feature_id: str):
    """
    Generate Markdown document for a feature.
    
    Returns the formatted document content with validation status and missing field hints.
    """
    try:
        # Load spec
        spec = spec_store.load(feature_id)
        if not spec:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
        
        # Enhanced template with validation hints
        document_template = """---
feature_id: {{ feature.feature_id }}
spec_version: {{ meta.spec_version }}
status: {{ feature.status }}
created_at: {{ feature.created_at }}
updated_at: {{ feature.updated_at }}
---

{% if spec.background %}
## 背景

{{ spec.background }}

{% else %}
## 背景

> ⚠️ **缺失字段**: `spec.background` (强烈推荐)
> 
> 背景信息有助于理解需求的上下文和动机。建议补充此字段以提高文档完整性。

{% endif %}

## 目标

{{ spec.goal }}

## 非目标

{% if spec.non_goals and spec.non_goals|length > 0 %}
{% for ng in spec.non_goals %}- {{ ng }}
{% endfor %}
{% else %}
> 暂无非目标定义
{% endif %}

## 验收标准

{% if spec.acceptance_criteria and spec.acceptance_criteria|length > 0 %}
{% for ac in spec.acceptance_criteria %}- **{{ ac.id }}**: {{ ac.criteria }}
{% if ac.test_hint %}  - *测试提示*: {{ ac.test_hint }}
{% endif %}
{% endfor %}
{% else %}
> ⚠️ **缺失字段**: `spec.acceptance_criteria` (必填)
> 
> 验收标准是 Gate S 验证的必填字段。请补充至少一条验收标准。

{% endif %}

## 任务列表

{% if planning.tasks and planning.tasks|length > 0 %}
{% for task in planning.tasks %}
### {{ task.task_id }}: {{ task.title }}

- **类型**: {{ task.type }}
- **范围**: {{ task.scope }}
{% if task.deliverables and task.deliverables|length > 0 %}
- **交付物**:
{% for deliverable in task.deliverables %}  - {{ deliverable }}
{% endfor %}
{% endif %}
{% if task.estimate %}
- **估算**: {{ task.estimate.value }} {{ task.estimate.unit }}
{% endif %}
{% if task.owner_role %}
- **负责人角色**: {{ task.owner_role }}
{% endif %}
{% if task.dependencies and task.dependencies|length > 0 %}
- **依赖**: {{ task.dependencies|join(', ') }}
{% endif %}
{% if task.affected_components and task.affected_components|length > 0 %}
- **影响组件**: {{ task.affected_components|join(', ') }}
{% endif %}

{% endfor %}
{% else %}
> ⚠️ **缺失字段**: `planning.tasks` (必填)
> 
> 任务列表是 Gate T 验证的必填字段。请使用以下命令生成任务：
> ```bash
> python -m canonical.cli plan {{ feature.feature_id }}
> ```

{% endif %}

## 验证要求

{% if planning.vv and planning.vv|length > 0 %}
{% for vv in planning.vv %}
### {{ vv.vv_id }}: {{ vv.type|upper }} 验证

- **关联任务**: {{ vv.task_id }}
- **验证步骤**: {{ vv.procedure }}
- **预期结果**: {{ vv.expected_result }}
{% if vv.evidence_required and vv.evidence_required|length > 0 %}
- **所需证据**:
{% for evidence in vv.evidence_required %}  - {{ evidence }}
{% endfor %}
{% endif %}

{% endfor %}
{% else %}
> ⚠️ **缺失字段**: `planning.vv` (必填)
> 
> 验证要求是 Gate V 验证的必填字段。请使用以下命令生成验证项：
> ```bash
> python -m canonical.cli vv {{ feature.feature_id }}
> ```
> 
> 注意：验证项数量必须 >= 任务数量（每个任务至少一个验证点）。

{% endif %}

{% if planning.known_assumptions and planning.known_assumptions|length > 0 %}
## 已知假设

{% for assumption in planning.known_assumptions %}- {{ assumption }}
{% endfor %}

{% endif %}

{% if planning.constraints and planning.constraints|length > 0 %}
## 约束条件

{% for constraint in planning.constraints %}- {{ constraint }}
{% endfor %}

{% endif %}

{% if planning.mvp_definition %}
## MVP 定义

{% if planning.mvp_definition.mvp_goal %}
### MVP 目标

{{ planning.mvp_definition.mvp_goal }}
{% endif %}

{% if planning.mvp_definition.mvp_cut_lines and planning.mvp_definition.mvp_cut_lines|length > 0 %}
### MVP 砍线

{% for cut_line in planning.mvp_definition.mvp_cut_lines %}- {{ cut_line }}
{% endfor %}
{% endif %}

{% if planning.mvp_definition.mvp_risks and planning.mvp_definition.mvp_risks|length > 0 %}
### MVP 风险

{% for risk in planning.mvp_definition.mvp_risks %}- {{ risk }}
{% endfor %}
{% endif %}

{% endif %}

{% if quality.completeness_score > 0 or quality.missing_fields|length > 0 %}
## 质量评估

- **完整度评分**: {{ "%.2f"|format(quality.completeness_score) }}/1.00

{% if quality.missing_fields and quality.missing_fields|length > 0 %}
### 缺失字段列表

{% for missing_field in quality.missing_fields %}- **{{ missing_field.path }}**: {{ missing_field.reason }}
{% endfor %}
{% endif %}

{% endif %}

{% if decision.recommendation != 'hold' or decision.rationale|length > 0 %}
## 决策建议

- **建议**: {{ decision.recommendation|upper }}

{% if decision.rationale and decision.rationale|length > 0 %}
### 理由

{% for reason in decision.rationale %}- {{ reason }}
{% endfor %}
{% endif %}

{% endif %}

{% if spec.project_context_ref %}
## 项目上下文

{% if spec.project_context_ref.project_id %}
- **项目ID**: {{ spec.project_context_ref.project_id }}
{% endif %}
{% if spec.project_context_ref.context_version %}
- **上下文版本**: {{ spec.project_context_ref.context_version }}
{% endif %}
{% if spec.project_context_ref.project_record_id %}
- **飞书项目记录ID**: {{ spec.project_context_ref.project_record_id }}
{% endif %}
{% if spec.project_context_ref.mentor_user_id %}
- **需求负责人**: {{ spec.project_context_ref.mentor_user_id }}
{% endif %}
{% if spec.project_context_ref.intern_user_id %}
- **执行成员**: {{ spec.project_context_ref.intern_user_id }}
{% endif %}

{% endif %}

{% if meta.source_artifacts and meta.source_artifacts|length > 0 %}
## 来源工件

{% for artifact in meta.source_artifacts %}- **{{ artifact.type }}**: {{ artifact.ref }}
{% endfor %}

{% endif %}

---

## 发布状态检查

{% set missing_fields = [] %}
{% if not spec.background %}{% set _ = missing_fields.append('spec.background (强烈推荐)') %}{% endif %}
{% if not spec.acceptance_criteria or spec.acceptance_criteria|length == 0 %}{% set _ = missing_fields.append('spec.acceptance_criteria (必填)') %}{% endif %}
{% if not planning.tasks or planning.tasks|length == 0 %}{% set _ = missing_fields.append('planning.tasks (必填)') %}{% endif %}
{% if not planning.vv or planning.vv|length == 0 %}{% set _ = missing_fields.append('planning.vv (必填)') %}{% endif %}
{% if not spec.project_context_ref or not spec.project_context_ref.project_record_id %}{% set _ = missing_fields.append('project_context_ref.project_record_id (必填)') %}{% endif %}
{% if feature.status != 'executable_ready' %}{% set _ = missing_fields.append('feature.status = executable_ready (必填)') %}{% endif %}

{% if missing_fields|length > 0 %}
### ⚠️ 缺失字段（发布前需补齐）

{% for field in missing_fields %}- {{ field }}
{% endfor %}

### 下一步操作

1. **补充缺失字段**:
   ```bash
   python -m canonical.cli answer {{ feature.feature_id }} --answer "spec.background=补充背景信息"
   ```

2. **生成任务和验证项**:
   ```bash
   python -m canonical.cli plan {{ feature.feature_id }}
   python -m canonical.cli vv {{ feature.feature_id }}
   ```

3. **人工评审**:
   ```bash
   python -m canonical.cli review {{ feature.feature_id }} --decision go
   ```

4. **发布到飞书**:
   ```bash
   python -m canonical.cli publish {{ feature.feature_id }}
   ```

{% else %}
### ✅ 所有必填字段已就绪

当前状态: `{{ feature.status }}`

{% if feature.status == 'executable_ready' %}
可以使用以下命令发布到飞书：
```bash
python -m canonical.cli publish {{ feature.feature_id }}
```
{% else %}
请先进行人工评审：
```bash
python -m canonical.cli review {{ feature.feature_id }} --decision go
```
{% endif %}

{% endif %}
"""
        
        # Render template
        from jinja2 import Template
        template = Template(document_template)
        spec_dict = spec.model_dump()
        document_content = template.render(**spec_dict)
        
        # Return as plain text response
        return Response(
            content=document_content,
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
        raise HTTPException(status_code=500, detail=f"Document generation failed: {str(e)}")
