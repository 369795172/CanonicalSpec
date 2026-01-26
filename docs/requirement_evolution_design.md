# 需求演进设计规范（Requirement Evolution Design）

## 1. 背景与目标

### 1.1 现状问题

当前 `refine` 流程存在以下体验问题：

1. **需求更新不可见**：`understanding_summary` 每轮替换，用户难以感知"需求在变"
2. **背景信息无累积**：用户回答的信息没有结构化累积，无法追溯
3. **轮次不显示**：用户不知道当前是第几轮细化
4. **历史不可查**：无法查看之前的问答记录和需求演进
5. **草稿规范未展示**：`draft_spec` 字段存在但未在 UI 中使用

### 1.2 设计目标

引入 **Requirement Genome（需求基因组）** 概念，实现：

- **可追溯**：每轮细化生成新版本，历史可查
- **可对比**：用户能看到需求如何演进
- **可累积**：背景信息结构化存储，不丢失
- **可感知**：UI 明确展示轮次、状态、变更

### 1.3 与现有系统的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     Canonical Spec 体系                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │ Requirement     │      │ Canonical Spec  │                   │
│  │ Genome          │ ──→  │ (MVP Schema)    │                   │
│  │ (细化阶段)       │      │ (编译阶段)       │                   │
│  └─────────────────┘      └─────────────────┘                   │
│         │                         │                             │
│         │ ready_to_compile        │ executable_ready            │
│         ↓                         ↓                             │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │ 细化 UI         │      │ Feishu 发布     │                   │
│  │ (本文档范围)     │      │ (现有能力)       │                   │
│  └─────────────────┘      └─────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**核心原则**：Requirement Genome 是 Canonical Spec 的**前置阶段**，用于需求澄清；当 `ready_to_compile = true` 时，Genome 转化为 Canonical Spec。

---

## 2. Requirement Genome 数据模型

### 2.1 核心结构

```python
class RequirementGenome(BaseModel):
    """需求基因组 - 累积式需求状态"""
    
    # === 版本信息 ===
    genome_version: str  # 格式：G-YYYYMMDD-NNNN
    round: int  # 当前轮次（用户视角）
    
    # === 累积理解 ===
    summary: str  # AI 累积摘要（Markdown）
    goals: List[str]  # 目标列表
    non_goals: List[str]  # 非目标列表
    
    # === 结构化信息 ===
    assumptions: List[Assumption]  # 假设（含来源轮次）
    constraints: List[Constraint]  # 约束（含来源轮次）
    user_stories: List[UserStory]  # 用户故事（含来源轮次）
    decisions: List[Decision]  # 已决策信息
    
    # === 澄清状态 ===
    open_questions: List[RefineQuestion]  # 待澄清问题
    ready_to_compile: bool  # 是否准备好编译
    
    # === 元信息 ===
    created_at: datetime
    updated_at: datetime
    
    # === 历史快照 ===
    history: List[GenomeSnapshot]  # 每轮的快照


class Assumption(BaseModel):
    """带来源的假设"""
    id: str  # A-1, A-2, ...
    content: str
    source_round: int  # 来源轮次
    confirmed: bool = False  # 是否已确认


class Constraint(BaseModel):
    """带来源的约束"""
    id: str  # C-1, C-2, ...
    content: str
    source_round: int
    type: str  # technical/business/time/resource


class UserStory(BaseModel):
    """用户故事"""
    id: str  # US-1, US-2, ...
    as_a: str  # 作为...
    i_want: str  # 我想要...
    so_that: str  # 以便...
    source_round: int
    priority: str = "medium"  # high/medium/low


class Decision(BaseModel):
    """已决策信息"""
    id: str  # D-1, D-2, ...
    question: str  # 原问题
    answer: str  # 用户回答
    round: int  # 决策轮次
    impact: str  # 对需求的影响


class GenomeSnapshot(BaseModel):
    """轮次快照"""
    round: int
    genome_version: str
    summary: str
    assumptions_count: int
    constraints_count: int
    user_stories_count: int
    questions_asked: List[str]
    user_answers: List[str]
    timestamp: datetime
```

