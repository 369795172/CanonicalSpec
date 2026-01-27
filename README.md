# Canonical Spec - 统一需求编译与执行入口系统

## 项目概述

Canonical 是一个**统一的需求编译与执行入口系统**，目标是将任意质量的需求输入（从一句话到完整文档）编译成可执行的最小任务集，并发布到执行系统（如飞书多维表格）。

## 核心目标

1. 接受任意质量的输入（从一句话到完整任务文档）
2. 自动判断：是否信息充分、是否值得进入执行系统
3. 如果信息不足：主动进入多轮澄清，每轮只聚焦一个需求
4. 最终只在满足条件时：产出**可执行的最小任务集**，并进入团队的执行系统
5. 如果不满足：给出**Hold / Drop 的明确理由**，而不是模糊失败

## 项目结构

```
canonical_spec/
├── docs/                    # 规范文档
│   ├── canonical_spec.md    # 业务基线文档（用户故事级）
│   ├── canoncial_technical_design.md  # 技术架构设计
│   └── mvp_contracts/       # MVP合同文档（6份契约文档）
│       ├── 00_scope_and_terms.md
│       ├── 01_canonical_spec_mvp_schema.md
│       ├── 02_gate_model.md
│       ├── 03_orchestrator_steps_io.md
│       ├── 04_feishu_publish_contract.md
│       ├── 05_review_checklist.md
│       └── 06_mvp_integration_matrix.md
├── src/                     # React 前端代码
│   ├── App.jsx              # 主应用组件
│   ├── main.jsx             # 入口文件
│   └── components/          # UI 组件
├── scripts/                 # 辅助脚本
│   ├── restart_backend.sh   # 重启后端服务
│   ├── restart_frontend.sh  # 重启前端服务
│   └── start_api.sh         # 启动 API 服务
└── canonical/               # Python 实现代码
    ├── cli.py              # CLI 命令入口
    ├── config.py           # 配置管理
    ├── engine/             # 核心引擎
    │   ├── compiler.py     # LLM 编译器
    │   ├── gate.py         # Gate 引擎（确定性判定）
    │   └── orchestrator.py # Pipeline 编排器
    ├── models/             # 数据模型
    │   ├── spec.py         # Canonical Spec 模型
    │   ├── gate.py         # Gate Result 模型
    │   └── snapshot.py     # Step Snapshot 模型
    ├── store/              # 存储层
    │   ├── spec_store.py   # Spec 存储
    │   ├── snapshot_store.py # Snapshot 存储
    │   └── ledger.py       # Publish Ledger
    └── adapters/           # 执行系统适配器
        └── feishu.py       # Feishu 适配器
```

## 文档说明

### 核心规范文档

- **`docs/canonical_spec.md`** - 业务基线文档（用户故事级）
- **`docs/canoncial_technical_design.md`** - 技术架构设计（3个核心协议 + Gate规则）

### MVP合同文档（`docs/mvp_contracts/`）

采用"六要素"契约模式，包含：

1. **`00_scope_and_terms.md`** - MVP范围、术语表、状态机
2. **`01_canonical_spec_mvp_schema.md`** - Canonical Spec MVP Schema（数据结构）
3. **`02_gate_model.md`** - Gate模型（确定性骨架，硬必填+加权评分）
4. **`03_orchestrator_steps_io.md`** - Orchestrator Steps I/O（9步编排流程）
5. **`04_feishu_publish_contract.md`** - Feishu发布契约（字段映射+幂等Ledger）
6. **`05_review_checklist.md`** - 开工前检查清单（定义完整性验证）
7. **`06_mvp_integration_matrix.md`** - MVP集成矩阵（快速参考）

## 代码说明

### 核心模块

- **`canonical/cli.py`** - CLI 命令入口，提供4个核心命令：
  - `canonical run <input>` - 执行完整Pipeline
  - `canonical answer <feature_id> <answers>` - 提交澄清答案
  - `canonical review <feature_id> <decision>` - 人工确认（go/hold/drop）
  - `canonical publish <feature_id>` - 发布到Feishu

