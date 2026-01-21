# MVP 集成矩阵

本文档提供 MVP 实现的快速参考矩阵，展示从入口命令到最终发布的完整流程。

## 命令 → 步骤 → 产物 → 决策点 → 发布结果

| 入口命令 | 执行的 Steps | 产出的 Artifacts | 决策点 | 发布结果 |
|---------|------------|----------------|--------|---------|
| `canonical run <input>` | `ingest` → `compile` → `validate_gates` | `spec_version: S-001`<br/>`gate_result`<br/>`missing_fields[]` | Gate Pass? | 如 Fail → 进入澄清<br/>如 Pass → 进入 `plan_tasks` |
| `canonical run <input>`<br/>（Gate Pass 后） | `plan_tasks` → `generate_vv` → `validate_gates` | `spec_version: S-002`<br/>`tasks[]`<br/>`vv[]`<br/>`gate_result` | Gate T/V Pass? | 如 Fail → 继续澄清<br/>如 Pass → `executable_ready` |
| `canonical answer <feature_id> <answers>` | `apply_answers` → `compile` → `validate_gates` | `spec_version: S-003`<br/>更新后的 Spec<br/>`gate_result` | Gate Pass? | 如 Fail → 继续澄清<br/>如 Pass → 进入下一步 |
| `canonical review <feature_id>` | `manual_review` | `review_decision`<br/>（go/hold/drop） | 人工决策 | go → 可发布<br/>hold/drop → 不发布 |
| `canonical publish <feature_id>` | `publish` | `external_id`<br/>`publish_record`<br/>Ledger 记录 | 幂等检查 | 成功 → `published`<br/>失败 → 错误信息 |

## 状态流转矩阵

| 当前状态 | 允许的命令 | 下一步状态 | 条件 |
|---------|----------|----------|------|
| `draft` | `canonical run`<br/>`canonical answer` | `clarifying`<br/>`executable_ready` | Gate Fail → clarifying<br/>Gate Pass → executable_ready |
| `clarifying` | `canonical answer` | `draft`<br/>`executable_ready` | 答案应用后重新编译<br/>Gate Pass → executable_ready |
| `executable_ready` | `canonical review` | `published`<br/>`hold`<br/>`drop` | review_decision=go → published<br/>review_decision=hold → hold<br/>review_decision=drop → drop |
| `published` | `canonical run`（新版本） | `draft`（新 feature_id） | 新版本必须使用新 spec_version |
| `hold` | `canonical answer`<br/>`canonical review` | `clarifying`<br/>`drop` | 条件满足 → 继续澄清<br/>明确放弃 → drop |
| `drop` | 无 | - | 归档状态，不可操作 |

## spec_version 演进矩阵

| Step | 输入 spec_version | 输出 spec_version | 是否生成新版本 | 说明 |
|------|-----------------|-----------------|--------------|------|
| `ingest` | - | - | ❌ | 不涉及 Spec |
| `compile` | - | `S-001` | ✅ | 首次生成 |
| `validate_gates` | `S-001` | `S-001` | ❌ | 只读操作 |
| `clarify_questions` | `S-001` | `S-001` | ❌ | 只读操作 |
| `apply_answers` | `S-001` | `S-002` | ✅ | 应用答案后生成新版本 |
| `plan_tasks` | `S-002` | `S-003` | ✅ | 生成任务后生成新版本 |
| `generate_vv` | `S-003` | `S-004` | ✅ | 生成 VV 后生成新版本 |
| `manual_review` | `S-004` | `S-004` | ❌ | 只读操作 |
| `publish` | `S-004` | `S-004` | ❌ | 只读操作，记录到 Ledger |

## Gate 判定矩阵

