标题: Class Sync API 核查与加固

背景:
sync-from-demo 接口历史上出现过「点击同步后复制大量重复课程」的问题。虽已有 fail-fast 预检与 DB 约束，但防重与可观测性仍有缺口：课程创建前无显式 exists 查询；媒体同步分支存在无条件 add_all；响应缺少 skipped_duplicate_courses、skipped_duplicate_media 等可观测字段。

目标:
在已有 fail-fast 基础上，补齐课程创建前 exists 检查、媒体分支统一去重、响应与审计的可观测字段，使同步更幂等、可追溯。

验收标准:
- AC-1: Phase 1 课程创建前增加 exists 查询，若目标班已存在同 course_unit_id 课程则跳过并计入 skipped_duplicate_courses
- AC-2: Phase 2 所有媒体分支统一先构建 existing_media_ids，仅对 media_id not in existing_media_ids 新增
- AC-3: 响应包含 skipped_duplicate_courses、skipped_duplicate_media、precheck_summary、duplicate_guard_hits
- AC-4: 审计 payload 包含 duplicate_guard_hits
- AC-5: 同一班级连续执行 sync-from-demo（dry_run=false）两次，第二次 courses_created=0、media_added=0 或仅新增真实差异
- AC-6: pytest tests/admin/test_sync_* 通过
