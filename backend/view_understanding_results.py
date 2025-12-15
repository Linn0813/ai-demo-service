#!/usr/bin/env python3
# encoding: utf-8
"""查看文档理解结果的工具脚本"""
import sys
import json
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))


def view_latest_understanding():
    """查看最新的理解结果"""
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
        return
    
    # 查找最新的理解结果文件
    understanding_files = list(debug_dir.glob("*document_understanding*.json"))
    if not understanding_files:
        print("❌ 未找到理解结果文件")
        return
    
    # 按修改时间排序
    understanding_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest_file = understanding_files[0]
    
    print(f"📄 最新理解结果文件: {latest_file.name}\n")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取理解结果（可能在understanding字段或payload.understanding字段）
    understanding = data.get("understanding") or data.get("payload", {}).get("understanding", {})
    if not understanding:
        print("⚠️  文件中未找到理解结果")
        print(f"\n文件内容:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        return
    
    print("="*60)
    print("文档理解结果")
    print("="*60)
    
    print(f"\n📋 基本信息:")
    print(f"  文档类型: {understanding.get('document_type', 'N/A')}")
    print(f"  核心主题: {understanding.get('main_topic', 'N/A')}")
    print(f"  质量评分: {understanding.get('quality_score', 0):.2f}")
    print(f"  复杂度: {understanding.get('estimated_complexity', 'N/A')}")
    print(f"  完整性: {understanding.get('completeness', 'N/A')}")
    print(f"  清晰度: {understanding.get('clarity', 'N/A')}")
    
    print(f"\n🎯 业务目标:")
    goals = understanding.get('business_goals', [])
    if goals:
        for i, goal in enumerate(goals[:5], 1):
            print(f"  {i}. {goal}")
    else:
        print("  (无)")
    
    print(f"\n🔑 关键概念:")
    concepts = understanding.get('key_concepts', [])
    if concepts:
        for i, concept in enumerate(concepts[:10], 1):
            print(f"  {i}. {concept}")
    else:
        print("  (无)")
    
    print(f"\n📚 关键术语:")
    terms = understanding.get('key_terms', [])
    if terms:
        for i, term in enumerate(terms[:10], 1):
            print(f"  {i}. {term}")
    else:
        print("  (无)")
    
    print(f"\n📐 业务规则:")
    rules = understanding.get('business_rules', [])
    if rules:
        for i, rule in enumerate(rules[:5], 1):
            print(f"  {i}. {rule}")
    else:
        print("  (无)")
    
    print(f"\n📊 文档结构:")
    structure = understanding.get('structure', {})
    if structure:
        print(f"  有章节结构: {structure.get('has_sections', False)}")
        print(f"  章节数量: {structure.get('section_count', 0)}")
        print(f"  层级: {structure.get('hierarchy_levels', [])}")
        main_sections = structure.get('main_sections', [])
        if main_sections:
            print(f"  主要章节:")
            for i, section in enumerate(main_sections[:5], 1):
                print(f"    {i}. {section}")
    
    print(f"\n📈 统计信息:")
    print(f"  总行数: {understanding.get('total_lines', 0)}")
    print(f"  章节数: {understanding.get('total_sections', 0)}")
    print(f"  Prompt版本: {understanding.get('prompt_version', 'N/A')}")
    print(f"  模型版本: {understanding.get('model_version', 'N/A')}")
    
    print(f"\n{'='*60}\n")


def view_all_understanding_files():
    """列出所有理解结果文件"""
    # 优先使用项目目录下的路径
    project_root = Path(__file__).parent.parent
    debug_dir = project_root / "data/debug/ai_runs"
    if not debug_dir.exists():
        # 尝试相对路径
        debug_dir = Path("data/debug/ai_runs")
        if not debug_dir.exists():
            print("❌ 调试目录不存在")
            return
    
    understanding_files = list(debug_dir.glob("*document_understanding*.json"))
    if not understanding_files:
        print("❌ 未找到理解结果文件")
        return
    
    # 按修改时间排序
    understanding_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"📁 找到 {len(understanding_files)} 个理解结果文件:\n")
    
    for i, file_path in enumerate(understanding_files[:10], 1):  # 只显示前10个
        mtime = file_path.stat().st_mtime
        from datetime import datetime
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # 读取文件获取质量评分
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                understanding = data.get("understanding", {})
                quality_score = understanding.get("quality_score", 0)
                doc_type = understanding.get("document_type", "N/A")
        except:
            quality_score = 0
            doc_type = "N/A"
        
        print(f"  {i}. {file_path.name}")
        print(f"     时间: {mtime_str}")
        print(f"     文档类型: {doc_type}")
        print(f"     质量评分: {quality_score:.2f}")
        print()


