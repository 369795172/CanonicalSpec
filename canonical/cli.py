"""
Canonical CLI - Command line interface for the Canonical system.

Commands:
- run: Execute initial pipeline (input -> compile -> validate)
- answer: Apply answers to a feature
- review: Apply manual review decision
- publish: Publish a feature to Feishu
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from canonical import __version__
from canonical.config import config
from canonical.models.spec import CanonicalSpec, FeatureStatus
from canonical.models.gate import GateResult
from canonical.engine.gate import GateEngine
from canonical.engine.orchestrator import Orchestrator
from canonical.store.spec_store import SpecStore
from canonical.store.ledger import Ledger
from canonical.adapters.feishu import FeishuPublisher, FeishuReader


def print_gate_result(gate_result: GateResult) -> None:
    """Print gate result in a formatted way."""
    click.echo("\n=== Gate 验证结果 ===")
    click.echo(f"Gate S (规格完整性): {'✓ PASS' if gate_result.gate_s.is_passed else '✗ FAIL'}")
    click.echo(f"Gate T (任务存在性): {'✓ PASS' if gate_result.gate_t.is_passed else '✗ FAIL'}")
    click.echo(f"Gate V (验证覆盖率): {'✓ PASS' if gate_result.gate_v.is_passed else '✗ FAIL'}")
    click.echo(f"完整度评分: {gate_result.completeness_score:.2f}")
    click.echo(f"总体通过: {'✓ YES' if gate_result.overall_pass else '✗ NO'}")
    click.echo(f"下一步操作: {gate_result.next_action}")
    
    if gate_result.clarify_questions:
        click.echo("\n--- 需要澄清的问题 ---")
        for q in gate_result.clarify_questions:
            click.echo(f"  [{q.id}] {q.question}")
            click.echo(f"       (字段: {q.field_path})")


def print_spec_summary(spec: CanonicalSpec) -> None:
    """Print spec summary."""
    click.echo("\n=== 需求规格摘要 ===")
    click.echo(f"Feature ID: {spec.feature.feature_id}")
    click.echo(f"标题: {spec.feature.title}")
    click.echo(f"状态: {spec.feature.status.value}")
    click.echo(f"版本: {spec.meta.spec_version}")
    click.echo(f"目标: {spec.spec.goal[:100]}..." if len(spec.spec.goal) > 100 else f"目标: {spec.spec.goal}")
    click.echo(f"验收标准数量: {len(spec.spec.acceptance_criteria)}")
    click.echo(f"任务数量: {len(spec.planning.tasks)}")
    click.echo(f"验证项数量: {len(spec.planning.vv)}")


@click.group()
@click.version_option(version=__version__)
def cli():
    """Canonical - 需求规格管理系统"""
    # Ensure data directories exist
    config.ensure_directories()


@cli.command()
@click.argument('input_text', required=False)
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True), help='从文件读取需求描述')
@click.option('--feature-id', '-f', help='指定 Feature ID (可选，默认自动生成)')
@click.option('--output', '-o', type=click.Path(), help='输出 spec 到文件')
def run(input_text: Optional[str], input_file: Optional[str], feature_id: Optional[str], output: Optional[str]):
    """
    执行初始 Pipeline: 输入 -> 编译 -> 验证
    
    支持两种输入方式：
    1. 通过 --input/-i 选项指定文件路径
    2. 直接在命令行传递文本内容（INPUT_TEXT）
    
    如果两者都提供，优先使用 --input 文件。
    """
    # 确定输入内容
    final_input_text = None
    
    if input_file:
        # 从文件读取
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                final_input_text = f.read()
            click.echo(f"从文件读取输入: {input_file}")
        except Exception as e:
            click.echo(f"\n✗ 读取文件失败: {str(e)}", err=True)
            sys.exit(2)
    elif input_text:
        # 使用命令行参数
        final_input_text = input_text
    else:
        # 两者都未提供
        click.echo("错误: 必须提供输入内容。使用方式：", err=True)
        click.echo("  1. python -m canonical.cli run --input <文件路径>")
        click.echo("  2. python -m canonical.cli run \"需求描述文本\"")
        sys.exit(1)
    
    if input_file and input_text:
        click.echo("警告: 同时提供了 --input 文件和命令行文本，将使用文件内容", err=True)
    
    click.echo(f"正在处理输入: {final_input_text[:50]}...")
    
    try:
        orchestrator = Orchestrator()
        spec, gate_result = orchestrator.run(final_input_text, feature_id)
        
        print_spec_summary(spec)
        print_gate_result(gate_result)
        
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
            click.echo(f"\nSpec 已保存到: {output}")
        
        # Exit with appropriate code
        if gate_result.overall_pass:
            click.echo("\n✓ 所有 Gate 通过，可以进入人工确认")
            sys.exit(0)
        else:
            click.echo("\n✗ Gate 验证未通过，请使用 'canonical answer' 提供缺失信息")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.argument('feature_id')
@click.option('--file', '-f', type=click.Path(exists=True), help='从 JSON 文件读取答案')
@click.option('--answer', '-a', multiple=True, help='直接提供答案 (格式: field_path=value)')
def answer(feature_id: str, file: Optional[str], answer: tuple):
    """
    应用答案到指定 Feature
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    answers = {}
    
    # Load answers from file
    if file:
        with open(file, 'r', encoding='utf-8') as f:
            answers = json.load(f)
    
    # Add command line answers (override file)
    for a in answer:
        if '=' in a:
            field_path, value = a.split('=', 1)
            answers[field_path.strip()] = value.strip()
    
    if not answers:
        click.echo("错误: 未提供答案。使用 --file 或 --answer 选项", err=True)
        sys.exit(1)
    
    click.echo(f"正在应用 {len(answers)} 个答案到 {feature_id}...")
    
    try:
        orchestrator = Orchestrator()
        spec, gate_result = orchestrator.answer(feature_id, answers)
        
        print_spec_summary(spec)
        print_gate_result(gate_result)
        
        if gate_result.overall_pass:
            click.echo("\n✓ 所有 Gate 通过，可以进入人工确认")
            sys.exit(0)
        else:
            click.echo("\n✗ Gate 验证未通过，请继续提供缺失信息")
            sys.exit(1)
            
    except ValueError as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.argument('feature_id')
