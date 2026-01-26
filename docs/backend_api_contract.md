# Canonical Spec 后端 API 规范文档

本文档定义了 Canonical Spec 工具的后端 API 完整规范，作为前后端开发契约。

## 版本信息

- **API 版本**: v1
- **文档版本**: 1.0.1
- **最后更新**: 2026-01-24

## ⚠️ 重要说明

本文档定义了**完整的 API 规范**，但并非所有 API 都已实现。实际实现状态请参考 [API 实现状态跟踪表](./api_status.md)。

**已实现的 API**（8个）:
- ✅ `GET /api/v1/system/health`
- ✅ `GET /api/v1/features`
- ✅ `GET /api/v1/features/{feature_id}`
- ✅ `POST /api/v1/run`
- ✅ `POST /api/v1/features/{feature_id}/answer`
- ✅ `POST /api/v1/refine`
- ✅ `POST /api/v1/refine/feedback`
- ✅ `POST /api/v1/transcribe`

**未实现的 API**（4个，但底层方法已存在）:
- 📋 `POST /api/v1/features/{feature_id}/plan` - orchestrator.plan_tasks() 已实现，但未暴露为 API
- 📋 `POST /api/v1/features/{feature_id}/vv` - orchestrator.generate_vv() 已实现，但未暴露为 API
- 📋 `POST /api/v1/features/{feature_id}/review` - orchestrator.review() 已实现，但未暴露为 API
- 📋 `POST /api/v1/features/{feature_id}/publish` - CLI publish() 已实现，但未暴露为 API

## 基础信息

### Base URL

- **开发环境**: `http://localhost:8000`
- **生产环境**: (待配置)

### 认证方式

当前 MVP 阶段暂不需要认证，未来版本可能添加 JWT 或 API Key 认证。

### 响应格式

所有 API 响应统一使用 JSON 格式，HTTP 状态码遵循 RESTful 规范。

### 错误响应标准格式

```json
{
  "detail": "错误描述信息",
  "error_code": "ERROR_CODE",
  "field": "字段路径（可选）"
}
```

常见 HTTP 状态码：
- `200` - 成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误

## API 端点列表

### 1. 系统健康检查

#### `GET /api/v1/system/health`

检查后端服务健康状态。

