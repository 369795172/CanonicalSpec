## Success Criteria
- A reader can run the Canonical Spec pipeline end-to-end (run -> plan -> vv -> review -> publish).
- A reader can provide missing fields (including background) when gates fail.
- An AI prompt can reliably create Feishu demand entries from a Canonical Spec.

## Why This Doc
You likely want a stable, repeatable way to turn messy task notes into Feishu demand entries.
This guide focuses on what to do, in what order, and what must be present for publish.

## What The Tool Is
The Canonical Spec tool is a CLI pipeline that turns input text into a structured spec,
plans tasks and validation, then publishes to Feishu Bitable.

Core pipeline (see `docs/mvp_contracts/03_orchestrator_steps_io.md`):
`ingest -> compile -> validate_gates -> plan_tasks -> generate_vv -> manual_review -> publish`

## What It Produces
- Canonical Spec (single source of truth)
- Planning tasks (T-N)
- Verification & Validation items (VV-N)
- Feishu record (idempotent publish)

## What You Must Provide For Publish
Minimum required fields for a successful publish:
- `feature.title` (maps to Feishu: 反馈问题)
- `spec.goal`
- `spec.acceptance_criteria`
- `planning.tasks`
- `planning.vv`
- `project_context_ref.project_record_id` (Feishu project record id)
- `feature.status = executable_ready` (set by review step)

Strongly recommended:
- `spec.background` (used in the Feishu 用户故事 field)

## Quick Start (Human)
### 1) Prepare input text (markdown or plain text)
Include at least goal, background, and acceptance criteria.

Example input:
```
标题: Phase 2: Data Repair Script

背景:
历史同步数据存在重复课程与错误的解锁时间，导致统计和学习进度异常。

目标:
创建数据修复脚本，修复现有数据问题（重复课程、解锁时间）。

验收标准:
- AC-1: 脚本可修复重复课程且无新增重复。
- AC-2: 解锁时间修复后与规则一致。
```

### 2) Run the pipeline
```
cd /Users/marvi/AndroidStudioProjects/canonical_frontend
source venv/bin/activate

python -m canonical.cli run --input /absolute/path/to/input.md
python -m canonical.cli plan F-2026-001
python -m canonical.cli vv F-2026-001
python -m canonical.cli review F-2026-001 --decision go
python -m canonical.cli publish F-2026-001
```

### 3) If Gate S/T/V fails, answer missing fields
```
python -m canonical.cli answer F-2026-001 --answer "spec.background=补充背景信息"
python -m canonical.cli answer F-2026-001 --answer "spec.acceptance_criteria=[...]"
```

## Quick Start (AI Prompt)
Use these prompts with a Canonical Spec document or plan file.

### Prompt A (Plan -> Feishu)
```
请根据 Canonical Spec 文档，将 {任务/计划} 在飞书多维表格里创建对应的需求条目。
要求：
1) 按 Phase 分组生成需求
2) 必填字段最小化（反馈问题、用户故事）
3) 用户故事需包含背景、目标、验收标准
```

### Prompt B (Existing Logs -> Feishu)
```
请根据 Canonical Spec 文档，帮我将 XXX 任务日志在飞书多维表格里创建对应的需求条目。
注意：
- 如果缺字段先补齐（尤其是背景）
- 发布前必须通过 Gate S/T/V
```

## How Feishu "用户故事" Is Built
The Feishu template includes background when present.
See: `canonical/adapters/feishu.py` and `docs/mvp_contracts/04_feishu_publish_contract.md`.

Template order:
1) Background (if provided)
2) Goal
3) Non-goals
4) Acceptance criteria
5) Tasks
6) V&V

## Common Failure Points
- Missing `project_context_ref.project_record_id` (publish required).
- Gate S fails because `spec.acceptance_criteria` or `spec.background` is empty.
- Gate T fails because `planning.tasks` is empty.
- Gate V fails because `planning.vv` is empty or has invalid `task_id`.

## References
- Canonical Spec schema: `docs/mvp_contracts/01_canonical_spec_mvp_schema.md`
- Gate model: `docs/mvp_contracts/02_gate_model.md`
- Orchestrator steps: `docs/mvp_contracts/03_orchestrator_steps_io.md`
- Feishu publish contract: `docs/mvp_contracts/04_feishu_publish_contract.md`
- Script example: `scripts/plan_to_feishu.py` and `scripts/README.md`
