#!/usr/bin/env python3
# encoding: utf-8
"""查看测试用例生成结果的工具脚本"""
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


def find_latest_test_case_file():
    """查找最新的测试用例生成结果文件"""
    # 优先使用项目目录下的路径
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root / "data/debug/ai_runs",  # 项目目录下（优先）
        Path("data/debug/ai_runs"),  # 相对路径（备用）
    ]
    
    debug_dir = None
    for path in possible_paths:
        if path.exists():
            debug_dir = path
            break
    
    if not debug_dir:
        print("❌ 调试目录不存在，尝试过的路径:")
        for path in possible_paths:
            print(f"  - {path}")
        return None
    
    # 查找测试用例生成结果文件
    test_case_files = list(debug_dir.glob("*generate_test_cases*.json"))
    if not test_case_files:
        print("❌ 未找到测试用例生成结果文件")
        return None
    
    # 按修改时间排序
    test_case_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return test_case_files[0]


def assess_test_case_quality(test_case: Dict[str, Any], index: int) -> Dict[str, Any]:
    """评估单个测试用例的质量"""
    issues = []
    score = 1.0
    
    # 检查必填字段
    if not test_case.get("case_name") or not str(test_case.get("case_name", "")).strip():
        issues.append("用例名称为空")
        score -= 0.3
    
    if not test_case.get("module_name") or not str(test_case.get("module_name", "")).strip():
        issues.append("功能模块为空")
        score -= 0.2
    
    # 检查步骤
    steps = test_case.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    if len(steps) < 2:
        issues.append(f"步骤数不足（{len(steps)}步，建议至少2步）")
        score -= 0.2
    elif len(steps) < 3:
        issues.append(f"步骤数较少（{len(steps)}步，建议至少3步）")
        score -= 0.1
    
    # 检查预期结果
    expected_result = str(test_case.get("expected_result", "")).strip()
    if not expected_result:
        issues.append("预期结果为空")
        score -= 0.3
    else:
        # 检查是否使用了通用预期结果
        generic_patterns = ["正确显示", "正常显示", "验证通过", "符合预期", "满足要求", "点击关闭直接消失"]
        if any(pattern in expected_result for pattern in generic_patterns):
            issues.append("使用了通用预期结果，建议使用具体描述")
            score -= 0.1
        # 检查预期结果长度
        if len(expected_result) < 5:
            issues.append("预期结果过短，可能不够具体")
            score -= 0.1
    
    # 检查前置条件（可选）
    preconditions = str(test_case.get("preconditions", "")).strip()
    if preconditions and len(preconditions) < 3:
        issues.append("前置条件过短")
        score -= 0.05
    
    # 检查步骤质量
    for step_index, step in enumerate(steps, 1):
        step_str = str(step).strip()
        if len(step_str) < 5:
            issues.append(f"步骤{step_index}描述过短或不清晰")
            score -= 0.05
        # 检查是否包含禁止的操作
        banned_actions = ["登录后台", "查看数据库", "手动投放", "后台操作"]
        if any(action in step_str for action in banned_actions):
            issues.append(f"步骤{step_index}包含不可执行的操作")
            score -= 0.1
    
    score = max(0, min(1, score))  # 限制在0-1之间
    
    return {"score": score, "issues": issues}