### 2.2 与现有模型的映射

| 现有字段 | Genome 字段 | 说明 |
|---------|------------|------|
| `RefineResult.round` | `Genome.round` | 保持 |
| `RefineResult.understanding_summary` | `Genome.summary` | 累积式更新 |
| `RefineResult.inferred_assumptions` | `Genome.assumptions` | 结构化 + 来源轮次 |
| `RefineResult.questions` | `Genome.open_questions` | 保持 |
| `RefineResult.ready_to_compile` | `Genome.ready_to_compile` | 保持 |
| `RefineResult.draft_spec` | 转化为 Canonical Spec | ready 时转化 |
| `RefineContext.conversation_history` | `Genome.history` + `Genome.decisions` | 结构化存储 |

### 2.3 版本演进规则

1. **每轮生成新版本**：`genome_version` 格式 `G-YYYYMMDD-NNNN`，每轮递增
2. **版本不可变**：历史版本只读，只能创建新版本
3. **快照保存**：每轮结束时保存 `GenomeSnapshot` 到 `history`
4. **累积合并**：新信息合并到现有字段，标记来源轮次

---

## 3. API 契约扩展

### 3.1 RefineResult 扩展

```python
class RefineResult(BaseModel):
    """扩展后的细化结果"""
    
    # === 现有字段（保持兼容） ===
    round: int
    understanding_summary: str
    inferred_assumptions: List[str]
    questions: List[RefineQuestion]
    ready_to_compile: bool
    draft_spec: Optional[Dict[str, Any]]
    
    # === 新增字段 ===
    genome: RequirementGenome  # 完整基因组状态
    changes: GenomeChanges  # 本轮变更摘要


class GenomeChanges(BaseModel):
    """本轮变更摘要"""
    new_assumptions: List[str]  # 新增假设
    new_constraints: List[str]  # 新增约束
    new_user_stories: List[str]  # 新增用户故事
    updated_fields: List[str]  # 更新的字段
    decisions_made: List[str]  # 本轮决策
```

### 3.2 API 响应示例

```json
{
  "round": 2,
  "understanding_summary": "你想做一个健身打卡应用...",
  "inferred_assumptions": ["目标用户是个人健身爱好者"],
  "questions": [...],
  "ready_to_compile": false,
  "genome": {
    "genome_version": "G-20260126-0002",
    "round": 2,
    "summary": "健身打卡应用，支持每日记录和统计...",
    "goals": ["帮助用户养成健身习惯"],
    "non_goals": ["不做社交功能"],
    "assumptions": [
      {"id": "A-1", "content": "目标用户是个人健身爱好者", "source_round": 1, "confirmed": true}
    ],
    "constraints": [
      {"id": "C-1", "content": "需要在 2 周内完成 MVP", "source_round": 2, "type": "time"}
    ],
    "user_stories": [...],
    "decisions": [
      {"id": "D-1", "question": "目标用户是谁？", "answer": "个人健身爱好者", "round": 1}
    ],
    "open_questions": [...],
    "ready_to_compile": false,
    "history": [...]
  },
  "changes": {
    "new_assumptions": [],
    "new_constraints": ["C-1: 需要在 2 周内完成 MVP"],
    "new_user_stories": [],
    "updated_fields": ["constraints"],
    "decisions_made": ["D-2: 时间约束确认"]
  }
}
```

---

## 4. UI 信息架构

### 4.1 整体布局

