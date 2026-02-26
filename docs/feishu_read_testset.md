# Feishu 读取真实联调用例集

用于 Feishu 文档读取能力的端到端验收。需配置 `CANONICAL_FEISHU_APP_ID` 和 `CANONICAL_FEISHU_APP_SECRET`。

## 用例分类

### 1. Docx 文档（成功路径）

- **类型**: 新版飞书文档
- **URL 格式**: `https://xxx.feishu.cn/docx/{document_id}`
- **预期**: 返回 `title`、`plain_text`、`blocks`、`source_url`
- **测试 URL**: 请替换为你有权限的 docx 文档链接

```
FEISHU_DOCX_URL="https://your-tenant.feishu.cn/docx/YOUR_DOCUMENT_ID"
```

### 2. Docs 文档（成功路径，旧版）

- **类型**: 旧版飞书文档
- **URL 格式**: `https://xxx.feishu.cn/docs/{doc_token}`
- **预期**: 返回 `title`、`plain_text`、`blocks`、`source_url`
- **测试 URL**: 请替换为你有权限的 docs 文档链接

```
FEISHU_DOCS_URL="https://your-tenant.feishu.cn/docs/YOUR_DOC_TOKEN"
```

### 3. Wiki 文档（成功路径）

- **类型**: 飞书知识库页面
- **URL 格式**: `https://xxx.feishu.cn/wiki/{space_id}/{node_token}` 或 `https://xxx.feishu.cn/wiki/{node_token}`
- **预期**: 返回 `title`、`plain_text`、`blocks`、`source_url`
- **测试 URL**: 请替换为你有权限的 wiki 页面链接

```
FEISHU_WIKI_URL="https://your-tenant.feishu.cn/wiki/YOUR_SPACE_ID/YOUR_NODE_TOKEN"
```

### 4. 无权限文档（失败路径）

- **类型**: 应用无访问权限的文档
- **预期**: 返回 403，`debug` 含 `code`、`msg`、`request_id`
- **测试 URL**: 使用未授权给应用的文档链接

### 5. 无效 Token（失败路径）

- **类型**: 不存在的 document_id
- **测试**: `--document-token InvalidToken123`
- **预期**: 返回 404 或 502，`debug` 可定位错误原因

## 验收顺序

1. CLI 成功读取私有 docx 文档
2. API 成功读取同一文档并返回结构化结果
3. 无权限/无效 token 场景返回可定位 `debug` 字段