def view_test_case_results(file_path: Optional[Path] = None):
    """查看测试用例生成结果"""
    if file_path is None:
        file_path = find_latest_test_case_file()
        if file_path is None:
            return
    
    print(f"📄 文件路径: {file_path}\n")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取测试用例数据
    payload = data.get("payload", {})
    test_cases = payload.get("test_cases", [])
    by_function_point = payload.get("by_function_point", {})
    meta = payload.get("meta", {})
    
    if not test_cases:
        print("⚠️  文件中未找到测试用例数据")
        print(f"\n文件内容键: {list(payload.keys())}")
        return
    
    print("="*80)
    print("测试用例生成结果")
    print("="*80)
    
    print(f"\n📊 统计信息:")
    print(f"  功能点总数: {meta.get('total_function_points', 0)}")
    print(f"  已处理功能点: {meta.get('processed_function_points', 0)}")
    print(f"  生成用例数: {len(test_cases)}")
    print(f"  警告数: {meta.get('total_warnings', 0)}")
    
    # 质量评估
    quality_results = [assess_test_case_quality(tc, i+1) for i, tc in enumerate(test_cases)]
    average_score = sum(q["score"] for q in quality_results) / len(quality_results) if quality_results else 0
    problem_count = sum(1 for q in quality_results if q["score"] < 0.8 or len(q["issues"]) > 0)
    
    print(f"\n📈 质量评估:")
    print(f"  平均质量评分: {average_score:.2%}")
    print(f"  有质量问题的用例: {problem_count} / {len(test_cases)}")
    
    # 显示用例列表
    print(f"\n📋 测试用例列表（共{len(test_cases)}个）:")
    print("-"*80)
    
    for index, test_case in enumerate(test_cases, 1):
        quality = quality_results[index - 1]
        print(f"\n【用例 {index}】")
        print(f"  功能模块: {test_case.get('module_name', 'N/A')}")
        if test_case.get('sub_module'):
            print(f"  子功能点: {test_case.get('sub_module')}")
        print(f"  用例名称: {test_case.get('case_name', 'N/A')}")
        print(f"  前置条件: {test_case.get('preconditions', '无')}")
        print(f"  优先级: {test_case.get('priority', '未设置')}")
        print(f"  步骤数: {len(test_case.get('steps', []))}")
        print(f"  测试步骤:")
        for step_idx, step in enumerate(test_case.get('steps', []), 1):
            print(f"    {step_idx}. {step}")
        print(f"  预期结果: {test_case.get('expected_result', 'N/A')}")
        print(f"  质量评分: {quality['score']:.2%}")
        if quality['issues']:
            print(f"  质量问题: {'; '.join(quality['issues'])}")
    
    print("\n" + "="*80)
    print(f"\n💡 提示:")
    print(f"  - 文件位置: {file_path}")
    print(f"  - 可以使用以下命令查看完整JSON: cat {file_path} | jq '.payload.test_cases'")
    print(f"  - 质量评分说明: 1.0=优秀, 0.8-0.9=良好, 0.7-0.8=一般, <0.7=需要改进")


def list_test_case_files():
    """列出所有测试用例生成结果文件"""
    # 优先使用项目目录下的路径
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root / "data/debug/ai_runs",  # 项目目录下（优先）
        Path("data/debug/ai_runs"),  # 相对路径（备用）
    ]
    
    debug_dir = None
    for path in possible_paths:
        if path.exists():
            debug_dir = path
            break
    
    if not debug_dir:
        print("❌ 调试目录不存在")
        return
    
    test_case_files = list(debug_dir.glob("*generate_test_cases*.json"))
    if not test_case_files:
        print("❌ 未找到测试用例生成结果文件")
        return
    
    test_case_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"📁 找到 {len(test_case_files)} 个测试用例生成结果文件:\n")
    
    for i, file_path in enumerate(test_case_files[:10], 1):  # 只显示前10个
        mtime = file_path.stat().st_mtime
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # 读取文件获取用例数量
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                payload = data.get("payload", {})
                test_cases = payload.get("test_cases", [])
                case_count = len(test_cases) if isinstance(test_cases, list) else 0
        except:
            case_count = 0
        
        print(f"  {i}. {file_path.name}")
        print(f"     时间: {mtime_str}")
        print(f"     用例数: {case_count}")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="查看测试用例生成结果")
    parser.add_argument("--list", action="store_true", help="列出所有测试用例生成结果文件")
    parser.add_argument("--file", type=str, help="查看指定文件")
    args = parser.parse_args()
    
    if args.list:
        list_test_case_files()
    elif args.file:
        # 尝试多个可能的路径
        project_root = Path(__file__).parent.parent
        possible_paths = [
            project_root / "data/debug/ai_runs" / args.file,  # 项目目录下（优先）
            Path("data/debug/ai_runs") / args.file,  # 相对路径（备用）
        ]
        file_path = None
        for path in possible_paths:
            if path.exists():
                file_path = path
                break
        if file_path:
            view_test_case_results(file_path)
        else:
            print(f"❌ 文件不存在: {args.file}")
    else:
        view_test_case_results()

