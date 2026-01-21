# Canonical Spec MVP Schema

## 层级定义
**层级名称**：Canonical Spec（唯一事实源）  
**数据源（SoT）**：`CanonicalSpecStore`（内部存储，版本化）  
**核心程序**：LLM Compiler（抽取/补全/提问生成）

## 输入
- **用户输入**：任意质量（一句话/对话/文档/repo context）
- **Project Context Ref**（可选）：`project_id` + `context_version`

## 输出结构（MVP 最小字段集）

### JSON Schema（最小示例）

```json
{
  "schema_version": "1.0",
  "feature": {
    "feature_id": "F-2026-001",
    "title": "短标题",
    "status": "draft|clarifying|executable_ready|published|hold|drop",
    "created_at": "2026-01-13T10:00:00Z",
    "updated_at": "2026-01-13T10:05:00Z"
  },
  "project_context_ref": {
    "project_id": "P-xxx",
    "context_version": "C-12",
    "project_record_id": "recv83AoVSDMQP",
    "mentor_user_id": "ou_xxx",
    "intern_user_id": "ou_yyy"
  },
  "spec": {
    "goal": "要解决的核心问题/用户价值",
    "non_goals": ["明确不做什么"],
    "acceptance_criteria": [
      { "id": "AC-1", "criteria": "可验证的验收标准", "test_hint": "可选：如何测" }
    ]
  },
  "planning": {
    "tasks": [
      {
        "task_id": "T-1",
        "title": "任务标题",
        "type": "dev|test|doc|ops|design|research",
        "scope": "任务范围",
        "deliverables": ["产物：文件/接口/脚本"],
        "owner_role": "dev|qa|pm|ops",
        "estimate": { "unit": "hour|day", "value": 4 },
        "dependencies": ["T-0"],
        "affected_components": ["backend/app/..."]
      }
    ],
    "vv": [
      {
        "vv_id": "VV-1",
        "task_id": "T-1",
        "type": "unit|integration|e2e|manual|benchmark",
        "procedure": "可复制粘贴的验证步骤",
        "expected_result": "预期结果",
        "evidence_required": ["log_snippet|screenshot|test_report"]
      }
    ]
  },
  "quality": {
    "completeness_score": 0.72,
    "missing_fields": [
      { "path": "spec.goal", "reason": "缺目标导致无法拆任务" }
    ]
  },
  "decision": {
    "recommendation": "go|hold|drop",
    "rationale": ["理由列表"]
  },
  "meta": {
    "spec_version": "S-20260113-0003",
    "source_artifacts": [
      { "type": "doc|chat|repo|file", "ref": "..." }
    ]
  }
}
```

### 字段表（必填/可选/来源/用途/校验）

| 字段路径 | 必填 | 来源 | 用途 | 校验规则 |
|---------|------|------|------|----------|
| `feature.feature_id` | ✅ | 系统生成 | 唯一标识 | 格式：`F-YYYY-NNN` |
| `feature.status` | ✅ | 系统更新 | 状态机 | 枚举：draft/clarifying/executable_ready/published/hold/drop |
| `feature.created_at` | ✅ | 系统生成 | 审计 | ISO 8601 |
| `feature.updated_at` | ✅ | 系统更新 | 审计 | ISO 8601 |
| `project_context_ref.project_id` | ⚠️ | 用户输入/系统 | 项目关联 | 格式：`P-xxx`（可选） |
| `project_context_ref.context_version` | ⚠️ | 系统生成 | Context 版本 | 格式：`C-NN`（可选） |
| `project_context_ref.project_record_id` | ⚠️ | 用户输入/系统 | Feishu 项目记录ID | 字符串（发布时必填） |
| `project_context_ref.mentor_user_id` | ⚠️ | 用户输入/系统 | Feishu 负责人用户ID | 字符串（可选，映射到"需求负责人"） |
| `project_context_ref.intern_user_id` | ⚠️ | 用户输入/系统 | Feishu 执行人用户ID | 字符串（可选，映射到"执行成员"） |
| `spec.goal` | ✅ | LLM 抽取 | Gate S 必填 | 非空字符串，长度 10-500 |
| `spec.non_goals` | ✅ | LLM 抽取 | 范围界定 | 数组（可为空 `[]`） |
| `spec.acceptance_criteria` | ✅ | LLM 抽取 | Gate S 必填 | 数组，至少 1 条，每条有 `id` + `criteria` |
| `planning.tasks` | ⚠️ | LLM 生成 | Gate T 判定 | 数组（可为空 `[]`，但 publish 前必须 ≥1） |
| `planning.vv` | ⚠️ | LLM 生成 | Gate V 判定 | 数组（可为空 `[]`，但每个 task 至少 1 个 vv） |
| `quality.completeness_score` | ✅ | Gate 计算 | 辅助决策 | 0.0-1.0，deterministic |
| `quality.missing_fields` | ✅ | Gate 计算 | 澄清依据 | 数组（可为空 `[]`） |
| `decision.recommendation` | ✅ | Gate + 人工 | 决策建议 | 枚举：go/hold/drop |
| `meta.spec_version` | ✅ | 系统生成 | 版本标识 | 格式：`S-YYYYMMDD-NNNN`，不可变 |

