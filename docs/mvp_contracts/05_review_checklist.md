# 开工前定义完成 Checklist

本文档用于快速 review/批准 MVP 契约包，确保所有关键定义已完成。

## 文档完整性检查

- [x] `00_scope_and_terms.md` - MVP 范围、术语表、状态机
- [x] `01_canonical_spec_mvp_schema.md` - Canonical Spec 最小字段集
- [x] `02_gate_model.md` - Gate 硬必填清单 + 加权评分模型
- [x] `03_orchestrator_steps_io.md` - Step Pipeline I/O + Snapshot 结构
- [x] `04_feishu_publish_contract.md` - Feishu 映射配置 + 幂等 Ledger

## 每层契约六要素检查

### Canonical Spec（01）
- [x] **数据源（SoT）**：`CanonicalSpecStore`（内部存储，版本化）
- [x] **输入**：任意用户输入 + 可选 project context ref
- [x] **输出结构**：最小字段集 JSON Schema + 字段表
- [x] **约束规则**：硬约束（不允许混入执行系统字段、版本不可变）+ 软约束（字段质量）
- [x] **检验标准**：输入→输出验证、可重放性
- [x] **失败姿势**：输入无法解析、LLM 失败、版本冲突

### Gate Model（02）
- [x] **数据源（SoT）**：Canonical Spec（输入）
- [x] **输入**：完整的 Canonical Spec + 可选 Gate Context
- [x] **输出结构**：Gate Result JSON（gate_s/t/v + completeness_score + missing_fields）
- [x] **约束规则**：硬必填清单（Gate S/T/V）+ 加权评分模型（确定性计算）
- [x] **检验标准**：可重放性（同一 Spec 多次计算结果一致）
- [x] **失败姿势**：Spec 格式错误、必填字段缺失、计算异常

### Orchestrator Steps（03）
- [x] **数据源（SoT）**：Step Snapshot Store + Evidence Store
- [x] **输入**：用户输入 + project context ref + run_id
- [x] **输出结构**：Canonical Spec + Gate Result + Publish Request
- [x] **约束规则**：硬约束（每个 Step 必须产出 Snapshot、关键决策可解释）
- [x] **检验标准**：可重放性（给定 inputs 可重跑 step）
- [x] **失败姿势**：Step 执行异常、LLM 调用失败、状态机流转错误

### Feishu Publish（04）
- [x] **数据源（SoT）**：Publish Ledger（内部事实源）
- [x] **输入**：Canonical Spec（executable_ready）+ Review Decision（go）+ Mapping Config
- [x] **输出结构**：Publish Result JSON（operation + external_id + field_map_snapshot）
- [x] **约束规则**：严格复用 Feishu 表结构（不新增字段）、幂等键（feature_id + target + spec_version）
- [x] **检验标准**：幂等性验证、映射正确性验证
- [x] **失败姿势**：Feishu API 失败、字段映射失败、映射配置版本不存在

## 关键定义验证

### Gate 硬必填清单
- [x] **Gate S**：`spec.goal`、`spec.non_goals`、`spec.acceptance_criteria`（≥1 条）
- [x] **Gate T**：`planning.tasks`（publish 前 ≥1 个）
- [x] **Gate V**：`planning.vv`（publish 前每个 task 至少 1 个 vv）
- [x] **判定规则**：硬必填通过 ≠ 自动 publish，必须人工确认

### 加权评分模型
- [x] **评分维度**：goal_quality（0.3）、acceptance_criteria_quality（0.25）、tasks_quality（0.25）、vv_quality（0.2）
- [x] **计算公式**：确定性函数（不依赖 LLM/随机性）
- [x] **用途**：仅用于辅助决策（排序/提示），不用于自动放行

### 状态机与流转
- [x] **6 个状态**：draft、clarifying、executable_ready、published、hold、drop
- [x] **合法流转**：已定义状态流转图
- [x] **约束规则**：published 不可回退、版本不可变、并发控制

### Feishu 映射配置
- [x] **字段清单**：10 个现有字段（反馈问题、用户故事、评审、排期、需求状态、需求负责人、执行成员、优先级、需求类型、所属项目）
- [x] **映射配置结构**：YAML 格式，包含 mapping_version、target、field_mappings
- [x] **版本化要求**：支持版本化、可回滚、可测试
- [x] **追溯策略**：采用方案 A（frontmatter 写入 `用户故事` 字段）