**请求参数**: 无

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-24T10:00:00Z"
}
```

---

### 2. 功能列表

#### `GET /api/v1/features`

获取所有功能的列表（摘要信息）。

**请求参数**:
- `status` (可选, query): 过滤状态，可选值: `draft`, `clarifying`, `executable_ready`, `published`, `hold`, `drop`
- `limit` (可选, query): 返回数量限制，默认 100
- `offset` (可选, query): 分页偏移量，默认 0

**响应示例**:
```json
{
  "features": [
    {
      "feature_id": "F-2026-001",
      "title": "用户登录功能",
      "status": "clarifying",
      "created_at": "2026-01-13T10:00:00Z",
      "updated_at": "2026-01-13T10:05:00Z",
      "spec": {
        "goal": "实现用户登录功能..."
      }
    }
  ],
  "total": 10,
  "limit": 100,
  "offset": 0
}
```

---

### 3. 获取功能详情

#### `GET /api/v1/features/{feature_id}`

获取单个功能的完整详情，包括 Canonical Spec、Gate 结果等。

**路径参数**:
- `feature_id` (必需): 功能 ID，格式: `F-YYYY-NNN`

**响应示例**:
```json
{
  "feature": {
    "feature_id": "F-2026-001",
    "title": "用户登录功能",
    "status": "clarifying",
    "created_at": "2026-01-13T10:00:00Z",
    "updated_at": "2026-01-13T10:05:00Z"
  },
  "spec": {
    "schema_version": "1.0",
    "feature": {
      "feature_id": "F-2026-001",
      "title": "用户登录功能",
      "status": "clarifying"
    },
    "project_context_ref": {
      "project_id": "P-xxx",
      "context_version": "C-12",
      "project_record_id": "recv83AoVSDMQP",
      "mentor_user_id": "ou_xxx",
      "intern_user_id": "ou_yyy"
    },
    "spec": {
      "goal": "实现用户登录功能，支持用户名密码登录",
      "non_goals": ["不实现第三方登录", "不实现记住密码"],
      "acceptance_criteria": [
        {
          "id": "AC-1",
          "criteria": "用户可以使用用户名和密码登录",
          "test_hint": "输入正确的用户名和密码，验证登录成功"
        }
      ]
    },
    "planning": {
      "tasks": [],
      "vv": []
    },
    "quality": {
      "completeness_score": 0.65,
      "missing_fields": [
        {
          "path": "planning.tasks",
          "reason": "tasks 数量为 0，无法形成可执行最小任务集"
        }
      ]
    },
    "decision": {
      "recommendation": "go",
      "rationale": []
    },
    "meta": {
      "spec_version": "S-20260113-0001",
      "source_artifacts": []
    }
  },
  "gate_result": {
    "gate_s": {
      "pass": true,
      "missing_fields": [],
      "reasons": []
    },
    "gate_t": {
      "pass": false,
      "missing_fields": [
        {
          "path": "planning.tasks",
          "reason": "tasks 数量为 0，无法形成可执行最小任务集"
        }
      ],
      "reasons": ["Gate T fail: 至少需要 1 个 task"]
    },
    "gate_v": {
      "pass": false,
      "missing_fields": [
        {
          "path": "planning.vv",
          "reason": "vv 数量少于 tasks 数量"
        }
      ],
      "reasons": ["Gate V fail: 每个 task 至少需要 1 个 vv"]
    },
    "completeness_score": 0.65,
    "weighted_details": {
      "goal_quality": 0.8,
      "acceptance_criteria_quality": 0.7,
      "tasks_quality": 0.0,
      "vv_quality": 0.0
    },
    "overall_pass": false,
    "next_action": "clarify",
    "clarify_questions": [
      {
        "id": "Q1",
        "field_path": "planning.tasks",
        "question": "请提供至少 1 个可执行任务",
        "why_asking": "需要明确具体的实现步骤",
        "suggestions": ["开发登录接口", "实现前端登录页面"]
      }
    ]
  }
}
```

**错误响应**:
- `404`: Feature 不存在
```json
{
  "detail": "Feature F-2026-001 not found",
  "error_code": "FEATURE_NOT_FOUND"
}
```

---

### 4. 创建功能（运行 Pipeline）

#### `POST /api/v1/run`

创建新功能，执行完整的 Pipeline：`ingest` → `compile` → `validate_gates`。

**请求体**:
```json
{
  "input": "我想实现一个用户登录功能，支持用户名密码登录",
  "project_context_ref": {
    "project_id": "P-xxx",
    "project_record_id": "recv83AoVSDMQP",
    "mentor_user_id": "ou_xxx",
    "intern_user_id": "ou_yyy"
  },
  "refine_result": {
    "understanding_summary": "...",
    "inferred_assumptions": [],
    "questions": []
  }
}
```

**字段说明**:
- `input` (必需): 用户输入的需求描述
- `project_context_ref` (可选): 项目上下文引用
- `refine_result` (可选): 如果前端已经执行过 refine，可以传入结果

**响应示例**:
```json
{
  "feature_id": "F-2026-001",
  "spec_version": "S-20260113-0001",
  "status": "clarifying",
  "gate_result": {
    "gate_s": {
      "pass": true,
      "missing_fields": [],
      "reasons": []
    },
    "gate_t": {
      "pass": false,
      "missing_fields": [
        {
          "path": "planning.tasks",
          "reason": "tasks 数量为 0"
        }
      ],
      "reasons": ["Gate T fail: 至少需要 1 个 task"]
    },
    "gate_v": {
      "pass": false,
      "missing_fields": [],
      "reasons": []
    },
    "completeness_score": 0.65,
    "overall_pass": false,
    "next_action": "clarify",
    "clarify_questions": [
      {
        "id": "Q1",
        "field_path": "planning.tasks",
        "question": "请提供至少 1 个可执行任务"
      }
    ]
  }
}
```

**错误响应**:
- `400`: 输入为空或格式错误
```json
{
  "detail": "Input cannot be empty",
  "error_code": "INVALID_INPUT"
}
```

---

### 5. 提交澄清答案

#### `POST /api/v1/features/{feature_id}/answer`

提交澄清问题的答案，触发 `apply_answers` → `compile` → `validate_gates`。

**路径参数**:
- `feature_id` (必需): 功能 ID

**请求体**:
```json
{
  "answers": {
    "planning.tasks": "T-1: 开发登录接口\nT-2: 实现前端登录页面",
    "spec.background": "当前系统缺少用户认证功能"
  }
}
```

**字段说明**:
- `answers` (必需): 字段路径到答案的映射，key 为 `gate_result.clarify_questions[].field_path`

**响应示例**:
```json
{
  "feature": {
    "feature_id": "F-2026-001",
    "status": "executable_ready",
    "updated_at": "2026-01-13T10:10:00Z"
  },
  "spec": {
    "meta": {
      "spec_version": "S-20260113-0002"
    },
    "planning": {
      "tasks": [
        {
          "task_id": "T-1",
          "title": "开发登录接口",
          "type": "dev",
          "scope": "实现 POST /api/v1/auth/login 接口",
          "deliverables": ["endpoint://POST /api/v1/auth/login"],
          "owner_role": "dev",
          "estimate": {
            "unit": "hour",
            "value": 4
          }
        }
      ]
    }
  },
  "gate_result": {
    "gate_s": {
      "pass": true
    },
    "gate_t": {
      "pass": true
    },
    "gate_v": {
      "pass": false,
      "missing_fields": [
        {
          "path": "planning.vv",
          "reason": "task T-1 没有绑定的 vv"
        }
      ]
    },
    "overall_pass": false,
    "next_action": "generate_vv"
  }
}
```

**错误响应**:
- `400`: 答案格式错误或必填字段缺失
- `404`: Feature 不存在

---

### 6. 生成任务计划

#### `POST /api/v1/features/{feature_id}/plan`

为功能生成任务计划，执行 `plan_tasks` step。

**路径参数**:
- `feature_id` (必需): 功能 ID

**请求体**: 无（可选传入提示信息）

**响应示例**:
```json
{
  "feature": {
    "feature_id": "F-2026-001",
    "status": "executable_ready",
    "updated_at": "2026-01-13T10:15:00Z"
  },
  "spec": {
    "meta": {
      "spec_version": "S-20260113-0003"
    },
    "planning": {
      "tasks": [
        {
          "task_id": "T-1",
          "title": "开发登录接口",
          "type": "dev",
          "scope": "实现 POST /api/v1/auth/login 接口",
          "deliverables": ["endpoint://POST /api/v1/auth/login"],
          "owner_role": "dev",
          "estimate": {
            "unit": "hour",
            "value": 4
          },
          "dependencies": [],
          "affected_components": ["backend/app/routers/auth.py"]
        },
        {
          "task_id": "T-2",
          "title": "实现前端登录页面",
          "type": "dev",
          "scope": "创建登录表单组件",
          "deliverables": ["file://frontend/src/components/LoginForm.tsx"],
          "owner_role": "dev",
          "estimate": {
            "unit": "hour",
            "value": 3
          },
          "dependencies": ["T-1"],
          "affected_components": ["frontend/src/components/"]
        }
      ]
    }
  },
  "gate_result": {
    "gate_t": {
      "pass": true
    },
    "next_action": "generate_vv"
  }
}
```

**错误响应**:
- `400`: Gate S 未通过，无法生成任务
- `404`: Feature 不存在

---

### 7. 生成验证项

#### `POST /api/v1/features/{feature_id}/vv`

为功能生成验证与验证项（V&V），执行 `generate_vv` step。

**路径参数**:
- `feature_id` (必需): 功能 ID

**请求体**: 无

**响应示例**:
```json
{
  "feature": {
    "feature_id": "F-2026-001",
    "status": "executable_ready",
    "updated_at": "2026-01-13T10:20:00Z"
  },
  "spec": {
    "meta": {
      "spec_version": "S-20260113-0004"
    },
    "planning": {
      "vv": [
        {
          "vv_id": "VV-1",
          "task_id": "T-1",
          "type": "integration",
          "procedure": "1. 启动后端服务\n2. 使用 curl 调用 POST /api/v1/auth/login\n3. 传入正确的用户名和密码\n4. 验证返回 200 状态码和 token",
          "expected_result": "返回 200 状态码，响应体包含 access_token 字段",
          "evidence_required": ["log_snippet", "test_report"]
        },
        {
          "vv_id": "VV-2",
          "task_id": "T-2",
          "type": "manual",
          "procedure": "1. 打开前端页面\n2. 输入用户名和密码\n3. 点击登录按钮\n4. 验证跳转到首页",
          "expected_result": "成功跳转到首页，显示用户信息",
          "evidence_required": ["screenshot"]
        }
      ]
    }
  },
  "gate_result": {
    "gate_v": {
      "pass": true
    },
    "overall_pass": true,
    "next_action": "manual_review"
  }
}
```

**错误响应**:
- `400`: Gate T 未通过，无法生成 VV
- `404`: Feature 不存在

---

### 8. 人工确认

#### `POST /api/v1/features/{feature_id}/review`

执行人工确认，设置 `review_decision`。

**路径参数**:
- `feature_id` (必需): 功能 ID

**请求体**:
```json
{
  "decision": "go",
  "rationale": ["需求清晰，可以开始实施"]
}
```

**字段说明**:
- `decision` (必需): 决策，可选值: `go`, `hold`, `drop`
- `rationale` (可选): 决策理由列表

**响应示例**:
```json
{
  "feature": {
    "feature_id": "F-2026-001",
    "status": "executable_ready",
    "updated_at": "2026-01-13T10:25:00Z"
  },
  "spec": {
    "decision": {
      "recommendation": "go",
      "rationale": ["需求清晰，可以开始实施"]
    }
  },
  "review_decision": "go",
  "next_action": "publish"
}
```

**错误响应**:
- `400`: Gate 未全部通过或 decision 值无效
- `404`: Feature 不存在

---

### 9. 发布到飞书

#### `POST /api/v1/features/{feature_id}/publish`

将功能发布到 Feishu 多维表格，执行 `publish` step。

**路径参数**:
- `feature_id` (必需): 功能 ID

**请求体**: 无（可选传入覆盖配置）

**响应示例**:
```json
{
  "operation": "created",
  "external_id": "recv83AoVSDMQP",
  "status": "success",
  "field_map_snapshot": {
    "反馈问题": "用户登录功能",
    "用户故事": "---\nfeature_id: F-2026-001\nspec_version: S-20260113-0004\n---\n\n**目标**:\n实现用户登录功能...",
    "需求状态": "待排期",
    "需求负责人": [],
    "执行成员": [],
    "优先级": "中",
    "需求类型": "新功能",
    "所属项目": ["recv83AoVSDMQP"]
  },
  "publish_record": {
    "target": "feishu",
    "external_id": "recv83AoVSDMQP",
    "spec_version": "S-20260113-0004",
    "operation": "created",
    "published_at": "2026-01-13T10:30:00Z",
    "status": "active"
  },
  "feature": {
    "feature_id": "F-2026-001",
    "status": "published",
    "updated_at": "2026-01-13T10:30:00Z"
  }
}
```

**错误响应**:
- `400`: 
  - Gate 未全部通过
  - `review_decision` 不是 `go`
  - `project_context_ref.project_record_id` 缺失
  - 字段映射失败
- `404`: Feature 不存在
- `409`: 幂等冲突（相同 spec_version 已发布）

**幂等性说明**:
- 幂等键: `feature_id + target + spec_version`
- 相同 `spec_version` 重复发布返回 `operation: "noop"`，不创建新记录
- 新 `spec_version` 发布会更新 Feishu 记录，但 Ledger 中记录为新版本

---

### 10. 需求精炼

#### `POST /api/v1/refine`

对用户输入进行需求精炼分析，生成理解摘要、推断假设、澄清问题等。

**请求体**:
```json
{
  "input": "我想做一个健身网站",
  "context": {
    "conversation_history": [],
    "round": 0,
    "feature_id": null,
    "additional_context": {}
  }
}
```

**字段说明**:
- `input` (必需): 用户输入的需求描述
- `context` (可选): 对话上下文，用于多轮精炼

**响应示例**:
```json
{
  "understanding_summary": "用户希望创建一个健身相关的网站。根据输入，我理解这可能包括：\n1. 用户注册和登录功能\n2. 健身计划管理\n3. 运动记录追踪\n4. 可能包含社交功能（分享、点赞等）",
  "inferred_assumptions": [
    "假设需要用户账户系统",
    "假设需要数据库存储用户数据和健身记录",
    "假设需要响应式设计支持移动端"
  ],
  "questions": [
    {
      "id": "Q1",
      "question": "这个健身网站的主要目标用户是谁？（例如：健身新手、专业教练、健身爱好者）",
      "why_asking": "了解目标用户有助于确定功能优先级和用户体验设计",
      "suggestions": ["健身新手", "专业教练", "健身爱好者", "所有人群"]
    },
    {
      "id": "Q2",
      "question": "你希望网站包含哪些核心功能？（例如：健身计划、运动记录、视频教程、社区互动）",
      "why_asking": "需要明确 MVP 范围，避免功能过于庞大",
      "suggestions": ["健身计划", "运动记录", "视频教程", "社区互动"]
    }
  ],
  "ready_to_compile": false,
  "round": 1
}
```

**字段说明**:
- `ready_to_compile`: 是否可以直接进入编译阶段（无需进一步澄清）
- `round`: 当前精炼轮次

---

### 11. 精炼反馈

#### `POST /api/v1/refine/feedback`

提交对精炼结果的反馈，继续精炼流程。

**请求体**:
```json
{
  "feedback": "Q1: 主要面向健身新手\nQ2: 核心功能包括健身计划和运动记录",
  "context": {
    "conversation_history": [
      {
        "role": "user",
        "content": "我想做一个健身网站"
      },
      {
        "role": "assistant",
        "content": "{上一轮的精炼结果 JSON}"
      }
    ],
    "round": 1,
    "feature_id": null
  }
}
```

**响应示例**:
```json
{
  "understanding_summary": "基于反馈，我更新了理解：\n这是一个面向健身新手的网站，核心功能包括：\n1. 健身计划管理（为新手提供预设计划）\n2. 运动记录追踪（记录每日运动情况）\n3. 基础的用户账户系统",
  "inferred_assumptions": [
    "假设需要预设的健身计划模板",
    "假设需要简单的数据可视化（如运动时长统计）"
  ],
  "questions": [
    {
      "id": "Q3",
      "question": "健身计划是否需要包含视频教程或图文说明？",
      "why_asking": "新手需要详细的指导，确定内容形式有助于规划技术实现",
      "suggestions": ["视频教程", "图文说明", "两者都需要"]
    }
  ],
  "ready_to_compile": false,
  "round": 2
}
```

---

### 12. 语音转文字

#### `POST /api/v1/transcribe`

将音频文件转换为文字（用于语音输入功能）。

**请求体**: `multipart/form-data`
- `audio_file` (必需): 音频文件，支持 WebM 格式

**响应示例**:
```json
{
  "text": "我想实现一个用户登录功能，支持用户名密码登录",
  "language": "zh-CN",
  "confidence": 0.95
}
```

**错误响应**:
- `400`: 文件格式不支持或文件为空
```json
{
  "detail": "Unsupported audio format. Only WebM is supported.",
  "error_code": "UNSUPPORTED_FORMAT"
}
```

---

## 数据 Schema 定义

### Feature 基础结构

```typescript
interface Feature {
  feature_id: string;        // 格式: F-YYYY-NNN
  title: string;
  status: "draft" | "clarifying" | "executable_ready" | "published" | "hold" | "drop";
  created_at: string;        // ISO 8601
  updated_at: string;        // ISO 8601
}
```

### Canonical Spec 完整结构

参考 `docs/mvp_contracts/01_canonical_spec_mvp_schema.md`

### Gate Result 结构

参考 `docs/mvp_contracts/02_gate_model.md`

## 状态流转与 API 调用关系

```mermaid
flowchart TD
    A[POST /api/v1/run] --> B{Gate Pass?}
    B -->|No| C[POST /api/v1/features/{id}/answer]
    C --> D[POST /api/v1/run<br/>重新编译]
    D --> B
    B -->|Yes| E[POST /api/v1/features/{id}/plan]
    E --> F[POST /api/v1/features/{id}/vv]
    F --> G{Gate V Pass?}
    G -->|No| C
    G -->|Yes| H[POST /api/v1/features/{id}/review]
    H --> I{Decision}
    I -->|go| J[POST /api/v1/features/{id}/publish]
    I -->|hold| K[Status: hold]
    I -->|drop| L[Status: drop]
    J --> M[Status: published]
```

## 注意事项

1. **版本不可变性**: `spec_version` 一旦生成不可修改，每次修改 Spec 内容都会生成新版本
2. **幂等性**: `publish` 操作基于 `feature_id + target + spec_version` 保证幂等
3. **Gate 判定**: Gate S/T/V 必须全部通过才能进入 `executable_ready` 状态
4. **人工确认**: `executable_ready` 状态必须经过人工确认才能发布
5. **项目上下文**: `project_context_ref.project_record_id` 在发布时必填

## 参考文档

- [Canonical Spec MVP Schema](./mvp_contracts/01_canonical_spec_mvp_schema.md)
- [Gate Model](./mvp_contracts/02_gate_model.md)
- [Orchestrator Steps I/O](./mvp_contracts/03_orchestrator_steps_io.md)
- [Feishu Publish Contract](./mvp_contracts/04_feishu_publish_contract.md)