def view_file(file_name: str):
    """查看指定文件的理解结果"""
    # 优先使用项目目录下的路径
    project_root = Path(__file__).parent.parent
    possible_paths = [
        project_root / "data/debug/ai_runs",  # 项目目录下（优先）
        Path("data/debug/ai_runs"),  # 相对路径（备用）
    ]
    
    file_path = None
    for base_path in possible_paths:
        candidate = base_path / file_name
        if candidate.exists():
            file_path = candidate
            break
    
    if not file_path:
        print(f"❌ 文件不存在: {file_name}")
        print("尝试过的路径:")
        for base_path in possible_paths:
            print(f"  - {base_path / file_name}")
        return
    
    print(f"📄 文件路径: {file_path}\n")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取理解结果（可能在understanding字段或payload.understanding字段）
    understanding = data.get("understanding") or data.get("payload", {}).get("understanding", {})
    if not understanding:
        print("⚠️  文件中未找到理解结果")
        print(f"\n文件内容键: {list(data.keys())}")
        return
    
    print("="*60)
    print("文档理解结果")
    print("="*60)
    
    print(f"\n📋 基本信息:")
    print(f"  文档类型: {understanding.get('document_type', 'N/A')}")
    print(f"  核心主题: {understanding.get('main_topic', 'N/A')}")
    print(f"  质量评分: {understanding.get('quality_score', 0):.2f}")
    print(f"  复杂度: {understanding.get('estimated_complexity', 'N/A')}")
    print(f"  完整性: {understanding.get('completeness', 'N/A')}")
    print(f"  清晰度: {understanding.get('clarity', 'N/A')}")
    
    print(f"\n🎯 业务目标:")
    goals = understanding.get('business_goals', [])
    if goals:
        for i, goal in enumerate(goals[:5], 1):
            print(f"  {i}. {goal}")
    else:
        print("  (无)")
    
    print(f"\n🔑 关键概念:")
    concepts = understanding.get('key_concepts', [])
    if concepts:
        for i, concept in enumerate(concepts[:10], 1):
            print(f"  {i}. {concept}")
    else:
        print("  (无)")
    
    print(f"\n📚 关键术语:")
    terms = understanding.get('key_terms', [])
    if terms:
        for i, term in enumerate(terms[:10], 1):
            print(f"  {i}. {term}")
    else:
        print("  (无)")
    
    print(f"\n📐 业务规则:")
    rules = understanding.get('business_rules', [])
    if rules:
        for i, rule in enumerate(rules[:5], 1):
            print(f"  {i}. {rule}")
    else:
        print("  (无)")
    
    print(f"\n📊 文档结构:")
    structure = understanding.get('structure', {})
    if structure:
        print(f"  有章节结构: {structure.get('has_sections', False)}")
        print(f"  章节数量: {structure.get('section_count', 0)}")
        print(f"  层级: {structure.get('hierarchy_levels', [])}")
        main_sections = structure.get('main_sections', [])
        if main_sections:
            print(f"  主要章节:")
            for i, section in enumerate(main_sections[:5], 1):
                print(f"    {i}. {section}")
    
    print(f"\n📈 统计信息:")
    print(f"  总行数: {understanding.get('total_lines', 0)}")
    print(f"  章节数: {understanding.get('total_sections', 0)}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="查看文档理解结果")
    parser.add_argument("--list", action="store_true", help="列出所有理解结果文件")
    parser.add_argument("--file", type=str, help="查看指定文件")
    args = parser.parse_args()
    
    if args.list:
        view_all_understanding_files()
    elif args.file:
        view_file(args.file)
    else:
        view_latest_understanding()

