# Feishu Publish Contract（发布契约）

## 层级定义
**层级名称**：Feishu Adapter + Mapping Config + Publish Ledger  
**数据源（SoT）**：Publish Ledger（内部事实源）  
**核心程序**：Feishu Publisher（幂等写入 + 回写 external_id）

## 输入
- **Canonical Spec**：`meta.spec_version` 必须存在（不可变版本标识），`feature.status = executable_ready`
- **Review Decision**：`review_decision = go`（人工确认通过）
- **Mapping Config**：字段映射配置（版本化）

**注意**：Publish 操作不修改 Spec 内容，不生成新 `spec_version`。幂等性基于 `feature_id + target + spec_version` 三元组。

## 输出结构

### Publish Result JSON

```json
{
  "operation": "created|updated|noop",
  "external_id": "recv83AoVSDMQP",
  "status": "success|partial|failed",
  "field_map_snapshot": {
    "反馈问题": "feature.title",
    "用户故事": "spec.goal + spec.acceptance_criteria",
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
    "spec_version": "S-20260113-0003",
    "operation": "created",
    "published_at": "2026-01-13T10:20:00Z",
    "status": "active"
  }
}
```

## Feishu 表结构（严格复用，不新增字段）

### 需求池表格字段清单

基于 `feishu-onboarding-tool` 的现有实现，需求池表格包含以下字段：

| 字段名（中文） | 字段类型 | 用途 | 可映射的 Spec 路径 |
|--------------|---------|------|-------------------|
| `反馈问题` | 文本字段 | 需求标题 | `feature.title` |
| `用户故事` | 文本字段（长文本） | 需求详细描述 | `spec.goal + spec.acceptance_criteria + planning.tasks` |
| `评审` | 单选字段 | 评审状态 | 固定值："审阅" |
| `排期` | 单选字段 | 排期状态 | 固定值："排期" |
| `需求状态` | 单选字段 | 需求状态 | 固定值："待排期"（MVP） |
| `需求负责人` | 人员字段 | 负责人 | 从 `project_context_ref` 获取（可选） |
| `执行成员` | 人员字段 | 执行人 | 从 `project_context_ref` 获取（可选） |
| `优先级` | 单选字段 | 优先级 | 固定值："中"（MVP） |
| `需求类型` | 单选字段 | 需求类型 | 固定值："新功能"（MVP） |
| `所属项目` | 关联字段 | 关联项目表 | 从 `project_context_ref.project_record_id` 获取 |

### 字段映射约束

**关键限制**：
- **不新增字段**：所有映射必须落在上述 10 个字段内
- **不修改字段类型**：字段类型由 Feishu 表结构决定，不可更改
- **固定值字段**：`评审`、`排期`、`需求状态`、`优先级`、`需求类型` 在 MVP 阶段使用固定值

## 字段映射配置（Mapping Config）

### 配置文件结构（YAML）

```yaml
mapping_version: "1.0"
target:
  system: "feishu"
  base_token: "AGGubg32SaLJaCsRB00cpYLlncc"
  table_id: "tblLCcUWtWUq5uyJ"
  project_record_id: "recv83AoVSDMQP"

field_mappings:
  - feishu_field: "反馈问题"
    spec_path: "feature.title"
    transform: "direct"  # direct|template|concat
    required: true

  - feishu_field: "用户故事"
    spec_path: "spec.goal"
    transform: "template"
    template: |
      **目标**:
      {{ spec.goal }}

      **非目标**:
      {{ spec.non_goals | join(', ') }}

      **验收标准**:
      {% for ac in spec.acceptance_criteria %}
      - {{ ac.id }}: {{ ac.criteria }}
      {% endfor %}

      **任务列表**:
      {% for task in planning.tasks %}
      - {{ task.task_id }}: {{ task.title }} ({{ task.type }})
      {% endfor %}

      **验证要求**:
      {% for vv in planning.vv %}
      - {{ vv.vv_id }}: {{ vv.procedure }}
      {% endfor %}
    required: true

  - feishu_field: "评审"
    spec_path: null
    transform: "fixed"
    fixed_value: "审阅"
    required: true

  - feishu_field: "排期"
    spec_path: null
    transform: "fixed"
    fixed_value: "排期"
    required: true

  - feishu_field: "需求状态"
    spec_path: null
    transform: "fixed"
    fixed_value: "待排期"
    required: true

  - feishu_field: "需求负责人"
    spec_path: "project_context_ref.mentor_user_id"
    transform: "direct"
    required: false
    default: []

  - feishu_field: "执行成员"
    spec_path: "project_context_ref.intern_user_id"
    transform: "direct"
    required: false
    default: []

  - feishu_field: "优先级"
    spec_path: null
    transform: "fixed"
    fixed_value: "中"
    required: true

  - feishu_field: "需求类型"
    spec_path: null
    transform: "fixed"
    fixed_value: "新功能"
    required: true

  - feishu_field: "所属项目"
    spec_path: "project_context_ref.project_record_id"
    transform: "direct"
    required: true
```

### 映射配置字段表

| 字段路径 | 必填 | 用途 | 校验规则 |
|---------|------|------|----------|
| `mapping_version` | ✅ | 配置版本 | 格式：`"1.0"`（语义化版本） |
| `target.system` | ✅ | 目标系统 | 枚举值：`"feishu"` |
| `target.base_token` | ✅ | Feishu App Token | 字符串 |
| `target.table_id` | ✅ | 表格 ID | 字符串 |
| `target.project_record_id` | ✅ | 项目记录 ID | 字符串 |
| `field_mappings[].feishu_field` | ✅ | Feishu 字段名 | 必须存在于表结构中 |
| `field_mappings[].spec_path` | ⚠️ | Spec 路径 | 可为 null（fixed 类型） |
| `field_mappings[].transform` | ✅ | 转换类型 | 枚举值：`direct|template|concat|fixed` |
| `field_mappings[].required` | ✅ | 是否必填 | 布尔值 |