```
┌─────────────────────────────────────────────────────────────────┐
│                         Create Modal                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────┐  ┌─────────────────────┐  │
│  │                                 │  │                     │  │
│  │      主内容区 (70%)              │  │  侧边栏 (30%)        │  │
│  │                                 │  │                     │  │
│  │  ┌─────────────────────────┐   │  │  ┌───────────────┐  │  │
│  │  │ 轮次标题                 │   │  │  │ 状态摘要       │  │  │
│  │  │ 第 2 轮细化 | v G-..002  │   │  │  │ Goals: 2      │  │  │
│  │  └─────────────────────────┘   │  │  │ Assumptions: 3│  │  │
│  │                                 │  │  │ Constraints: 1│  │  │
│  │  ┌─────────────────────────┐   │  │  │ Stories: 0    │  │  │
│  │  │ AI 需求理解              │   │  │  │ Questions: 2  │  │  │
│  │  │ (understanding_summary)  │   │  │  └───────────────┘  │  │
│  │  └─────────────────────────┘   │  │                     │  │
│  │                                 │  │  ┌───────────────┐  │  │
│  │  ┌─────────────────────────┐   │  │  │ 历史轮次       │  │  │
│  │  │ 本轮变更 (changes)       │   │  │  │ ● 当前 (R2)   │  │  │
│  │  │ + 新增约束: C-1          │   │  │  │ ○ 第 1 轮     │  │  │
│  │  └─────────────────────────┘   │  │  │ ○ 初始输入    │  │  │
│  │                                 │  │  └───────────────┘  │  │
│  │  ┌─────────────────────────┐   │  │                     │  │
│  │  │ 澄清问题                 │   │  │  ┌───────────────┐  │  │
│  │  │ Q1: ...                  │   │  │  │ 快速操作       │  │  │
│  │  │ Q2: ...                  │   │  │  │ [查看详情]    │  │  │
│  │  └─────────────────────────┘   │  │  │ [对比上轮]    │  │  │
│  │                                 │  │  └───────────────┘  │  │
│  │  ┌─────────────────────────┐   │  │                     │  │
│  │  │ 草稿规范 (if ready)      │   │  │                     │  │
│  │  │ [展开查看 draft_spec]    │   │  │                     │  │
│  │  └─────────────────────────┘   │  └─────────────────────┘  │
│  │                                 │                           │
│  └─────────────────────────────────┘                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [取消]  [提交回答并继续细化]  [创建功能]                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 主内容区组件

#### 4.2.1 轮次标题

```jsx
<div className="round-header">
  <span className="round-number">第 {genome.round} 轮细化</span>
  <span className="genome-version">{genome.genome_version}</span>
  {genome.ready_to_compile && <span className="ready-badge">Ready</span>}
</div>
```

#### 4.2.2 本轮变更区（新增）

```jsx
{changes && (changes.new_assumptions.length > 0 || 
             changes.new_constraints.length > 0 || 
             changes.decisions_made.length > 0) && (
  <div className="changes-section">
    <div className="section-title">
      <RefreshCw size={14} /> 本轮更新
    </div>
    {changes.new_assumptions.map(a => <div className="change-item new">+ 假设: {a}</div>)}
    {changes.new_constraints.map(c => <div className="change-item new">+ 约束: {c}</div>)}
    {changes.decisions_made.map(d => <div className="change-item decision">✓ 决策: {d}</div>)}
  </div>
)}
```

#### 4.2.3 草稿规范预览（新增）

```jsx
{genome.ready_to_compile && draft_spec && (
  <details className="draft-spec-section">
    <summary>
      <FileText size={14} /> 草稿规范预览
    </summary>
    <div className="draft-spec-content">
      <div className="spec-field">
        <label>目标</label>
        <p>{draft_spec.spec?.goal}</p>
      </div>
      <div className="spec-field">
        <label>验收标准</label>
        <ul>
          {draft_spec.spec?.acceptance_criteria?.map(ac => (
            <li key={ac.id}>{ac.criteria}</li>
          ))}
        </ul>
      </div>
    </div>
  </details>
)}
```

### 4.3 侧边栏组件

#### 4.3.1 状态摘要

```jsx
<div className="status-summary">
  <div className="status-item">
    <Target size={14} /> 目标: {genome.goals.length}
  </div>
  <div className="status-item">
    <Lightbulb size={14} /> 假设: {genome.assumptions.length}
  </div>
  <div className="status-item">
    <AlertCircle size={14} /> 约束: {genome.constraints.length}
  </div>
  <div className="status-item">
    <Users size={14} /> 用户故事: {genome.user_stories.length}
  </div>
  <div className="status-item highlight">
    <HelpCircle size={14} /> 待澄清: {genome.open_questions.length}
  </div>