### 幂等性保证
- [x] **幂等键**：`feature_id + target + spec_version`
- [x] **幂等语义**：相同 spec_version 重复发布返回 noop，新 spec_version 创建新记录
- [x] **Ledger 结构**：包含所有必要字段（feature_id、target、spec_version、external_id、operation、status）

## 可执行性验证

### 实现边界清晰
- [x] **Canonical Spec**：不包含 Feishu 字段，纯内部结构
- [x] **Gate Engine**：确定性计算，不依赖 LLM 主观判断
- [x] **Orchestrator**：Step 输入输出 JSON，可配置化
- [x] **Feishu Adapter**：映射配置驱动，不硬编码字段

### 扩展性保证
- [x] **未来接 Jira/GitHub**：只需新增 Adapter + Mapping Config，不改 Core 语义
- [x] **未来平台化**：Step Pipeline 可配置化/可视化编排（方案4）

## 文档质量检查

- [x] **每份文档 < 200 行**：所有文档均满足
- [x] **结构清晰**：每份文档包含数据源、输入、输出、约束、检验、失败姿势
- [x] **可引用**：统一引用基线文档（canonical_spec.md、canonical_technical_design.md）

## 待确认事项（已完成补充）

- [x] **Project Context Ref 结构**：`project_context_ref` 的具体字段定义（mentor_user_id、intern_user_id、project_record_id 等）✅ 已定义在 `01_canonical_spec_mvp_schema.md`
- [x] **人工确认流程**：CLI 工具中人工确认的具体交互流程（命令、确认项、Hold/Drop 理由输入）✅ 已定义在 `canoncial_technical_design.md`
- [x] **错误处理策略**：各层错误处理的统一策略（重试、降级、通知）✅ 已定义在 `03_orchestrator_steps_io.md`、`02_gate_model.md`、`04_feishu_publish_contract.md`

## MVP 验证要求

### 确定性验证（必须通过）
1. **Gate 计算确定性**
   - **测试**：给定相同的 Canonical Spec，调用 Gate Engine 100 次
   - **预期**：所有 `gate_result`（包括 `completeness_score`）完全一致
   - **验证点**：`gate_s.pass`、`gate_t.pass`、`gate_v.pass`、`completeness_score`、`missing_fields` 路径

2. **spec_version 单调性**
   - **测试**：对同一 `feature_id` 执行多次修改步骤（`compile`、`apply_answers`、`plan_tasks`、`generate_vv`）
   - **预期**：每次成功步骤都生成新的 `spec_version`，且版本号单调递增
   - **验证点**：`spec_version` 格式正确、不可修改、单调递增

3. **发布幂等性**
   - **测试**：使用相同的 `feature_id + target + spec_version` 调用 `publish` 10 次
   - **预期**：第 1 次返回 `operation = created`，后续 9 次返回 `operation = noop`，不产生重复 Ledger 记录
   - **验证点**：Ledger 记录数量、`operation` 字段、Feishu API 调用次数

### 功能验证（必须通过）
4. **完整 Pipeline 流程**
   - **测试**：从"一句话输入"到"发布到 Feishu"的完整流程
   - **预期**：所有步骤按顺序执行，每个步骤产出正确的 Snapshot 和 Spec 版本
   - **验证点**：Step Snapshot 完整性、Spec 版本演进、Gate 结果正确性

5. **澄清循环**
   - **测试**：输入不完整需求，触发澄清，提交答案，继续流程
   - **预期**：澄清问题准确对应 `missing_fields`，答案应用后生成新版本，Gate 结果更新
   - **验证点**：澄清问题质量、答案应用正确性、版本演进

### 集成验证（必须通过）
6. **Feishu 字段映射**
   - **测试**：给定完整的 Canonical Spec，验证映射到 Feishu 字段的正确性
   - **预期**：所有必填字段映射成功，frontmatter 包含 `feature_id` 和 `spec_version`
   - **验证点**：字段值正确性、frontmatter 格式、必填字段完整性

## Review 结论

**定义完成度**：✅ 100%（核心定义已完成，所有待确认事项已补充）

**可开工性**：✅ 是（核心契约已清晰，验证要求已定义，可开始实现）

**风险点**：
1. **Feishu 字段映射**：需要实际测试验证映射配置的正确性（已定义验证要求）
2. **Gate 计算确定性**：需要单元测试验证同一输入多次计算结果一致（已定义验证要求）
3. **幂等性实现**：需要集成测试验证重复发布的幂等行为（已定义验证要求）
4. **CLI 交互体验**：需要实际使用验证命令交互流程的可用性
