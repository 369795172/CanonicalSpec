# Plan to Feishu Script

将计划文档转换为飞书需求条目的辅助脚本。

## 功能

- 解析计划文档，自动识别阶段（Phase 1/2/3）
- 为每个阶段生成格式化的输入文本
- 调用 `canonical run` 执行完整的 Orchestrator Pipeline
- 自动生成任务和验证项
- 支持自动确认和发布到飞书

## 使用方法

### 基本用法

```bash
cd /Users/marvi/AndroidStudioProjects/canonical_frontend

python scripts/plan_to_feishu.py \
  --plan-file ../.cursor/plans/class_sync_fix_plan_d7ce09cf.plan.md \
  --project-record-id "recv83AoVSDMQP"
```

### 参数说明

- `--plan-file`: 计划文档路径（必填）
- `--project-record-id`: 飞书项目记录ID（可选，但发布时必填）
- `--dry-run`: 仅显示将要执行的操作，不实际发布
- `--auto-review`: 自动确认并发布（跳过人工确认）

### 执行流程

1. **解析计划文档**：识别三个阶段
   - Phase 1: Sync Logic Enhancement
   - Phase 2: Data Repair Script
   - Phase 3: Validate and Test

2. **生成输入文本**：为每个阶段生成包含目标、任务、验收标准的格式化文本

3. **调用 Orchestrator Pipeline**：
   - `canonical run` - 编译为 Canonical Spec
   - `canonical plan` - 生成任务规划
   - `canonical vv` - 生成验证项

4. **Gate 验证**：自动验证 Gate S/T/V

5. **发布到飞书**：
   - 如果使用 `--auto-review`，自动确认并发布
   - 否则提示用户手动确认

## 环境要求

- Python 3.8+
- canonical CLI 已安装并配置
- 环境变量已设置：
  - `CANONICAL_LLM_API_KEY` - LLM API 密钥
  - `CANONICAL_FEISHU_APP_ID` - 飞书应用ID
  - `CANONICAL_FEISHU_APP_SECRET` - 飞书应用密钥
  - `CANONICAL_FEISHU_BASE_TOKEN` - 飞书多维表格 App Token
  - `CANONICAL_FEISHU_TABLE_ID` - 飞书表格ID

## 示例输出

```
正在解析计划文档: ../.cursor/plans/class_sync_fix_plan_d7ce09cf.plan.md
✓ 识别到 3 个阶段

=== 处理 Phase 1: Sync Logic Enhancement ===
Feature ID: F-2026-001
输入文本预览:
Phase 1: Sync Logic Enhancement

目标：修复同步逻辑，使其能够识别没有 course_unit_id 的历史课程，避免创建重复课程。
...

正在调用 canonical run...
✓ Phase 1 Gate 通过

正在生成任务规划...
✓ 已生成 2 个任务

正在生成验证项...
✓ 已生成 2 个验证项

提示: 使用以下命令确认并发布:
  canonical review F-2026-001
  canonical publish F-2026-001
```

## 注意事项

1. **project_record_id**：发布到飞书时必须提供，可以通过参数或环境变量设置
2. **Gate 验证**：如果 Gate 未通过，需要使用 `canonical answer` 提供缺失信息
3. **幂等性**：重复运行脚本不会创建重复的需求条目（基于 feature_id + spec_version）

## 故障排除

### 找不到 canonical 命令

确保已安装 canonical CLI：
```bash
pip install -e /Users/marvi/AndroidStudioProjects/canonical_frontend
```

### Gate 验证失败

使用 `canonical answer` 命令提供缺失信息：
```bash
canonical answer F-2026-001 --answer "spec.goal=修复同步逻辑问题"
```

### 发布失败：缺少 project_record_id

设置环境变量或通过参数提供：
```bash
export CANONICAL_PROJECT_RECORD_ID="recv83AoVSDMQP"
python scripts/plan_to_feishu.py --plan-file ...
```