@click.option('--decision', '-d', type=click.Choice(['go', 'hold', 'drop']), help='直接指定决策')
@click.option('--rationale', '-r', help='决策理由')
def review(feature_id: str, decision: Optional[str], rationale: Optional[str]):
    """
    人工确认 Feature
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    
    if not spec:
        click.echo(f"错误: Feature {feature_id} 不存在", err=True)
        sys.exit(1)
    
    # Show spec summary
    print_spec_summary(spec)
    
    # Validate gates
    gate_engine = GateEngine()
    gate_result = gate_engine.validate(spec)
    print_gate_result(gate_result)
    
    # Get decision interactively if not provided
    if not decision:
        click.echo("\n请选择操作:")
        click.echo("  [g] go - 发布到 Feishu")
        click.echo("  [h] hold - 暂缓")
        click.echo("  [d] drop - 放弃")
        
        choice = click.prompt("选择", type=str, default="h")
        decision_map = {'g': 'go', 'h': 'hold', 'd': 'drop'}
        decision = decision_map.get(choice.lower(), 'hold')
        
        if decision in ['hold', 'drop']:
            rationale = click.prompt("请输入理由 (可选)", default="", show_default=False)
    
    try:
        orchestrator = Orchestrator()
        updated_spec = orchestrator.review(feature_id, decision, rationale or None)
        
        click.echo(f"\n✓ 决策已应用: {decision}")
        click.echo(f"   新状态: {updated_spec.feature.status.value}")
        
        if decision == 'go':
            click.echo("\n提示: 使用 'canonical publish' 命令发布到 Feishu")
        
        sys.exit(0)
        
    except ValueError as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.argument('feature_id')
@click.option('--dry-run', is_flag=True, help='仅显示将要发布的内容，不实际发布')
def publish(feature_id: str, dry_run: bool):
    """
    发布 Feature 到 Feishu
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    
    if not spec:
        click.echo(f"错误: Feature {feature_id} 不存在", err=True)
        sys.exit(1)
    
    # Check status
    if spec.feature.status != FeatureStatus.EXECUTABLE_READY:
        click.echo(f"错误: Feature 状态必须是 executable_ready，当前: {spec.feature.status.value}", err=True)
        click.echo("提示: 使用 'canonical review' 命令进行人工确认", err=True)
        sys.exit(1)
    
    print_spec_summary(spec)
    
    if dry_run:
        click.echo("\n=== Dry Run 模式 ===")
        click.echo("以下内容将被发布到 Feishu:")
        click.echo(f"  标题: {spec.feature.title}")
        click.echo(f"  目标: {spec.spec.goal[:100]}...")
        click.echo(f"  验收标准: {len(spec.spec.acceptance_criteria)} 条")
        click.echo(f"  任务: {len(spec.planning.tasks)} 个")
        click.echo(f"  验证项: {len(spec.planning.vv)} 个")
        sys.exit(0)
    
    try:
        publisher = FeishuPublisher()
        result = publisher.publish(spec)
        
        click.echo("\n=== 发布结果 ===")
        click.echo(f"操作: {result['operation']}")
        click.echo(f"External ID: {result['external_id']}")
        click.echo(f"状态: {result['status']}")
        click.echo(f"Spec Version: {result['spec_version']}")
        
        if result['operation'] == 'noop':
            click.echo("\n注意: 此版本已经发布过，无需重复发布")
        else:
            click.echo(f"\n✓ 发布成功!")
        
        sys.exit(0)
        
    except ValueError as e:
        click.echo(f"\n✗ 发布失败: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.option('--url', '-u', help='飞书文档 URL (docx/docs/wiki)')
@click.option('--document-token', '-d', help='文档 token (document_id)')
@click.option('--wiki-token', help='Wiki node_token (需配合 --wiki-space-id)')
@click.option('--wiki-space-id', help='Wiki space_id (需配合 --wiki-token)')
@click.option('--debug', is_flag=True, help='输出 debug 字段')
def read_feishu(url: Optional[str], document_token: Optional[str], wiki_token: Optional[str], wiki_space_id: Optional[str], debug: bool):
    """
    读取飞书文档内容

    支持 docx/docs/wiki 链接。使用 --url 或 --document-token 或 (--wiki-token + --wiki-space-id)。
    """
    if not url and not document_token and not (wiki_token and wiki_space_id):
        click.echo("错误: 必须提供 --url 或 --document-token 或 (--wiki-token + --wiki-space-id)", err=True)
        sys.exit(1)

    try:
        reader = FeishuReader()
        result = reader.read(
            url=url,
            document_token=document_token,
            wiki_token=wiki_token,
            wiki_space_id=wiki_space_id,
        )

        if result.get("debug"):
            click.echo(f"\n✗ 读取失败: {result['debug'].get('msg', 'Unknown error')}", err=True)
            if debug:
                click.echo(json.dumps(result["debug"], indent=2, ensure_ascii=False))
            sys.exit(2)

        click.echo(f"\n=== 标题 ===\n{result.get('title', '')}")
        click.echo(f"\n=== 正文 ===\n{result.get('plain_text', '')}")
        if debug:
            click.echo(f"\n=== Debug ===\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        sys.exit(0)

    except Exception as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.argument('feature_id')
def show(feature_id: str):
    """
    显示 Feature 详情
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    
    if not spec:
        click.echo(f"错误: Feature {feature_id} 不存在", err=True)
        sys.exit(1)
    
    # Print full spec
    click.echo(json.dumps(spec.model_dump(mode='json'), indent=2, ensure_ascii=False, default=str))


@cli.command()
@click.option('--status', '-s', type=click.Choice(['all', 'draft', 'clarifying', 'executable_ready', 'published', 'hold', 'drop']), default='all')
def list(status: str):
    """
    列出所有 Features
    """
    spec_store = SpecStore()
    features = spec_store.list_features()
    
    if not features:
        click.echo("没有找到任何 Feature")
        sys.exit(0)
    
    click.echo(f"\n{'Feature ID':<15} {'状态':<18} {'标题':<30} {'版本':<20}")
    click.echo("-" * 85)
    
    for feature_id in features:
        spec = spec_store.load(feature_id)
        if spec:
            if status != 'all' and spec.feature.status.value != status:
                continue
            title = spec.feature.title[:28] + ".." if len(spec.feature.title) > 30 else spec.feature.title
            version = spec.meta.spec_version or "N/A"
            click.echo(f"{feature_id:<15} {spec.feature.status.value:<18} {title:<30} {version:<20}")


@cli.command()
@click.argument('feature_id')
def validate(feature_id: str):
    """
    验证 Feature 的 Gate 状态
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    spec_store = SpecStore()
    spec = spec_store.load(feature_id)
    
    if not spec:
        click.echo(f"错误: Feature {feature_id} 不存在", err=True)
        sys.exit(1)
    
    gate_engine = GateEngine()
    gate_result = gate_engine.validate(spec)
    
    print_spec_summary(spec)
    print_gate_result(gate_result)
    
    if gate_result.overall_pass:
        sys.exit(0)
    else:
        sys.exit(1)


@cli.command()
@click.argument('feature_id')
def plan(feature_id: str):
    """
    为 Feature 生成任务规划
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    try:
        orchestrator = Orchestrator()
        spec, gate_result = orchestrator.plan_tasks(feature_id)
        
        click.echo(f"\n✓ 已生成 {len(spec.planning.tasks)} 个任务:")
        for task in spec.planning.tasks:
            click.echo(f"  - {task.task_id}: {task.title} ({task.type.value})")
        
        print_gate_result(gate_result)
        
        if gate_result.gate_t.is_passed:
            click.echo("\n提示: 使用 'canonical vv' 命令生成验证项")
        
        sys.exit(0 if gate_result.gate_t.is_passed else 1)
        
    except ValueError as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


@cli.command()
@click.argument('feature_id')
def vv(feature_id: str):
    """
    为 Feature 生成验证项
    
    FEATURE_ID: Feature 标识符 (如 F-2026-001)
    """
    try:
        orchestrator = Orchestrator()
        spec, gate_result = orchestrator.generate_vv(feature_id)
        
        click.echo(f"\n✓ 已生成 {len(spec.planning.vv)} 个验证项:")
        for vv_item in spec.planning.vv:
            click.echo(f"  - {vv_item.vv_id}: {vv_item.procedure[:50]}... ({vv_item.type.value})")
        
        print_gate_result(gate_result)
        
        if gate_result.overall_pass:
            click.echo("\n提示: 使用 'canonical review' 命令进行人工确认")
        
        sys.exit(0 if gate_result.gate_v.is_passed else 1)
        
    except ValueError as e:
        click.echo(f"\n✗ 错误: {str(e)}", err=True)
        sys.exit(2)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()
