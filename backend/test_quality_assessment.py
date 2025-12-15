#!/usr/bin/env python3
# encoding: utf-8
"""文档理解功能质量评估脚本"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent))

from domain.test_case.service import AIDemoTestCaseService
from models.schemas import DocumentUnderstanding


def assess_understanding_quality(understanding: DocumentUnderstanding) -> Dict[str, Any]:
    """评估理解结果的质量"""
    scores = {}
    issues = []
    
    # 1. 文档类型识别
    if understanding.document_type and understanding.document_type != "未知":
        scores["document_type"] = 1.0
    else:
        scores["document_type"] = 0.0
        issues.append("文档类型未识别")
    
    # 2. 核心主题
    if understanding.main_topic and len(understanding.main_topic) > 0:
        scores["main_topic"] = 1.0
    else:
        scores["main_topic"] = 0.0
        issues.append("核心主题为空")
    
    # 3. 业务目标
    if len(understanding.business_goals) > 0:
        scores["business_goals"] = min(1.0, len(understanding.business_goals) / 3.0)
    else:
        scores["business_goals"] = 0.0
        issues.append("业务目标为空")
    
    # 4. 关键概念
    if len(understanding.key_concepts) > 0:
        scores["key_concepts"] = min(1.0, len(understanding.key_concepts) / 5.0)
    else:
        scores["key_concepts"] = 0.0
        issues.append("关键概念为空")
    
    # 5. 文档结构
    if understanding.structure.has_sections:
        scores["structure"] = min(1.0, understanding.structure.section_count / 10.0)
    else:
        scores["structure"] = 0.0
        issues.append("未识别到文档结构")
    
    # 6. 质量评分
    scores["quality_score"] = understanding.quality_score
    
    # 计算总体质量
    overall_score = sum(scores.values()) / len(scores)
    
    return {
        "scores": scores,
        "overall_score": overall_score,
        "issues": issues,
        "quality_level": "优秀" if overall_score >= 0.8 else "良好" if overall_score >= 0.6 else "一般" if overall_score >= 0.4 else "较差"
    }


def assess_extraction_quality(modules: List[Dict[str, Any]], understanding: DocumentUnderstanding) -> Dict[str, Any]:
    """评估模块提取的质量"""
    scores = {}
    issues = []
    
    # 1. 模块数量
    module_count = len(modules)
    if module_count > 0:
        scores["module_count"] = min(1.0, module_count / 5.0)
    else:
        scores["module_count"] = 0.0
        issues.append("未提取到模块")
    
    # 2. 模块与业务目标的相关性
    if understanding.business_goals:
        relevant_modules = 0
        for module in modules:
            module_name = module.get("name", "")
            # 简单检查：模块名是否包含业务目标关键词
            for goal in understanding.business_goals[:3]:
                if any(keyword in module_name for keyword in goal.split()[:2]):
                    relevant_modules += 1
                    break
        
        if module_count > 0:
            scores["relevance"] = relevant_modules / module_count
        else:
            scores["relevance"] = 0.0
    else:
        scores["relevance"] = 0.5  # 无法评估
        issues.append("无法评估相关性（业务目标为空）")
    
    # 3. 模块与关键概念的相关性
    if understanding.key_concepts:
        concept_covered = 0
        for concept in understanding.key_concepts[:5]:
            for module in modules:
                module_name = module.get("name", "")
                if concept in module_name or any(word in module_name for word in concept.split()):
                    concept_covered += 1
                    break
        
        scores["concept_coverage"] = min(1.0, concept_covered / len(understanding.key_concepts[:5]))
    else:
        scores["concept_coverage"] = 0.5
        issues.append("无法评估概念覆盖（关键概念为空）")
    
    # 计算总体质量
    overall_score = sum(scores.values()) / len(scores)
    
    return {
        "scores": scores,
        "overall_score": overall_score,
        "module_count": module_count,
        "issues": issues,
        "quality_level": "优秀" if overall_score >= 0.8 else "良好" if overall_score >= 0.6 else "一般" if overall_score >= 0.4 else "较差"
    }


def assess_generation_quality(test_cases: List[Dict[str, Any]], understanding: DocumentUnderstanding) -> Dict[str, Any]:
    """评估测试用例生成的质量"""
    scores = {}
    issues = []
    
    # 1. 用例数量
    case_count = len(test_cases)
    if case_count > 0:
        scores["case_count"] = min(1.0, case_count / 20.0)
    else:
        scores["case_count"] = 0.0
        issues.append("未生成测试用例")
    
    # 2. 用例完整性（检查必要字段）
    complete_cases = 0
    for case in test_cases:
        if case.get("case_name") and case.get("steps") and case.get("expected_result"):
            complete_cases += 1
    
    if case_count > 0:
        scores["completeness"] = complete_cases / case_count
    else:
        scores["completeness"] = 0.0
    
    # 3. 用例与业务目标的相关性
    if understanding.business_goals:
        relevant_cases = 0
        for case in test_cases:
            case_name = case.get("case_name", "")
            for goal in understanding.business_goals[:3]:
                if any(keyword in case_name for keyword in goal.split()[:2]):
                    relevant_cases += 1
                    break
        
        if case_count > 0:
            scores["relevance"] = relevant_cases / case_count
        else:
            scores["relevance"] = 0.0
    else:
        scores["relevance"] = 0.5
        issues.append("无法评估相关性（业务目标为空）")
    
    # 4. 步骤详细程度
    avg_steps = 0
    if case_count > 0:
        total_steps = sum(len(case.get("steps", [])) for case in test_cases)
        avg_steps = total_steps / case_count
        scores["step_detail"] = min(1.0, avg_steps / 5.0)
    else:
        scores["step_detail"] = 0.0
    
    # 计算总体质量
    overall_score = sum(scores.values()) / len(scores)
    
    return {
        "scores": scores,
        "overall_score": overall_score,
        "case_count": case_count,
        "avg_steps": avg_steps,
        "issues": issues,
        "quality_level": "优秀" if overall_score >= 0.8 else "良好" if overall_score >= 0.6 else "一般" if overall_score >= 0.4 else "较差"
    }


def print_assessment(title: str, assessment: Dict[str, Any]):
    """打印评估结果"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"总体评分: {assessment['overall_score']:.2f} ({assessment['quality_level']})")
    print(f"\n分项评分:")
    for key, value in assessment['scores'].items():
        print(f"  - {key}: {value:.2f}")
    
    if assessment.get('module_count') is not None:
        print(f"\n模块数量: {assessment['module_count']}")
    if assessment.get('case_count') is not None:
        print(f"用例数量: {assessment['case_count']}")
        print(f"平均步骤数: {assessment.get('avg_steps', 0):.1f}")
    
    if assessment['issues']:
        print(f"\n⚠️  问题:")
        for issue in assessment['issues']:
            print(f"  - {issue}")
    else:
        print(f"\n✅ 未发现问题")