</div>
```

#### 4.3.2 历史轮次列表

```jsx
<div className="history-list">
  <div className="section-title">
    <History size={14} /> 演进历史
  </div>
  <div 
    className={`history-item ${currentView === 'current' ? 'active' : ''}`}
    onClick={() => setCurrentView('current')}
  >
    ● 当前 (第 {genome.round} 轮)
  </div>
  {genome.history.slice().reverse().map((snapshot, idx) => (
    <div 
      key={snapshot.round}
      className={`history-item ${currentView === idx ? 'active' : ''}`}
      onClick={() => setCurrentView(idx)}
    >
      ○ 第 {snapshot.round} 轮 
      <span className="snapshot-stats">
        A:{snapshot.assumptions_count} C:{snapshot.constraints_count}
      </span>
    </div>
  ))}
</div>
```

### 4.4 历史对比视图（可选）

```jsx
{showDiff && previousSnapshot && (
  <div className="diff-view">
    <div className="diff-header">
      对比: 第 {previousSnapshot.round} 轮 → 第 {genome.round} 轮
    </div>
    <div className="diff-content">
      <DiffSection 
        title="假设" 
        before={previousSnapshot.assumptions} 
        after={genome.assumptions} 
      />
      <DiffSection 
        title="约束" 
        before={previousSnapshot.constraints} 
        after={genome.constraints} 
      />
    </div>
  </div>
)}
```

### 4.5 历史记录默认折叠（主列表）

**设计目标**：当前需求是主角，历史列表不占据主区域的主要空间。  
**策略**：
- 首页主区域默认显示“欢迎 + 创建入口”，历史列表仅通过“查看历史”按钮展开。
- 展开后允许用户返回折叠状态，避免历史列表长期占据主视图。

---

## 5. 后端实现要点

### 5.1 Refiner 改造

```python
# canonical/engine/refiner.py

class RequirementRefiner:
    
    def refine(self, user_input: str, context: RefineContext) -> RefineResult:
        """细化需求，返回包含 Genome 的结果"""
        
        # 1. 获取或创建 Genome
        genome = context.genome or self._create_initial_genome()
        
        # 2. 构建 LLM prompt（包含 Genome 上下文）
        messages = self._build_messages_with_genome(user_input, genome, context)
        
        # 3. 调用 LLM
        response = self._call_llm(messages)
        
        # 4. 解析响应，更新 Genome
        new_genome, changes = self._update_genome(genome, response)
        
        # 5. 保存快照
        new_genome.history.append(self._create_snapshot(genome))
        
        # 6. 返回结果
        return RefineResult(
            round=new_genome.round,
            understanding_summary=new_genome.summary,
            inferred_assumptions=[a.content for a in new_genome.assumptions],
            questions=new_genome.open_questions,
            ready_to_compile=new_genome.ready_to_compile,
            draft_spec=self._generate_draft_spec(new_genome) if new_genome.ready_to_compile else None,
            genome=new_genome,
            changes=changes,
        )
