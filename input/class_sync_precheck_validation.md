标题: 班级同步功能严格预检机制

背景:
当前的班级同步功能（从Demo班同步到目标班）在源课程数据不完整时，可能导致严重的同步错误。例如：
1. 当源课程的course_level_id或course_unit_id缺失时，同步功能可能无法正确匹配课程
2. 之前出现过点击同步后，目标课程会把源课程对应的所有内容完整复制一遍，导致目标课程多出一倍的课程量
3. 这种问题会导致数据不一致，影响教学进度和统计准确性

目标:
为班级同步功能添加严格的预检机制，确保在数据不完整时拒绝同步操作，避免产生错误的数据。

验收标准:
- AC-1: 目标班级必须具备course_level_id，否则返回错误
- AC-2: Demo班级必须具备course_level_id，且与目标班级一致，否则返回错误
- AC-3: Demo班级和目标班级内的所有课程必须同时具备course_level_id与course_unit_id，否则返回错误
- AC-4: 课程的course_level_id必须与所属班级一致，否则返回错误
- AC-5: 课程的course_unit_id必须存在，且其course_level_id必须与课程一致，否则返回错误
- AC-6: 任一校验失败将直接返回错误，不执行任何同步写入操作
- AC-7: 错误信息清晰明确，指出具体的数据问题
- AC-8: 添加预检测试脚本，覆盖多种错误场景

技术实现:
- 在 `backend/app/routers/class_management.py` 的 `_sync_class_from_demo_impl` 函数中添加预检逻辑
- 检查班级的course_level_id完整性
- 检查课程的course_level_id和course_unit_id完整性
- 验证课程与班级的一致性
- 验证course_unit_id的有效性和关联关系
- 添加测试脚本 `backend/tests/admin/test_sync_precheck_validation.py`
- 更新API文档 `docs/api/v1/admin/08_class_management.md`

相关文件:
- backend/app/routers/class_management.py
- backend/tests/admin/test_sync_precheck_validation.py
- docs/api/v1/admin/08_class_management.md
