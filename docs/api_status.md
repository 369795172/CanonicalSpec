# API 实现状态跟踪表

本文档跟踪 Canonical Spec 后端 API 的实现状态，帮助前后端开发团队了解当前进度。

## 状态说明

- ✅ **已实现** - API 已实现并通过测试
- 🚧 **开发中** - API 正在开发中
- 📋 **待实现** - API 已规划但尚未开始实现
- ❌ **已废弃** - API 已废弃，不应使用

## 核心功能 API

| 端点 | 方法 | 状态 | 实现说明 | 测试状态 | 备注 |
|-----|-----|------|---------|---------|------|
| `/api/v1/system/health` | GET | ✅ | 健康检查端点 | ✅ | 基础功能 |
| `/api/v1/features` | GET | ✅ | 功能列表查询 | ✅ | 支持状态过滤、分页 |
| `/api/v1/features/{feature_id}` | GET | ✅ | 功能详情查询 | ✅ | 返回完整 Spec 和 Gate 结果 |
| `/api/v1/run` | POST | ✅ | 创建功能 Pipeline | ✅ | ingest → compile → validate_gates |
| `/api/v1/features/{feature_id}/answer` | POST | ✅ | 提交澄清答案 | ✅ | apply_answers → compile → validate_gates |
| `/api/v1/features/{feature_id}/plan` | POST | 📋 | 生成任务计划 | ❌ | orchestrator.plan_tasks() 已实现，但未暴露为 API |
| `/api/v1/features/{feature_id}/vv` | POST | 📋 | 生成验证项 | ❌ | orchestrator.generate_vv() 已实现，但未暴露为 API |
| `/api/v1/features/{feature_id}/review` | POST | 📋 | 人工确认 | ❌ | orchestrator.review() 已实现，但未暴露为 API |
| `/api/v1/features/{feature_id}/publish` | POST | 📋 | 发布到飞书 | ❌ | CLI publish() 和 FeishuPublisher.publish() 已实现，但未暴露为 API |

## 辅助功能 API

| 端点 | 方法 | 状态 | 实现说明 | 测试状态 | 备注 |
|-----|-----|------|---------|---------|------|
| `/api/v1/refine` | POST | ✅ | 需求精炼分析 | ✅ | 前端已使用 |
| `/api/v1/refine/feedback` | POST | ✅ | 精炼反馈 | ✅ | 前端已使用 |
| `/api/v1/transcribe` | POST | ✅ | 语音转文字 | ✅ | 使用 AI Builder Space API |

## 实现优先级

### P0 - 核心流程（必须实现）

1. ✅ `POST /api/v1/run` - 创建功能
2. ✅ `GET /api/v1/features/{feature_id}` - 获取详情
3. ✅ `POST /api/v1/features/{feature_id}/answer` - 提交答案
4. 📋 `POST /api/v1/features/{feature_id}/plan` - 生成任务
5. 📋 `POST /api/v1/features/{feature_id}/vv` - 生成验证项
6. 📋 `POST /api/v1/features/{feature_id}/review` - 人工确认
7. 📋 `POST /api/v1/features/{feature_id}/publish` - 发布

### P1 - 辅助功能（重要）

1. ✅ `GET /api/v1/features` - 列表查询
2. ✅ `POST /api/v1/refine` - 需求精炼
3. ✅ `POST /api/v1/transcribe` - 语音转文字

### P2 - 增强功能（可选）

1. `GET /api/v1/features/{feature_id}/history` - 版本历史
2. `GET /api/v1/features/{feature_id}/snapshots` - 步骤快照查询
3. `POST /api/v1/features/{feature_id}/rollback` - 回滚到指定版本

## 前端调用情况

根据 `src/App.jsx` 分析，前端当前调用的 API：

### 已调用的 API ✅

- `GET /api/v1/features` - 功能列表（第 227 行）
- `GET /api/v1/features/{feature_id}` - 功能详情（第 756 行）
- `POST /api/v1/run` - 创建功能（第 376 行、第 1065 行）
- `POST /api/v1/features/{feature_id}/answer` - 提交答案（第 776 行）
- `POST /api/v1/refine` - 需求精炼（第 993 行）
- `POST /api/v1/refine/feedback` - 精炼反馈（第 1029 行）
- `POST /api/v1/transcribe` - 语音转文字（第 153 行、第 351 行）

### 未调用的 API 📋

- `POST /api/v1/features/{feature_id}/plan` - 生成任务计划
- `POST /api/v1/features/{feature_id}/vv` - 生成验证项
- `POST /api/v1/features/{feature_id}/review` - 人工确认
- `POST /api/v1/features/{feature_id}/publish` - 发布到飞书

**说明**: 这些 API 可能通过 CLI 工具调用，或前端尚未实现对应功能。

## 数据库表实现状态