### 映射配置版本化要求

1. **版本标识**：`mapping_version` 必须语义化版本（`MAJOR.MINOR`）
2. **可回滚**：系统必须支持加载历史版本的映射配置
3. **可测试**：映射配置必须支持单元测试（给定 Spec，验证输出字段）

## 幂等性保证（Publish Ledger）

### Ledger 结构

```json
{
  "ledger_id": "L-20260113-0001",
  "feature_id": "F-2026-001",
  "target": "feishu",
  "spec_version": "S-20260113-0003",
  "external_id": "recv83AoVSDMQP",
  "operation": "created",
  "published_at": "2026-01-13T10:20:00Z",
  "status": "active|superseded|rolled_back",
  "field_map_snapshot": { ... },
  "mapping_version": "1.0"
}
```

### 幂等键

**唯一键**：`feature_id + target + spec_version`

**幂等语义**：
- **相同 spec_version 重复发布**：查询 Ledger，如果已存在且 `status = active`，返回 `operation = noop`，不调用 Feishu API
- **新 spec_version 发布**：创建新 Ledger 记录，调用 Feishu API，记录 `external_id`。由于 `spec_version` 不可变，每次 Spec 内容变更都会产生新版本，因此新版本发布总是创建新 Ledger 记录
- **更新场景**：如果同一 `feature_id` 的 `external_id` 已存在（通过 frontmatter 追溯），且新 `spec_version` 发布，则调用 Feishu 更新 API（更新同一记录，但 Ledger 中记录为新版本）

### 幂等实现逻辑

```python
def upsert_feature(spec, target_config, mapping_config):
    # 1. 查询 Ledger
    existing = ledger.get(feature_id=spec.feature.feature_id, target="feishu", spec_version=spec.meta.spec_version)
    
    if existing and existing.status == "active":
        return {"operation": "noop", "external_id": existing.external_id}
    
    # 2. 映射字段
    feishu_fields = map_spec_to_feishu(spec, mapping_config)
    
    # 3. 查询 Feishu 是否存在（通过 external_id 或 feature_id 匹配）
    external_id = find_existing_feishu_record(spec.feature.feature_id)
    
    if external_id:
        # 更新
        result = feishu_client.update_record(external_id, feishu_fields)
        operation = "updated"
    else:
        # 创建
        result = feishu_client.create_record(feishu_fields)
        external_id = result["record_id"]
        operation = "created"
    
    # 4. 写入 Ledger
    ledger.create({
        "feature_id": spec.feature.feature_id,
        "target": "feishu",
        "spec_version": spec.meta.spec_version,
        "external_id": external_id,
        "operation": operation,
        "status": "active"
    })
    
    return {"operation": operation, "external_id": external_id}
```

## Spec Version / Feature ID 追溯策略

**问题**：Feishu 表结构不新增字段，如何追溯 `spec_version` 和 `feature_id`？

### 方案 A：写入描述字段的 frontmatter（推荐）

在 `用户故事` 字段的开头添加 frontmatter：

```markdown
---
feature_id: F-2026-001
spec_version: S-20260113-0003
canonical_ref: https://canonical.example.com/specs/F-2026-001/S-20260113-0003
---

**目标**:
...
```

**优点**：可追溯，不破坏现有字段  
**缺点**：需要解析 frontmatter（但实现简单）

### 方案 B：仅依赖 Ledger（不推荐）

不在 Feishu 字段中写入追溯信息，完全依赖内部 Ledger。

**优点**：不污染 Feishu 数据  
**缺点**：Feishu 记录无法独立追溯（必须查询 Ledger）

### MVP 选择

**采用方案 A**：在 `用户故事` 字段开头添加 frontmatter，包含 `feature_id` + `spec_version` + `canonical_ref`（可选）。

## 检验标准

### 幂等性验证
- **重复发布同一 spec_version**：必须返回 `operation = noop`，不产生重复记录
- **新 spec_version 发布**：必须创建新 Ledger 记录，记录 `external_id`

### 映射正确性验证
- **字段映射测试**：给定 Canonical Spec + Mapping Config，验证输出的 Feishu 字段值正确
- **必填字段检查**：`required: true` 的字段必须映射成功，否则拒绝发布

### 错误处理策略
- **Feishu API 调用失败**（网络超时、限流、服务不可用）
  - **策略**：自动重试（最多 3 次，指数退避）
  - **记录**：记录到 Ledger（`status = failed`），包含错误码和重试记录
  - **降级**：重试失败后，返回错误，不更新 Ledger 状态为 `active`
- **字段映射失败**（必填字段缺失、类型不匹配）
  - **策略**：立即拒绝发布，不调用 Feishu API
  - **记录**：返回错误，列出缺失字段
- **映射配置版本不存在**
  - **策略**：立即返回错误，不执行发布
  - **记录**：返回错误，包含可用版本列表

### 失败姿势

| 失败场景 | 处理方式 | 输出 |
|---------|---------|------|
| Feishu API 调用失败（可重试） | 自动重试 3 次，失败后记录到 Ledger（`status = failed`），返回错误 | 错误信息 + Ledger 记录 + 重试记录 |
| Feishu API 调用失败（不可重试） | 立即记录到 Ledger（`status = failed`），返回错误 | 错误信息 + Ledger 记录 |
| 字段映射失败（必填字段缺失） | 拒绝发布，返回错误 | 错误信息（列出缺失字段） |
| 映射配置版本不存在 | 返回错误，不执行发布 | 错误信息 + 可用版本列表 |