def test_full_workflow_with_assessment():
    """测试完整流程并评估质量"""
    print("\n" + "="*60)
    print("文档理解功能质量评估")
    print("="*60 + "\n")
    
    service = AIDemoTestCaseService()
    
    # 测试文档
    test_doc = """# 用户登录功能

## 功能描述
用户可以通过手机号和密码登录系统。

## 业务目标
1. 提供安全的用户认证
2. 支持多种登录方式
3. 提升用户体验

## 关键概念
- 用户认证
- 密码加密
- 会话管理
- 安全验证

## 业务规则
1. 密码长度至少6位
2. 登录失败3次后锁定账户
3. 会话超时时间为30分钟

## 功能模块

### 登录页面
- 手机号输入框
- 密码输入框
- 登录按钮
- 忘记密码链接

### 验证逻辑
- 手机号格式验证
- 密码强度验证
- 账户状态检查
"""
    
    print(f"测试文档长度: {len(test_doc)} 字符\n")
    
    # 步骤1: 文档理解
    print("步骤1: 执行文档理解...")
    try:
        modules, understanding = service.extract_function_modules_with_content(
            requirement_doc=test_doc,
            trace_id="quality_assessment_001",
            enable_understanding=True
        )
        
        if understanding:
            understanding_assessment = assess_understanding_quality(understanding)
            print_assessment("文档理解质量评估", understanding_assessment)
            
            # 打印理解结果详情
            print(f"\n理解结果详情:")
            print(f"  - 文档类型: {understanding.document_type}")
            print(f"  - 核心主题: {understanding.main_topic}")
            print(f"  - 业务目标: {', '.join(understanding.business_goals[:3])}")
            print(f"  - 关键概念: {', '.join(understanding.key_concepts[:5])}")
            print(f"  - 章节数量: {understanding.structure.section_count}")
            print(f"  - 层级: {understanding.structure.hierarchy_levels}")
        else:
            print("⚠️  未获取到理解结果")
            understanding = None
        
        # 步骤2: 模块提取质量评估
        print(f"\n步骤2: 评估模块提取质量...")
        if understanding:
            extraction_assessment = assess_extraction_quality(modules, understanding)
            print_assessment("模块提取质量评估", extraction_assessment)
            
            print(f"\n提取的模块:")
            for i, module in enumerate(modules[:5], 1):
                print(f"  {i}. {module.get('name', 'N/A')}")
        else:
            print("⚠️  无法评估（缺少理解结果）")
        
        # 步骤3: 测试用例生成质量评估
        if len(modules) > 0:
            print(f"\n步骤3: 生成测试用例并评估质量...")
            test_modules = modules[:2]  # 只测试前2个模块
            
            result = service.generate_test_cases(
                requirement_doc=test_doc,
                confirmed_function_points=test_modules,
                trace_id="quality_assessment_002",
                enable_understanding=True,
                document_understanding=understanding.to_dict() if understanding else None,
                limit=2,
                max_workers=2
            )
            
            test_cases = result.get("test_cases", [])
            
            if understanding:
                generation_assessment = assess_generation_quality(test_cases, understanding)
                print_assessment("测试用例生成质量评估", generation_assessment)
                
                print(f"\n生成的测试用例示例（前3个）:")
                for i, case in enumerate(test_cases[:3], 1):
                    print(f"  {i}. {case.get('case_name', 'N/A')}")
                    print(f"     步骤数: {len(case.get('steps', []))}")
            else:
                print("⚠️  无法评估（缺少理解结果）")
        
        # 总结
        print(f"\n{'='*60}")
        print("质量评估总结")
        print(f"{'='*60}")
        if understanding:
            print(f"✅ 文档理解: {understanding_assessment['quality_level']} ({understanding_assessment['overall_score']:.2f})")
        if understanding and len(modules) > 0:
            print(f"✅ 模块提取: {extraction_assessment['quality_level']} ({extraction_assessment['overall_score']:.2f})")
        if understanding and len(test_cases) > 0:
            print(f"✅ 用例生成: {generation_assessment['quality_level']} ({generation_assessment['overall_score']:.2f})")
        
        print(f"\n{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ 评估失败: {e}")
        import traceback
        traceback.print_exc()