| Gate | 必填字段 | Pass 条件 | Fail 后动作 |
|------|---------|----------|------------|
| Gate S | `spec.goal`<br/>`spec.non_goals`<br/>`spec.acceptance_criteria` | 所有字段存在且非空 | 进入 `clarify_questions` |
| Gate T | `planning.tasks`（≥1）<br/>每个 task: `task_id`、`title`、`scope`、`deliverables` | 所有字段满足 | 进入 `clarify_questions` 或 `plan_tasks` |
| Gate V | `planning.vv`（≥tasks数量）<br/>每个 vv: `vv_id`、`task_id`、`procedure`、`expected_result` | 所有字段满足 + 每个 task 至少 1 个 vv | 进入 `clarify_questions` 或 `generate_vv` |

## 幂等性矩阵

| 操作 | 幂等键 | 第 1 次调用 | 第 N 次调用（N>1） |
|------|--------|------------|------------------|
| `canonical run` | `input + project_context_ref` | 生成新 `feature_id` + `spec_version` | 生成新 `feature_id` + `spec_version`（不同输入） |
| `canonical answer` | `feature_id + answers` | 生成新 `spec_version` | 生成新 `spec_version`（每次答案应用都生成新版本） |
| `canonical publish` | `feature_id + target + spec_version` | `operation = created`<br/>创建 Ledger 记录 | `operation = noop`<br/>不创建 Ledger 记录 |

## 错误处理矩阵

| 错误类型 | 发生位置 | 处理策略 | 重试次数 | 降级方案 |
|---------|---------|---------|---------|---------|
| LLM 调用失败（网络超时） | `compile`、`apply_answers`、`plan_tasks`、`generate_vv` | 自动重试 | 3 次（指数退避） | 返回错误，不生成新版本 |
| LLM 调用失败（权限不足） | 同上 | 立即返回错误 | 0 次 | 返回错误，提示检查 API Key |
| Gate 计算异常 | `validate_gates` | 返回错误 | 0 次 | Gate Engine 是确定性函数，不应出现异常 |
| Feishu API 调用失败（网络超时） | `publish` | 自动重试 | 3 次（指数退避） | 记录到 Ledger（`status = failed`） |
| Feishu API 调用失败（权限不足） | `publish` | 立即返回错误 | 0 次 | 记录到 Ledger（`status = failed`） |
| 字段映射失败（必填字段缺失） | `publish` | 拒绝发布 | 0 次 | 返回错误，列出缺失字段 |

## 验证检查清单

### 实现前检查
- [ ] 所有 Step 的输入输出结构已定义
- [ ] `spec_version` 生成策略已统一（每次修改生成新版本）
- [ ] Gate 判定规则已实现为确定性函数
- [ ] 错误处理策略已统一（重试/降级/通知）
- [ ] `project_context_ref` 字段已定义并映射到 Feishu

### 实现后验证
- [ ] Gate 计算确定性测试通过（100 次调用结果一致）
- [ ] `spec_version` 单调性测试通过（版本号递增）
- [ ] 发布幂等性测试通过（重复调用返回 noop）
- [ ] 完整 Pipeline 流程测试通过（从输入到发布）
- [ ] Feishu 字段映射测试通过（所有字段正确映射）

## 快速参考

### CLI 命令示例
```bash
# 1. 初始输入
canonical run "添加用户登录功能" \
  --project-record-id recv83AoVSDMQP \
  --mentor-user-id ou_xxx

# 2. 提交澄清答案
canonical answer F-2026-001 --file answers.json

# 3. 人工确认
canonical review F-2026-001
# 交互式提示: [g]o / [h]old / [d]rop

# 4. 发布
canonical publish F-2026-001
```

### 关键路径
1. **成功路径**：`run` → Gate Pass → `plan_tasks` → `generate_vv` → Gate Pass → `review` (go) → `publish`
2. **澄清路径**：`run` → Gate Fail → `clarify_questions` → `answer` → `compile` → Gate Pass → 继续
3. **Hold 路径**：`run` → Gate Pass → `review` (hold) → 等待条件满足 → 继续澄清
