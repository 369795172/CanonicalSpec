# Requirement Genome Contract（需求演进契约）

## 层级定义
**层级名称**：Requirement Genome（需求演进/细化阶段）  
**数据源（SoT）**：Genome Store（可为内存/本地存储/后端持久化）  
**核心程序**：Requirement Refiner（LLM + 规则合并）

## 输入
- **用户输入**：本轮回答/补充信息
- **Refine Context**：历史对话/已有 Genome（可选）
- **Round**：当前轮次（用户视角）

## 输出结构

### RefineResult（扩展）
```json
{
  "round": 2,
  "understanding_summary": "累积式理解摘要",
  "inferred_assumptions": ["字符串列表（兼容旧字段）"],
  "questions": [],
  "ready_to_compile": false,
  "draft_spec": null,
  "genome": { "...": "RequirementGenome" },
  "changes": { "...": "GenomeChanges" }
}
```

### RequirementGenome
```json
{
  "genome_version": "G-20260126-0002",
  "round": 2,
  "summary": "累积式摘要",
  "goals": ["目标列表"],
  "non_goals": ["非目标列表"],
  "assumptions": [
    { "id": "A-1", "content": "...", "source_round": 1, "confirmed": true }
  ],
  "constraints": [
    { "id": "C-1", "content": "...", "source_round": 2, "type": "time" }
  ],
  "user_stories": [
    { "id": "US-1", "as_a": "...", "i_want": "...", "so_that": "...", "source_round": 2, "priority": "medium" }
  ],
  "decisions": [
    { "id": "D-1", "question": "...", "answer": "...", "round": 1, "impact": "..." }
  ],
  "open_questions": [],
  "ready_to_compile": false,
  "created_at": "2026-01-26T10:00:00Z",
  "updated_at": "2026-01-26T10:05:00Z",
  "history": [
    {
      "round": 1,
      "genome_version": "G-20260126-0001",
      "summary": "...",
      "assumptions_count": 1,
      "constraints_count": 0,
      "user_stories_count": 0,
      "questions_asked": ["..."],
      "user_answers": ["..."],
      "timestamp": "2026-01-26T10:02:00Z"
    }
  ]
}
```

### GenomeChanges
```json
{
  "new_assumptions": ["新增假设列表"],
  "new_constraints": ["新增约束列表"],
  "new_user_stories": ["新增用户故事列表"],
  "updated_fields": ["constraints", "goals"],
  "decisions_made": ["本轮决策列表"]
}
```

## 字段映射（兼容性）
| 现有字段 | Genome 字段 | 说明 |
|---------|------------|------|
| `RefineResult.round` | `RequirementGenome.round` | 保持一致 |
| `RefineResult.understanding_summary` | `RequirementGenome.summary` | 累积式更新 |
| `RefineResult.inferred_assumptions` | `RequirementGenome.assumptions[].content` | 兼容旧字段 |
| `RefineResult.questions` | `RequirementGenome.open_questions` | 保持一致 |
| `RefineResult.ready_to_compile` | `RequirementGenome.ready_to_compile` | 保持一致 |
| `RefineResult.draft_spec` | Canonical Spec 输入 | `ready_to_compile = true` 时才生成 |

## 约束规则
### 硬约束
1. **版本不可变**：`genome_version` 只读；每轮必须生成新版本
2. **累积更新**：新增信息合并到现有 Genome，不允许整体替换
3. **轮次一致性**：`round` 必须单调递增，与历史快照一致
4. **来源标注**：新增 `assumptions/constraints/user_stories/decisions` 必须标注 `source_round`

### 软约束
- `summary` 使用 2-3 句累积式摘要
- `history` 中每轮必须有 `questions_asked` 与 `user_answers`（可为空数组）

## 检验标准
1. **版本递增**：多轮 refine 后 `genome_version` 单调递增
2. **信息累积**：上一轮字段在下一轮仍可追溯
3. **变更可见**：`changes` 能准确反映本轮新增/修改项
4. **编译前置条件**：仅当 `ready_to_compile = true` 才允许进入 Canonical Spec 编译

## 失败姿势
| 失败场景 | 处理方式 | 输出 |
|---------|---------|------|
| LLM 输出不完整 | 记录缺失字段，生成 `ready_to_compile = false` | RefineResult（含问题列表） |
| 版本冲突 | 返回冲突错误，要求重新加载最新 Genome | 错误信息 |
| JSON 解析失败 | 返回错误，不更新 Genome | 错误信息 |
