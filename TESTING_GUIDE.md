# LLM 需求细化功能测试指南

## 前置条件

### 1. 环境变量配置

确保设置了 LLM API 配置（用于 RequirementRefiner）：

```bash
# 在 canonical_frontend 目录下创建或更新 .env 文件
export CANONICAL_LLM_API_KEY="your-openai-api-key"
export CANONICAL_LLM_BASE_URL="https://api.openai.com/v1"  # 可选，默认 OpenAI
export CANONICAL_LLM_MODEL="gpt-4"  # 可选，默认 gpt-4
```

或者如果使用其他兼容 OpenAI API 的服务：
```bash
export CANONICAL_LLM_API_KEY="your-api-key"
export CANONICAL_LLM_BASE_URL="https://your-api-endpoint/v1"
```

### 2. 检查依赖

确保所有 Python 依赖已安装：
```bash
cd canonical_frontend
source venv/bin/activate  # 如果使用虚拟环境
pip install -r requirements.txt
```

## 测试步骤

### 步骤 1: 重启后端服务

**必须重启后端**，因为：
- 新增了 `canonical/engine/refiner.py` 模块
- 新增了 `canonical/models/refine.py` 模块
- 修改了 `canonical/api.py` 添加了新路由
- Python 模块导入需要重启才能生效

```bash
cd canonical_frontend

# 如果后端正在运行，先停止（Ctrl+C）

# 启动后端（使用 start_api.sh 或直接运行）
bash start_api.sh

# 或者直接运行：
source venv/bin/activate
uvicorn canonical.api:app --host 0.0.0.0 --port 8000 --reload
```

**验证后端启动成功**：
- 访问 http://localhost:8000/docs 应该能看到新的 API 端点：
  - `POST /api/v1/refine`
  - `POST /api/v1/refine/feedback`

### 步骤 2: 刷新前端页面

**前端通常会自动热重载**（Vite 开发服务器），但建议：
1. 硬刷新浏览器页面（Cmd+Shift+R 或 Ctrl+Shift+R）
2. 或者重启前端开发服务器：

```bash
cd canonical_frontend
npm run dev
```

### 步骤 3: 功能测试

#### 测试场景 1: 初始需求细化

1. **打开前端页面**：http://localhost:5173（或 Vite 配置的端口）

2. **点击"创建功能"按钮**

3. **输入模糊需求**，例如：
   ```
   我想做一个健身网站
   ```

4. **点击"开始分析"按钮**

5. **预期结果**：
   - 显示 "AI 需求理解" 摘要（2-3句话）
   - 显示 "推断的假设" 列表
   - 显示 1-2 个关键问题（不是静态模板问题）
   - 每个问题有 "为什么需要" 说明和答案建议

#### 测试场景 2: 多轮对话细化

1. **在测试场景 1 的基础上**，回答显示的问题

2. **点击"提交回答并继续细化"按钮**

3. **预期结果**：
   - 显示新的理解摘要（基于你的回答更新）
   - 可能显示新的问题或确认需求已清晰
   - 如果需求足够清晰，显示 "需求已足够清晰，可以开始创建功能"

4. **继续对话**，直到 `ready_to_compile` 为 true

#### 测试场景 3: 创建功能

1. **当 refine 结果显示 `ready_to_compile: true` 时**

2. **点击"创建功能"按钮**

3. **预期结果**：
   - 调用 `/api/v1/run` 并传入 `refine_result`
   - 使用 `draft_spec` 直接编译，而不是重新分析输入
   - 创建功能并跳转到详情页

#### 测试场景 4: Gate 失败时的智能问题

1. **创建一个功能**（即使 refine 后，Gate 可能仍会失败）

2. **如果 Gate 失败**，查看澄清问题

3. **预期结果**：
   - 问题应该是上下文相关的（基于你的实际需求）
   - 不是静态模板问题（如"你希望这个功能解决的用户痛点一句话是什么？"）
   - 问题会解释为什么需要这个信息

## 调试技巧

### 检查后端日志

后端启动后，查看控制台输出：
- 如果看到 "Warning: Failed to initialize Requirement Refiner"，说明 LLM 配置有问题
- 如果看到 API 调用错误，检查网络连接和 API key

### 检查浏览器控制台

打开浏览器开发者工具（F12），查看：
- Network 标签：检查 API 请求是否成功
- Console 标签：查看是否有 JavaScript 错误

### 测试 API 端点（可选）

使用 curl 或 Postman 直接测试后端：

```bash
# 测试 refine 端点
curl -X POST http://localhost:8000/api/v1/refine \
  -H "Content-Type: application/json" \
  -d '{
    "input": "我想做一个健身网站",
    "context": {
      "conversation_history": [],
      "round": 0
    }
  }'
```

## 常见问题

### Q: 后端启动失败，提示 "ModuleNotFoundError: No module named 'canonical.engine.refiner'"

**A**: 确保在 `canonical_frontend` 目录下运行，并且 Python 路径正确。检查：
```bash
python -c "import canonical.engine.refiner"
```

### Q: 前端显示 "Requirement Refiner not available"

**A**: 检查环境变量 `CANONICAL_LLM_API_KEY` 是否设置，并重启后端。

### Q: Refine 返回的问题还是静态模板问题

**A**: 检查：
1. 后端是否正确使用了 `RequirementRefiner.generate_clarify_questions()`
2. 查看后端日志，确认是否调用了 refiner
3. 检查 `orchestrator.py` 中的逻辑是否正确

### Q: 前端界面没有显示 refine 结果

**A**: 检查：
1. 浏览器控制台是否有错误
2. Network 标签中 `/api/v1/refine` 请求是否成功
3. 响应数据格式是否正确

## 验证清单

- [ ] 后端成功启动，没有导入错误
- [ ] `/api/v1/refine` 端点可访问（在 /docs 中可见）
- [ ] 前端页面正常加载
- [ ] 输入模糊需求后，显示 AI 理解摘要
- [ ] 显示的问题不是静态模板，而是上下文相关的
- [ ] 多轮对话可以正常进行
- [ ] `ready_to_compile` 为 true 时可以创建功能
- [ ] Gate 失败时的问题也是智能生成的

## 下一步

测试通过后，可以：
1. 优化 prompt 以获得更好的问题质量
2. 调整 refine 的判断逻辑（何时认为需求足够清晰）
3. 添加更多 UI 优化（如加载动画、错误提示等）