- **`canonical/engine/`** - 核心引擎模块：
  - `compiler.py` - LLM编译器（抽取/补全/提问生成）
  - `gate.py` - Gate引擎（确定性判定，硬必填+加权评分）
  - `orchestrator.py` - Pipeline编排器（9步流程）

- **`canonical/models/`** - 数据模型：
  - `spec.py` - Canonical Spec模型（唯一事实源）
  - `gate.py` - Gate Result模型
  - `snapshot.py` - Step Snapshot模型

- **`canonical/store/`** - 存储层：
  - `spec_store.py` - Spec存储（版本化）
  - `snapshot_store.py` - Snapshot存储（证据链）
  - `ledger.py` - Publish Ledger（幂等性保证）

- **`canonical/adapters/`** - 执行系统适配器：
  - `feishu.py` - Feishu适配器（字段映射+发布）

## 核心概念

### Canonical Spec
唯一事实源，系统内部的结构化规格，包含：
- 目标与非目标
- 已知假设
- 风险与不确定性
- 可执行最小任务集（是否存在）
- 决策建议（Go / Hold / Drop）

### Gate S/T/V
确定性判定点：
- **Gate S**：Spec可用（能说清要做什么+怎么验收）
- **Gate T**：可拆出"最小可执行任务集"（B模式核心）
- **Gate V**：可验证闭环（每个任务至少一个验证点）

### Step Pipeline
9步编排流程：
1. `ingest` - 输入解析
2. `compile` - 编译为Canonical Spec
3. `validate_gates` - Gate判定
4. `clarify_questions` - 生成澄清问题
5. `apply_answers` - 应用答案
6. `plan_tasks` - 任务规划
7. `generate_vv` - 生成验证点
8. `manual_review` - 人工确认
9. `publish` - 发布到执行系统

## 状态机

6个状态：`draft` → `clarifying` → `executable_ready` → `published` / `hold` / `drop`

## 快速开始

### 阅读文档

1. **理解业务目标**（5-10分钟）：阅读 `docs/canonical_spec.md`
2. **理解技术架构**（10-15分钟）：阅读 `docs/canoncial_technical_design.md`
3. **理解MVP实现**（15-20分钟）：按顺序阅读 `docs/mvp_contracts/` 目录下的文档
4. **验证定义完整性**（5分钟）：查看 `docs/mvp_contracts/05_review_checklist.md`

### 使用代码

```bash
# 安装依赖（如果有 requirements.txt）
pip install -r requirements.txt

# 运行 CLI
canonical run "添加用户登录功能"
canonical answer F-2026-001 --file answers.json
canonical review F-2026-001
canonical publish F-2026-001
```

## 完成度

**定义完成度**：✅ 100%

- ✅ 所有6份MVP合同文档已完成
- ✅ 每层契约六要素（数据源、输入、输出、约束、检验、失败姿势）已定义
- ✅ 关键定义（Gate硬必填、加权评分、状态机、Feishu映射、幂等性）已明确
- ✅ Python 实现代码已完成

**可开工性**：✅ 是（核心契约已清晰，验证要求已定义，代码实现已完成）

## 实施路径建议

1. **Phase 1**：核心数据结构实现（Canonical Spec Schema）✅ 已完成
2. **Phase 2**：Gate Engine实现（硬必填检查+评分计算）✅ 已完成
3. **Phase 3**：Orchestrator实现（Step Pipeline+Snapshot）✅ 已完成
4. **Phase 4**：Feishu集成（字段映射+幂等Ledger）✅ 已完成
5. **Phase 5**：CLI工具实现（4个核心命令）✅ 已完成

## 验证要求

- **确定性验证**：Gate计算确定性、spec_version单调性、发布幂等性
- **功能验证**：完整Pipeline流程、澄清循环
- **集成验证**：Feishu字段映射正确性

## License

待定
