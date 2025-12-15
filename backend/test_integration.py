#!/usr/bin/env python3
# encoding: utf-8
"""集成测试：测试理解→提取→生成的完整流程"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from domain.test_case.service import AIDemoTestCaseService


def test_full_workflow():
    """测试完整工作流"""
    print("=" * 60)
    print("集成测试：理解 → 提取 → 生成")
    print("=" * 60 + "\n")
    
    # 创建服务
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
    
    # 步骤1: 提取功能模块（带理解）
    print("步骤1: 提取功能模块（启用文档理解）...")
    try:
        modules, understanding = service.extract_function_modules_with_content(
            requirement_doc=test_doc,
            trace_id="integration_test_001",
            enable_understanding=True
        )
        
        print(f"✅ 提取成功!")
        print(f"   - 提取到 {len(modules)} 个功能模块")
        if understanding:
            print(f"   - 文档类型: {understanding.document_type}")
            print(f"   - 核心主题: {understanding.main_topic}")
            print(f"   - 质量评分: {understanding.quality_score:.2f}")
            print(f"   - 业务目标: {', '.join(understanding.business_goals[:3])}")
        
        # 显示提取的模块
        for i, module in enumerate(modules[:3], 1):  # 只显示前3个
            print(f"   - 模块{i}: {module.get('name', 'N/A')}")
        
        print()
        
        # 步骤2: 生成测试用例（使用理解结果）
        print("步骤2: 生成测试用例（使用理解结果）...")
        if len(modules) > 0:
            # 只使用前2个模块进行测试
            test_modules = modules[:2]
            result = service.generate_test_cases(
                requirement_doc=test_doc,
                confirmed_function_points=test_modules,
                trace_id="integration_test_002",
                enable_understanding=True,
                document_understanding=understanding.to_dict() if understanding else None,
                limit=2,
                max_workers=2
            )
            
            test_cases = result.get("test_cases", [])
            print(f"✅ 生成成功!")
            print(f"   - 生成 {len(test_cases)} 个测试用例")
            if result.get("document_understanding"):
                print(f"   - 理解结果已包含在响应中")
            
            # 显示前3个测试用例
            for i, case in enumerate(test_cases[:3], 1):
                print(f"   - 用例{i}: {case.get('case_name', 'N/A')}")
        
        print("\n" + "=" * 60)
        print("✅ 集成测试通过！")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_without_understanding():
    """测试不使用理解结果的情况（向后兼容）"""
    print("=" * 60)
    print("向后兼容测试：不使用理解结果")
    print("=" * 60 + "\n")
    
    service = AIDemoTestCaseService()
    
    test_doc = """# 简单功能测试

## 功能描述
这是一个简单的测试功能。

## 功能点
- 功能点1
- 功能点2
"""
    
    print("测试禁用理解功能...")
    try:
        modules, understanding = service.extract_function_modules_with_content(
            requirement_doc=test_doc,
            trace_id="compat_test_001",
            enable_understanding=False  # 禁用理解
        )
        
        print(f"✅ 提取成功（未使用理解）!")
        print(f"   - 提取到 {len(modules)} 个功能模块")
        print(f"   - 理解结果: {'存在' if understanding else 'None（符合预期）'}")
        
        print("\n✅ 向后兼容测试通过！\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 向后兼容测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("文档理解功能集成测试")
    print("=" * 60 + "\n")
    
    success = True
    
    # 测试1: 完整工作流
    success &= test_full_workflow()
    
    # 测试2: 向后兼容
    success &= test_without_understanding()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 所有集成测试通过！")
        print("=" * 60 + "\n")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ 部分测试失败")
        print("=" * 60 + "\n")
        sys.exit(1)