def compare_with_without_understanding():
    """对比使用理解和不使用理解的效果"""
    print("\n" + "="*60)
    print("对比测试：使用理解 vs 不使用理解")
    print("="*60 + "\n")
    
    service = AIDemoTestCaseService()
    
    test_doc = """# 订单管理功能

## 业务目标
1. 支持订单创建和查询
2. 订单状态管理
3. 订单支付处理

## 功能模块
### 订单列表
- 订单查询
- 订单筛选
- 订单排序

### 订单详情
- 订单信息展示
- 订单操作
"""
    
    print("测试1: 不使用文档理解...")
    modules1, _ = service.extract_function_modules_with_content(
        requirement_doc=test_doc,
        trace_id="compare_001",
        enable_understanding=False
    )
    print(f"  提取到 {len(modules1)} 个模块")
    
    print("\n测试2: 使用文档理解...")
    modules2, understanding = service.extract_function_modules_with_content(
        requirement_doc=test_doc,
        trace_id="compare_002",
        enable_understanding=True
    )
    print(f"  提取到 {len(modules2)} 个模块")
    
    if understanding:
        print(f"  理解结果质量评分: {understanding.quality_score:.2f}")
    
    print(f"\n对比结果:")
    print(f"  模块数量差异: {len(modules2) - len(modules1)}")
    print(f"  模块名称对比:")
    print(f"    不使用理解: {[m.get('name') for m in modules1]}")
    print(f"    使用理解: {[m.get('name') for m in modules2]}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="文档理解功能质量评估")
    parser.add_argument("--compare", action="store_true", help="对比使用理解和不使用理解的效果")
    args = parser.parse_args()
    
    if args.compare:
        compare_with_without_understanding()
    else:
        test_full_workflow_with_assessment()