| 表名 | 状态 | 说明 |
|------|------|------|
| `features` | ✅ | 功能主表 |
| `canonical_specs` | ✅ | Spec 版本存储 |
| `step_snapshots` | 📋 | 步骤快照（审计） |
| `evidences` | 📋 | 证据存储 |
| `publish_ledger` | 📋 | 发布记录（幂等保证） |

## 已知问题

### 前端调用但后端未实现的 API

无（所有前端调用的 API 都已实现）

### 后端方法已实现但未暴露为 API 的端点

以下 4 个 API 的底层方法已实现，但未在 `canonical/api.py` 中暴露为 HTTP 端点：

1. **`POST /api/v1/features/{feature_id}/plan`**
   - 底层方法: `orchestrator.plan_tasks(feature_id)` ✅ 已实现
   - CLI 命令: `canonical plan <feature_id>` ✅ 已实现
   - API 端点: ❌ 未实现

2. **`POST /api/v1/features/{feature_id}/vv`**
   - 底层方法: `orchestrator.generate_vv(feature_id)` ✅ 已实现
   - CLI 命令: `canonical vv <feature_id>` ✅ 已实现
   - API 端点: ❌ 未实现

3. **`POST /api/v1/features/{feature_id}/review`**
   - 底层方法: `orchestrator.review(feature_id, decision, rationale)` ✅ 已实现
   - CLI 命令: `canonical review <feature_id> --decision <go/hold/drop>` ✅ 已实现
   - API 端点: ❌ 未实现

4. **`POST /api/v1/features/{feature_id}/publish`**
   - 底层方法: `FeishuPublisher.publish(spec)` ✅ 已实现
   - CLI 命令: `canonical publish <feature_id>` ✅ 已实现
   - API 端点: ❌ 未实现

**建议**: 在 `canonical/api.py` 中添加这 4 个 API 端点，调用对应的 orchestrator/CLI 方法。

### 后端实现但前端未使用的 API

- `POST /api/v1/features/{feature_id}/plan` - 前端可能通过其他方式触发
- `POST /api/v1/features/{feature_id}/vv` - 前端可能通过其他方式触发
- `POST /api/v1/features/{feature_id}/review` - 前端可能通过其他方式触发
- `POST /api/v1/features/{feature_id}/publish` - 前端可能通过其他方式触发

### 数据不一致问题

1. **Spec 版本管理**: 需要确保每次修改都生成新版本
2. **Gate 结果缓存**: 需要确保 Gate 结果与最新 Spec 版本一致
3. **状态流转**: 需要确保状态流转符合状态机定义

## 测试覆盖情况

| API 端点 | 单元测试 | 集成测试 | E2E 测试 |
|---------|---------|---------|---------|
| `GET /api/v1/system/health` | ✅ | ✅ | ✅ |
| `GET /api/v1/features` | ✅ | ✅ | ✅ |
| `GET /api/v1/features/{feature_id}` | ✅ | ✅ | ✅ |
| `POST /api/v1/run` | ✅ | ✅ | ✅ |
| `POST /api/v1/features/{feature_id}/answer` | ✅ | ✅ | ✅ |
| `POST /api/v1/features/{feature_id}/plan` | ❌ | ❌ | ❌ |
| `POST /api/v1/features/{feature_id}/vv` | ❌ | ❌ | ❌ |
| `POST /api/v1/features/{feature_id}/review` | ❌ | ❌ | ❌ |
| `POST /api/v1/features/{feature_id}/publish` | ❌ | ❌ | ❌ |
| `POST /api/v1/refine` | ✅ | ✅ | ✅ |
| `POST /api/v1/refine/feedback` | ✅ | ✅ | ✅ |
| `POST /api/v1/transcribe` | ✅ | ✅ | ✅ |

## 下一步计划

### 短期目标（1-2 周）

1. 实现 `POST /api/v1/features/{feature_id}/plan` API
2. 实现 `POST /api/v1/features/{feature_id}/vv` API
3. 实现 `POST /api/v1/features/{feature_id}/review` API
4. 实现 `POST /api/v1/features/{feature_id}/publish` API（包括 Feishu 集成）

### 中期目标（1 个月）

1. 实现 `step_snapshots` 表和相关功能
2. 实现 `evidences` 表和相关功能
3. 实现 `publish_ledger` 表和相关功能
4. 完善测试覆盖（单元测试、集成测试、E2E 测试）

### 长期目标（3 个月）

1. 实现版本历史查询 API
2. 实现步骤快照查询 API
3. 实现回滚功能
4. 性能优化和监控

## 更新日志

- **2026-01-24**: 创建初始状态跟踪表
  - 标记已实现的 API（健康检查、列表、详情、创建、答案、精炼、转文字）
  - 标记待实现的 API（计划、验证、确认、发布）
  - 分析前端调用情况

## 参考文档

- [后端 API 规范文档](./backend_api_contract.md)
- [数据库结构文档](./backend_database_schema.md)
- [MVP 集成矩阵](./mvp_contracts/06_mvp_integration_matrix.md)