```

### 5.2 LLM Prompt 调整

```python
REFINE_SYSTEM_PROMPT_V2 = """你是一个需求分析专家。你的任务是帮助用户将模糊的需求想法转化为清晰、可执行的规格。

## 当前需求基因组状态

{genome_json}

## 你的工作方式

1. **理解新输入**：分析用户的新回答
2. **累积更新**：将新信息合并到现有 Genome 中（不是替换）
3. **标记来源**：新增的假设/约束/故事标记为当前轮次
4. **生成变更**：明确指出本轮新增/修改了什么
5. **继续提问**：如果信息不足，生成 1-2 个关键问题

## 输出格式（JSON）

{
  "summary": "更新后的需求理解（累积式，2-3句话）",
  "goals": ["目标列表（累积）"],
  "non_goals": ["非目标列表（累积）"],
  "new_assumptions": [{"content": "...", "confirmed": false}],
  "new_constraints": [{"content": "...", "type": "..."}],
  "new_user_stories": [{"as_a": "...", "i_want": "...", "so_that": "..."}],
  "new_decisions": [{"question": "...", "answer": "...", "impact": "..."}],
  "questions": [...],
  "ready_to_compile": false,
  "draft_spec": null
}
"""
```

---

## 6. 状态持久化

### 6.1 前端 LocalStorage

```javascript
// 保存 Genome 状态
useEffect(() => {
  if (genome) {
    localStorage.setItem(`genome_${featureId}`, JSON.stringify(genome));
  }
}, [genome, featureId]);

// 恢复 Genome 状态
useEffect(() => {
  const saved = localStorage.getItem(`genome_${featureId}`);
  if (saved) {
    setGenome(JSON.parse(saved));
  }
}, [featureId]);
```

### 6.2 后端数据库（可选）

如需持久化到数据库，可扩展 `features` 表：

```sql
ALTER TABLE features ADD COLUMN genome JSONB;
ALTER TABLE features ADD COLUMN genome_version VARCHAR(20);
```

---

## 7. 迁移策略

### 7.1 Phase 1：UI 增强（最小改动）

- 显示轮次信息
- 显示对话历史（折叠）
- 利用现有 `conversation_history`

### 7.2 Phase 2：Genome 数据模型

- 引入 `RequirementGenome` 类
- 后端返回 `genome` 字段
- 前端存储和展示 Genome

### 7.3 Phase 3：完整功能

- 侧边栏状态显示
- 历史对比视图
- 草稿规范预览
- 与 Canonical Spec 完整对接

---

## 8. 检验标准

### 8.1 用户体验验收

- [ ] 用户能看到当前是第几轮细化
- [ ] 用户能看到本轮新增了什么信息
- [ ] 用户能查看历史轮次的需求状态
- [ ] 用户能对比不同轮次的变化
- [ ] 当 ready_to_compile 时，用户能预览草稿规范

### 8.2 技术验收

- [ ] Genome 版本递增，历史不可变
- [ ] 每轮快照正确保存
- [ ] LocalStorage 正确持久化
- [ ] API 响应包含完整 Genome

---

## 附录 A：与 RequirementDocGen 对比

| 功能 | RequirementDocGen | Canonical (目标) |
|------|-------------------|-----------------|
| Genome 概念 | ✅ | ✅ (新增) |
| 轮次显示 | ✅ | ✅ (新增) |
| 历史记录 | ✅ | ✅ (新增) |
| 对比视图 | ✅ | ✅ (新增) |
| 侧边栏状态 | ✅ | ✅ (新增) |
| Canonical Spec | ❌ | ✅ (现有) |
| 飞书同步 | ❌ | ✅ (现有) |
| Gate 验证 | ❌ | ✅ (现有) |

---

## 附录 B：相关文件

- `canonical_frontend/src/App.jsx` — refine UI 主逻辑
- `canonical_frontend/canonical/models/refine.py` — RefineResult 数据结构
- `canonical_frontend/canonical/engine/refiner.py` — LLM 输出逻辑
- `canonical_frontend/docs/mvp_contracts/01_canonical_spec_mvp_schema.md` — Canonical Spec 规范
