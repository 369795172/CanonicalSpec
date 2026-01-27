#!/usr/bin/env python3
"""
测试 Requirement Genome 功能
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_refine():
    """测试第一轮 refine"""
    print("=" * 60)
    print("测试第一轮 refine")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/refine",
        json={
            "input": "我想做一个用户登录功能，需要用户名和密码",
            "context": {
                "conversation_history": [],
                "round": 0,
                "additional_context": {}
            }
        }
    )
    
    assert response.status_code == 200, f"API 返回错误: {response.status_code}"
    data = response.json()
    
    print(f"✅ Round: {data.get('round')}")
    print(f"✅ Understanding Summary: {data.get('understanding_summary', '')[:100]}...")
    print(f"✅ Questions: {len(data.get('questions', []))}")
    print(f"✅ Genome: {'存在' if data.get('genome') else '不存在'}")
    print(f"✅ Changes: {'存在' if data.get('changes') else '不存在'}")
    
    if data.get('genome'):
        genome = data['genome']
        print(f"   - Genome Version: {genome.get('genome_version')}")
        print(f"   - Assumptions: {len(genome.get('assumptions', []))}")
        print(f"   - Constraints: {len(genome.get('constraints', []))}")
        print(f"   - User Stories: {len(genome.get('user_stories', []))}")
        print(f"   - Decisions: {len(genome.get('decisions', []))}")
        print(f"   - History: {len(genome.get('history', []))}")
    
    if data.get('changes'):
        changes = data['changes']
        print(f"   - New Assumptions: {len(changes.get('new_assumptions', []))}")
        print(f"   - New Constraints: {len(changes.get('new_constraints', []))}")
        print(f"   - Decisions Made: {len(changes.get('decisions_made', []))}")
    
    return data

def test_feedback(context_data, feedback_text):
    """测试第二轮 refine feedback"""
    print("\n" + "=" * 60)
    print(f"测试第二轮 refine feedback: {feedback_text[:50]}...")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/refine/feedback",
        json={
            "feedback": feedback_text,
            "context": context_data
        }
    )
    
    assert response.status_code == 200, f"API 返回错误: {response.status_code}"
    data = response.json()
    
    print(f"✅ Round: {data.get('round')}")
    print(f"✅ Understanding Summary: {data.get('understanding_summary', '')[:100]}...")
    print(f"✅ Questions: {len(data.get('questions', []))}")
    print(f"✅ Genome: {'存在' if data.get('genome') else '不存在'}")
    print(f"✅ Changes: {'存在' if data.get('changes') else '不存在'}")
    
    if data.get('genome'):
        genome = data['genome']
        print(f"   - Genome Version: {genome.get('genome_version')}")
        print(f"   - Assumptions: {len(genome.get('assumptions', []))}")
        print(f"   - Constraints: {len(genome.get('constraints', []))}")
        print(f"   - User Stories: {len(genome.get('user_stories', []))}")
        print(f"   - Decisions: {len(genome.get('decisions', []))}")
        print(f"   - History: {len(genome.get('history', []))}")
        
        # 检查版本是否递增
        prev_version = context_data.get('additional_context', {}).get('genome', {}).get('genome_version')
        if prev_version:
            print(f"   - 版本递增: {prev_version} -> {genome.get('genome_version')}")
    
    if data.get('changes'):
        changes = data['changes']
        print(f"   - New Assumptions: {changes.get('new_assumptions', [])}")
        print(f"   - New Constraints: {changes.get('new_constraints', [])}")
        print(f"   - Decisions Made: {changes.get('decisions_made', [])}")
        print(f"   - Updated Fields: {changes.get('updated_fields', [])}")
    
    return data

if __name__ == "__main__":
    try:
        # 测试第一轮
        result1 = test_refine()
        
        # 准备第二轮 context
        context2 = {
            "conversation_history": [
                {"role": "user", "content": "我想做一个用户登录功能，需要用户名和密码"},
                {"role": "assistant", "content": json.dumps(result1)}
            ],
            "round": result1.get('round', 1),
            "additional_context": {
                "genome": result1.get('genome', {})
            }
        }
        
        # 测试第二轮
        result2 = test_feedback(context2, "是的，需要密码加密处理，使用哈希加密。不需要用户注册功能。")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