### 字段说明

#### `planning.tasks[]` 结构
- `task_id`：格式 `T-N`（N 从 1 开始）
- `type`：枚举值（dev/test/doc/ops/design/research）
- `dependencies`：数组，引用其他 `task_id`
- `gate.requires/provides`：Gate 依赖关系（MVP 暂不强制）

#### `planning.vv[]` 结构
- `vv_id`：格式 `VV-N`
- `task_id`：必须引用已存在的 `task_id`
- `type`：枚举值（unit/integration/e2e/manual/benchmark）
- `evidence_required`：数组，指定需要的证据类型

## 约束规则

### 硬约束（违反则拒绝）
1. **不允许混入执行系统字段**：Canonical Spec 不得包含任何 Feishu 字段名/表结构
2. **版本不可变**：`meta.spec_version` 一旦生成不可修改（新版本必须生成新的）
3. **任务-VV 绑定**：每个 `task` 在 publish 前必须至少有一个 `vv` 绑定

### 软约束（违反则记录到 `missing_fields`）
- `spec.goal` 长度 < 10 或 > 500
- `acceptance_criteria` 数量 = 0
- `planning.tasks` 数量 = 0（publish 前）
- `planning.vv` 数量 < `planning.tasks` 数量（publish 前）

## 检验标准

### 输入 → 输出验证
- **任意输入**（包括空字符串）必须能产生一个合法的 Canonical Spec（至少 `draft` 状态）
- **缺失点**必须被结构化记录到 `quality.missing_fields[]`（不得丢失）
- **版本生成（不可变策略）**：每次成功编译/更新必须生成新的 `spec_version`（包括 `compile`、`apply_answers`、`plan_tasks`、`generate_vv` 等所有修改 Spec 内容的步骤）。`spec_version` 一旦生成不可修改，旧版本只读可追溯。

### 可重放性
- 给定相同的输入 + `project_context_ref`，多次编译应产生相同的 `spec_version`（或明确记录差异原因）
- **版本单调性**：同一 `feature_id` 的 `spec_version` 必须单调递增，不允许回退或重复

## Project Context Ref 结构说明

### 字段定义
- `project_id`：项目标识符（可选，用于跨 feature 共享 context）
- `context_version`：Context 版本号（可选，用于追溯 Project Context Dossier 版本）
- `project_record_id`：Feishu 多维表格中的项目记录ID（发布时必填，映射到"所属项目"字段）
- `mentor_user_id`：Feishu 用户ID，负责人（可选，映射到"需求负责人"字段）
- `intern_user_id`：Feishu 用户ID，执行人（可选，映射到"执行成员"字段）

### 获取方式
- **CLI 参数**：`canonical run --project-record-id xxx --mentor-user-id yyy`
- **配置文件**：从 `~/.canonical/config.yaml` 读取默认值
- **环境变量**：`CANONICAL_PROJECT_RECORD_ID`、`CANONICAL_MENTOR_USER_ID` 等

## 失败姿势

| 失败场景 | 处理方式 | 输出 |
|---------|---------|------|
| 输入完全无法解析 | 生成 `draft` 状态，`missing_fields` 包含 `spec.goal` | 进入澄清流程 |
| LLM 调用失败 | 返回错误，记录到 Evidence，不生成 Spec | 错误信息 + 重试建议 |
| 版本冲突（并发编辑） | 返回冲突错误，要求用户选择版本 | 用户选择合并/覆盖 |
| `project_context_ref.project_record_id` 缺失（发布时） | 拒绝发布，返回错误 | 错误信息："project_record_id required for publish" |