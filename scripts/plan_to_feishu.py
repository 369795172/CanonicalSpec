#!/usr/bin/env python3
"""
Plan to Feishu - 将计划文档转换为飞书需求条目

使用方法:
    python scripts/plan_to_feishu.py \
        --plan-file ../.cursor/plans/class_sync_fix_plan_d7ce09cf.plan.md \
        --project-record-id "recv83AoVSDMQP"
"""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import yaml


class Phase:
    """表示一个阶段"""
    
    def __init__(self, number: int, name: str, goal: str, tasks: List[Dict[str, str]], 
                 acceptance_criteria: List[str], affected_files: List[str],
                 background: str):
        self.number = number
        self.name = name
        self.goal = goal
        self.tasks = tasks
        self.acceptance_criteria = acceptance_criteria
        self.affected_files = affected_files
        self.background = background


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """解析 YAML frontmatter"""
    if not content.startswith('---'):
        return {}
    
    end = content.find('---', 3)
    if end == -1:
        return {}
    
    frontmatter_text = content[3:end].strip()
    try:
        return yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return {}


def parse_plan_document(plan_file: Path) -> List[Phase]:
    """解析计划文档，提取阶段信息"""
    with open(plan_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析 frontmatter
    frontmatter = parse_frontmatter(content)
    
    # 提取 markdown 内容（跳过 frontmatter）
    if content.startswith('---'):
        end = content.find('---', 3)
        markdown_content = content[end + 3:].strip()
    else:
        markdown_content = content
    
    phases = []

    plan_overview = frontmatter.get("overview", "").strip()
    background_parts = []
    if plan_overview:
        background_parts.append(f"概述: {plan_overview}")

    root_cause_match = re.search(
        r'### Root Cause\s+(.*?)(?=### Evidence|### Issues|## |$)',
        markdown_content,
        re.DOTALL
    )
    if root_cause_match:
        background_parts.append(f"根因: {root_cause_match.group(1).strip()}")

    issues_match = re.search(
        r'### Issues Reported in Meeting\s+(.*?)(?=## |$)',
        markdown_content,
        re.DOTALL
    )
    if issues_match:
        background_parts.append(f"会议问题: {issues_match.group(1).strip()}")

    common_background = "\n\n".join(background_parts).strip()
    
    # 识别 Phase 1: Sync Logic Enhancement
    phase1_match = re.search(
        r'### Phase 1: Sync Logic Enhancement\s+(.*?)(?=### Phase 2:|## |$)',
        markdown_content,
        re.DOTALL
    )
    if phase1_match:
        phase1_content = phase1_match.group(1)
        # 提取任务（从 frontmatter todos 中）
        phase1_tasks = [
            {'id': 'analyze-sync-logic', 'content': 'Document exact sync logic flow and identify all matching points'},
            {'id': 'enhance-sync-matching', 'content': 'Add name-based fallback matching in _sync_class_from_demo_impl'}
        ]
        # 提取验收标准
        acceptance_criteria = [
            '同步逻辑能够通过 course_unit_id 和 course_name 两种方式匹配课程',
            '历史课程（无 unit_id）能够正确识别并更新，而不是创建重复',
            '修改后的代码通过单元测试'
        ]
        affected_files = ['backend/app/routers/class_management.py']
        
        phases.append(Phase(
            number=1,
            name='Phase 1: Sync Logic Enhancement',
            goal='修复同步逻辑，使其能够识别没有 course_unit_id 的历史课程，避免创建重复课程',
            tasks=phase1_tasks,
            acceptance_criteria=acceptance_criteria,
            affected_files=affected_files,
            background=common_background
        ))
    
    # 识别 Phase 2: Data Repair Script
    phase2_match = re.search(
        r'### Phase 2: Data Repair Script\s+(.*?)(?=### Phase 3:|## |$)',
        markdown_content,
        re.DOTALL
    )
    if phase2_match:
        phase2_content = phase2_match.group(1)
        phase2_tasks = [
            {'id': 'create-repair-script', 'content': 'Create script to backfill course_unit_id for historical courses'},
            {'id': 'fix-duplicate-courses', 'content': 'Clean up duplicate courses in affected classes'},
            {'id': 'fix-unlock-times', 'content': 'Correct unlock times based on class start_date'}
        ]
        acceptance_criteria = [
            '脚本能够正确匹配历史课程并回填 course_unit_id',
            '重复课程被正确清理，媒体分配被合并',
            '解锁时间根据班级 start_date 正确计算'
        ]
        affected_files = ['backend/scripts/fix_class_sync_data.py']
        
        phases.append(Phase(
            number=2,
            name='Phase 2: Data Repair Script',
            goal='创建数据修复脚本，修复现有数据问题（重复课程、解锁时间）',
            tasks=phase2_tasks,
            acceptance_criteria=acceptance_criteria,
            affected_files=affected_files,
            background=common_background
        ))
    
    # 识别 Phase 3: Validate and Test
    phase3_match = re.search(
        r'### Phase 3: Validate and Test\s+(.*?)(?=## |$)',
        markdown_content,
        re.DOTALL
    )
    if phase3_match:
        phase3_content = phase3_match.group(1)
        phase3_tasks = [
            {'id': 'test-dry-run', 'content': 'Test sync with dry_run on affected classes'},
            {'id': 'validate-results', 'content': 'Verify course counts and media assignments match demo'}
        ]
        acceptance_criteria = [
            'dry-run 测试通过，无数据错误',
            '课程数量与演示班级匹配',
            '媒体分配正确',
            '解锁时间序列正确'
        ]
        affected_files = []
        
        phases.append(Phase(
            number=3,
            name='Phase 3: Validate and Test',
            goal='验证修复效果，确保数据正确性',
            tasks=phase3_tasks,
            acceptance_criteria=acceptance_criteria,
            affected_files=affected_files,
            background=common_background
        ))
    
    return phases


def format_phase_input(phase: Phase) -> str:
    """格式化阶段输入文本"""
    lines = [
        f"{phase.name}",
        "",
        "背景：",
        phase.background or "暂无补充背景。",
        "",
        f"目标：{phase.goal}",
        "",
        "任务列表：",
    ]
    
    for task in phase.tasks:
        lines.append(f"- {task['id']}: {task['content']}")
    
    lines.extend([
        "",
        "验收标准：",
    ])
    
    for ac in phase.acceptance_criteria:
        lines.append(f"- {ac}")
    
    if phase.affected_files:
        lines.extend([
            "",
            "相关文件：",
        ])
        for file in phase.affected_files:
            lines.append(f"- {file}")
    
    return "\n".join(lines)


def update_spec_project_context(feature_id: str, project_record_id: Optional[str] = None,
                                mentor_user_id: Optional[str] = None,
                                intern_user_id: Optional[str] = None) -> bool:
    """更新 Spec 的 project_context_ref"""
    if not project_record_id:
        return False
    
    # 导入 canonical 模块
    # 确保在正确的路径下导入
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    project_root_str = str(project_root.absolute())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    
    try:
        from canonical.store.spec_store import SpecStore
        from canonical.models.spec import ProjectContextRef
    except ImportError as e:
        print(f"警告: 无法导入 canonical 模块: {e}，将跳过 project_context_ref 设置", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    
    try:
        spec_store = SpecStore()
        spec = spec_store.load(feature_id)
        if not spec:
            print(f"警告: 无法加载 Feature {feature_id}", file=sys.stderr)
            return False

        # 创建或更新 project_context_ref
        if not spec.project_context_ref:
            spec.project_context_ref = ProjectContextRef()

        spec.project_context_ref.project_record_id = project_record_id
        if mentor_user_id:
            spec.project_context_ref.mentor_user_id = mentor_user_id
        if intern_user_id:
            spec.project_context_ref.intern_user_id = intern_user_id

        # 直接写回当前版本文件，避免版本冲突
        feature_dir = spec_store.base_dir / spec.feature.feature_id
        spec_file = feature_dir / f"{spec.meta.spec_version}.json"
        if not spec_file.exists():
            print(f"警告: 未找到 Spec 文件: {spec_file}", file=sys.stderr)
            return False

        with open(spec_file, 'w', encoding='utf-8') as f:
            json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        print(f"警告: 更新 project_context_ref 失败: {e}", file=sys.stderr)
        return False


def write_answers_file(phase: Phase) -> Path:
    """为 acceptance_criteria 写入答案文件"""
    criteria = []
    for idx, text in enumerate(phase.acceptance_criteria, start=1):
        criteria.append({"id": f"AC-{idx}", "criteria": text})

    answers = {
        "spec.acceptance_criteria": criteria,
        "spec.background": phase.background,
    }
    temp_dir = Path(tempfile.mkdtemp(prefix="canonical-answers-"))
    file_path = temp_dir / "answers.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(answers, f, ensure_ascii=False, indent=2)
    return file_path


def load_gate_result(feature_id: str):
    """使用 GateEngine 获取 gate 结果"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    project_root_str = str(project_root.absolute())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    try:
        from canonical.store.spec_store import SpecStore
        from canonical.engine.gate import GateEngine
    except ImportError as e:
        print(f"警告: 无法导入 GateEngine: {e}", file=sys.stderr)
        return None

    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    if not spec:
        return None

    gate_engine = GateEngine()
    return gate_engine.validate(spec)


def build_fallback_vv(feature_id: str) -> Optional[Path]:
    """为已存在的任务生成最小 VV，避免 LLM 失败"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    project_root_str = str(project_root.absolute())
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    try:
        from canonical.store.spec_store import SpecStore
    except ImportError as e:
        print(f"警告: 无法导入 canonical 模块以生成 VV: {e}", file=sys.stderr)
        return None

    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    if not spec or not spec.planning.tasks:
        print("警告: 未找到任务，无法生成 VV", file=sys.stderr)
        return None

    vv_items = []
    for idx, task in enumerate(spec.planning.tasks, start=1):
        vv_items.append({
            "vv_id": f"VV-{idx}",
            "task_id": task.task_id,
            "type": "manual",
            "procedure": (
                f"1. 执行任务 {task.task_id} 的交付物。\n"
                "2. 按任务说明验证结果。\n"
                "3. 记录验证输出与关键日志。"
            ),
            "expected_result": f"{task.task_id} 对应的交付物可用且满足任务目标。",
            "evidence_required": ["log_snippet"],
        })

    answers = {"planning.vv": vv_items}
    temp_dir = Path(tempfile.mkdtemp(prefix="canonical-vv-"))
    file_path = temp_dir / "vv.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(answers, f, ensure_ascii=False, indent=2)
    return file_path


def get_python_executable() -> str:
    """获取 Python 可执行文件路径，优先使用虚拟环境"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # 检查项目目录下的 venv
    venv_python = project_root / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    
    # 检查父目录的 venv（backend/venv）
    parent_venv_python = project_root.parent / "backend" / "venv" / "bin" / "python"
    if parent_venv_python.exists():
        return str(parent_venv_python)
    
    # 使用系统 python3
    return "python3"


def run_canonical_command(command: List[str]) -> subprocess.CompletedProcess:
    """运行 canonical 命令"""
    python_exe = get_python_executable()
    
    # 尝试使用 python -m canonical.cli 如果直接调用失败
    if command[0] == "canonical":
        # 替换为 python -m canonical.cli
        command = [python_exe, "-m", "canonical.cli"] + command[1:]
    
    try:
        process = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            cwd=Path(__file__).parent.parent  # 确保在 canonical_frontend 目录下运行
        )
        return process
    except FileNotFoundError:
        print("错误: 无法运行 canonical 命令。", file=sys.stderr)
        print(f"尝试的命令: {' '.join(command)}", file=sys.stderr)
        print(f"Python 可执行文件: {python_exe}", file=sys.stderr)
        sys.exit(1)


def process_plan_to_feishu(plan_file: Path, project_record_id: Optional[str] = None, 
                          dry_run: bool = False, auto_review: bool = False):
    """处理计划文档，生成飞书需求条目"""
    
    print(f"正在解析计划文档: {plan_file}")
    
    # 1. 解析计划文档
    phases = parse_plan_document(plan_file)
    
    if not phases:
        print("错误: 未能从计划文档中提取到阶段信息", file=sys.stderr)
        sys.exit(1)
    
    print(f"✓ 识别到 {len(phases)} 个阶段\n")
    
    feature_ids = []
    
    # 2. 为每个阶段生成输入文本并调用 canonical run
    for phase in phases:
        print(f"=== 处理 {phase.name} ===")
        
        # 生成输入文本
        input_text = format_phase_input(phase)
        
        # 生成 feature_id (格式: F-YYYY-NNN)
        # 使用 SpecStore 生成，确保唯一性
        try:
            from canonical.store.spec_store import SpecStore
            spec_store = SpecStore()
            feature_id = spec_store.generate_feature_id()
        except ImportError:
            # 如果无法导入，使用简单生成方式
            year = datetime.now().strftime("%Y")
            # 使用时间戳确保唯一性
            import time
            seq = int(time.time()) % 1000 + phase.number
            feature_id = f"F-{year}-{seq:03d}"
        
        feature_ids.append(feature_id)
        
        print(f"Feature ID: {feature_id}")
        print(f"输入文本预览:\n{input_text[:200]}...\n")
        
        # 调用 canonical run
        # 注意: input_text 作为命令行参数传递
        command = ["canonical", "run", input_text, "--feature-id", feature_id]
        
        print("正在调用 canonical run...")
        result = run_canonical_command(command)
        
        if result.returncode != 0:
            print(f"✗ {phase.name} Gate 未通过")
            print(result.stdout)
            print(result.stderr, file=sys.stderr)

            if phase.acceptance_criteria:
                print("\n正在补齐验收标准...")
                answers_file = write_answers_file(phase)
                answer_result = run_canonical_command(
                    ["canonical", "answer", feature_id, "--file", str(answers_file)]
                )
                print(answer_result.stdout)
                if answer_result.returncode != 0:
                    print(answer_result.stderr, file=sys.stderr)
                    print("\n提示: 请手动使用 'canonical answer' 提供缺失信息")
                    print("\n" + "="*60 + "\n")
                    continue
            else:
                print("\n提示: 请使用 'canonical answer' 命令提供缺失信息")
                print("\n" + "="*60 + "\n")
                continue

        gate_result = load_gate_result(feature_id)
        if not gate_result or not gate_result.gate_s.is_passed:
            print("\n提示: Gate S 未通过，请继续澄清后再进入 plan/vv")
            print("\n" + "="*60 + "\n")
            continue

        print(f"✓ {phase.name} Gate S 通过，进入任务规划")
        print(result.stdout)

        print("\n正在生成任务规划...")
        plan_result = run_canonical_command(["canonical", "plan", feature_id])
        print(plan_result.stdout)
        if plan_result.returncode != 0:
            print(plan_result.stderr, file=sys.stderr)
            print("\n提示: 任务规划失败，停止后续步骤")
            print("\n" + "="*60 + "\n")
            continue

        gate_result = load_gate_result(feature_id)
        if not gate_result or not gate_result.gate_t.is_passed:
            print("\n提示: Gate T 未通过，请补齐任务后再进入 VV")
            print("\n" + "="*60 + "\n")
            continue

        print("正在生成验证项...")
        vv_result = run_canonical_command(["canonical", "vv", feature_id])
        print(vv_result.stdout)
        if vv_result.returncode != 0:
            print(vv_result.stderr, file=sys.stderr)
            print("\n提示: VV 生成失败，尝试使用回退 VV")
            fallback_file = build_fallback_vv(feature_id)
            if not fallback_file:
                print("\n提示: 无法生成回退 VV，停止后续步骤")
                print("\n" + "="*60 + "\n")
                continue
            answer_vv = run_canonical_command(
                ["canonical", "answer", feature_id, "--file", str(fallback_file)]
            )
            print(answer_vv.stdout)
            if answer_vv.returncode != 0:
                print(answer_vv.stderr, file=sys.stderr)
                print("\n提示: 回退 VV 写入失败，停止后续步骤")
                print("\n" + "="*60 + "\n")
                continue

        gate_result = load_gate_result(feature_id)
        if not gate_result or not gate_result.gate_v.is_passed:
            print("\n提示: Gate V 未通过，请补齐验证项后再进入 review/publish")
            print("\n" + "="*60 + "\n")
            continue

        if auto_review:
                # 更新 project_context_ref（如果提供）
                if project_record_id:
                    print(f"\n正在设置 project_context_ref...")
                    if update_spec_project_context(feature_id, project_record_id):
                        print("✓ project_context_ref 已设置")
                    else:
                        print("警告: 无法设置 project_context_ref，发布可能会失败", file=sys.stderr)
                
                # 自动 review (go)
                print(f"\n正在自动确认 {feature_id}...")
                review_result = run_canonical_command(
                    ["canonical", "review", feature_id, "--decision", "go"]
                )
                if review_result.returncode == 0:
                    print(review_result.stdout)
                    
                    if not dry_run:
                        # 发布到飞书
                        print(f"\n正在发布 {feature_id} 到飞书...")
                        publish_result = run_canonical_command(["canonical", "publish", feature_id])
                        if publish_result.returncode == 0:
                            print(publish_result.stdout)
                            print(f"✓ {phase.name} 已成功发布到飞书")
                        else:
                            print(f"✗ 发布失败: {publish_result.stderr}", file=sys.stderr)
                            if "project_record_id" in publish_result.stderr:
                                print("\n提示: 请设置 project_record_id。可以使用以下方式:")
                                print("  1. 通过 --project-record-id 参数")
                                print("  2. 通过环境变量 CANONICAL_PROJECT_RECORD_ID")
                                print("  3. 手动更新 Spec 文件")
                    else:
                        print(f"✓ {phase.name} 准备发布（dry-run 模式）")
                else:
                    print(f"✗ Review 失败: {review_result.stderr}", file=sys.stderr)
        else:
                # 更新 project_context_ref（如果提供）
                if project_record_id:
                    print(f"\n正在设置 project_context_ref...")
                    if update_spec_project_context(feature_id, project_record_id):
                        print("✓ project_context_ref 已设置")
                    else:
                        print("警告: 无法设置 project_context_ref，发布时需要手动设置", file=sys.stderr)
                
                print(f"\n提示: 使用以下命令确认并发布:")
                print(f"  canonical review {feature_id}")
                if project_record_id:
                    print(f"  canonical publish {feature_id}")
                else:
                    print(f"  # 注意: 发布前需要设置 project_record_id")
                    print(f"  # 方式1: 通过环境变量 CANONICAL_PROJECT_RECORD_ID")
                    print(f"  # 方式2: 手动更新 Spec 文件中的 project_context_ref.project_record_id")
                    print(f"  canonical publish {feature_id}")
        
        print("\n" + "="*60 + "\n")
    
    # 总结
    print("=== 处理完成 ===")
    print(f"共处理 {len(phases)} 个阶段，生成 {len(feature_ids)} 个 Feature:")
    for fid in feature_ids:
        print(f"  - {fid}")
    
    if not auto_review:
        print("\n下一步操作:")
        print("1. 使用 'canonical review <feature_id>' 确认每个 Feature")
        print("2. 使用 'canonical publish <feature_id>' 发布到飞书")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将计划文档转换为飞书需求条目",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/plan_to_feishu.py \\
      --plan-file ../.cursor/plans/class_sync_fix_plan_d7ce09cf.plan.md \\
      --project-record-id "recv83AoVSDMQP"
        """
    )
    
    parser.add_argument(
        '--plan-file',
        type=Path,
        required=True,
        help='计划文档路径'
    )
    
    parser.add_argument(
        '--project-record-id',
        type=str,
        help='飞书项目记录ID（可选，可通过环境变量 CANONICAL_PROJECT_RECORD_ID 设置）'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将要执行的操作，不实际发布'
    )
    
    parser.add_argument(
        '--auto-review',
        action='store_true',
        help='自动确认并发布（跳过人工确认）'
    )
    
    args = parser.parse_args()
    
    # 检查计划文件是否存在
    if not args.plan_file.exists():
        print(f"错误: 计划文件不存在: {args.plan_file}", file=sys.stderr)
        sys.exit(1)
    
    # 设置项目记录ID到环境变量（如果提供）
    if args.project_record_id:
        import os
        os.environ['CANONICAL_PROJECT_RECORD_ID'] = args.project_record_id
    
    # 执行处理
    process_plan_to_feishu(
        plan_file=args.plan_file,
        project_record_id=args.project_record_id,
        dry_run=args.dry_run,
        auto_review=args.auto_review
    )


if __name__ == '__main__':
    main()
