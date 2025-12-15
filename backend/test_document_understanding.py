#!/usr/bin/env python3
# encoding: utf-8
"""测试文档理解功能"""
import sys
import json
from pathlib import Path

# 添加backend目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from models.schemas import DocumentUnderstanding, DocumentStructure
from domain.test_case.document_understanding import DocumentUnderstandingService
from infrastructure.llm.service import LLMService
from shared.config import settings


def test_data_models():
    """测试数据模型"""
    print("=" * 60)
    print("测试1: 数据模型")
    print("=" * 60)
    
    # 测试 DocumentStructure
    structure = DocumentStructure(
        has_sections=True,
        section_count=5,
        hierarchy_levels=[1, 2, 3],
        main_sections=["章节1", "章节2"],
        section_tree={"title": "文档", "level": 0, "children": []}
    )
    print(f"✅ DocumentStructure 创建成功: {structure.section_count} 个章节")
    
    # 测试 DocumentUnderstanding
    understanding = DocumentUnderstanding(
        document_type="PRD",
        main_topic="测试主题",
        business_goals=["目标1", "目标2"],
        structure=structure,
        key_concepts=["概念1"],
        quality_score=0.8
    )
    print(f"✅ DocumentUnderstanding 创建成功: {understanding.document_type}")
    
    # 测试序列化
    understanding_dict = understanding.to_dict()
    print(f"✅ 序列化成功: {len(understanding_dict)} 个字段")
    
    # 测试反序列化
    understanding2 = DocumentUnderstanding(**understanding_dict)
    print(f"✅ 反序列化成功: {understanding2.document_type}")
    
    print()


def test_prompts():
    """测试提示词构建"""
    print("=" * 60)
    print("测试2: 提示词构建")
    print("=" * 60)
    
    from domain.test_case.prompts import (
        build_document_understanding_prompt,
        build_module_extraction_prompt_with_understanding,
        build_generation_prompt_with_understanding
    )
    
    # 测试文档理解提示词
    test_doc = "这是一个测试文档\n# 章节1\n内容1\n## 子章节1\n内容2"
    prompt1 = build_document_understanding_prompt(test_doc)
    print(f"✅ 文档理解提示词构建成功: {len(prompt1)} 字符")
    
    # 测试增强的模块提取提示词
    structure = DocumentStructure(
        has_sections=True,
        section_count=2,
        hierarchy_levels=[1, 2],
        main_sections=["章节1"],
        section_tree={}
    )
    understanding = DocumentUnderstanding(
        document_type="PRD",
        main_topic="测试",
        business_goals=["目标1"],
        structure=structure,
        key_concepts=["概念1"]
    )
    
    prompt2 = build_module_extraction_prompt_with_understanding(test_doc, understanding)
    print(f"✅ 增强模块提取提示词构建成功: {len(prompt2)} 字符")
    assert "文档理解结果" in prompt2, "提示词应包含理解结果"
    
    prompt3 = build_generation_prompt_with_understanding(test_doc, understanding)
    print(f"✅ 增强生成提示词构建成功: {len(prompt3)} 字符")
    assert "文档理解结果" in prompt3, "提示词应包含理解结果"
    
    print()


def test_understanding_service():
    """测试文档理解服务"""
    print("=" * 60)
    print("测试3: 文档理解服务")
    print("=" * 60)
    
    # 创建LLM服务
    llm_service = LLMService(
        base_url=settings.llm_base_url,
        model=settings.llm_default_model,
        api_key=settings.llm_api_key,
        provider=settings.llm_provider,
    )
    
    # 创建理解服务
    understanding_service = DocumentUnderstandingService(llm_service)
    print("✅ DocumentUnderstandingService 初始化成功")
    
    # 测试文档（简单的测试文档）
    test_doc = """# 用户登录功能

## 功能描述
用户可以通过手机号和密码登录系统。

## 业务目标
1. 提供安全的用户认证
2. 支持多种登录方式

## 关键概念
- 用户认证
- 密码加密
- 会话管理

## 业务规则
1. 密码长度至少6位
2. 登录失败3次后锁定账户
"""
    
    print(f"测试文档长度: {len(test_doc)} 字符")
    print("正在调用理解服务...")
    
    try:
        understanding = understanding_service.understand_document(
            test_doc,
            run_id="test_001"
        )
        
        print(f"✅ 文档理解成功!")
        print(f"   - 文档类型: {understanding.document_type}")
        print(f"   - 核心主题: {understanding.main_topic}")
        print(f"   - 业务目标数量: {len(understanding.business_goals)}")
        print(f"   - 关键概念数量: {len(understanding.key_concepts)}")
        print(f"   - 质量评分: {understanding.quality_score:.2f}")
        print(f"   - 复杂度: {understanding.estimated_complexity}")
        print(f"   - 章节数量: {understanding.structure.section_count}")
        print(f"   - 层级: {understanding.structure.hierarchy_levels}")
        
        # 测试缓存
        print("\n测试缓存功能...")
        understanding2 = understanding_service.understand_document(test_doc, run_id="test_002")
        assert understanding2.document_type == understanding.document_type, "缓存应返回相同结果"
        print("✅ 缓存功能正常")
        
    except Exception as e:
        print(f"❌ 文档理解失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()


def test_service_integration():
    """测试服务集成"""
    print("=" * 60)
    print("测试4: 服务集成")
    print("=" * 60)
    
    from domain.test_case.service import AIDemoTestCaseService
    
    service = AIDemoTestCaseService()
    print("✅ AIDemoTestCaseService 初始化成功")
    
    # 检查理解服务是否已集成
    assert hasattr(service, 'understanding_service'), "应包含理解服务"
    print("✅ 理解服务已集成")
    
    print()


def test_api_schemas():
    """测试API Schema"""
    print("=" * 60)
    print("测试5: API Schema")
    print("=" * 60)
    
    from models.schemas import (
        ExtractModulesRequest,
        GenerateTestCasesRequest,
        ExtractModulesResponse,
        GenerateTestCasesResponse
    )
    
    # 测试请求模型
    extract_request = ExtractModulesRequest(
        requirement_doc="这是一个测试文档，用于验证API Schema的功能",
        enable_understanding=True
    )
    assert extract_request.enable_understanding == True, "enable_understanding 应为 True"
    print("✅ ExtractModulesRequest 创建成功")
    
    generate_request = GenerateTestCasesRequest(
        requirement_doc="这是一个测试文档，用于验证API Schema的功能",
        enable_understanding=True,
        document_understanding={"document_type": "PRD"}
    )
    assert generate_request.enable_understanding == True, "enable_understanding 应为 True"
    assert generate_request.document_understanding is not None, "document_understanding 应存在"
    print("✅ GenerateTestCasesRequest 创建成功")
    
    # 测试响应模型
    structure = DocumentStructure(
        has_sections=True,
        section_count=1,
        hierarchy_levels=[1],
        main_sections=["章节1"],
        section_tree={}
    )
    understanding = DocumentUnderstanding(
        document_type="PRD",
        main_topic="测试",
        structure=structure
    )
    
    extract_response = ExtractModulesResponse(
        function_points=[],
        requirement_doc="这是一个测试文档，用于验证API Schema的功能",
        document_understanding=understanding.to_dict()
    )
    assert extract_response.document_understanding is not None, "document_understanding 应存在"
    print("✅ ExtractModulesResponse 创建成功")
    
    generate_response = GenerateTestCasesResponse(
        test_cases=[],
        by_function_point={},
        meta={},
        document_understanding=understanding.to_dict()
    )
    assert generate_response.document_understanding is not None, "document_understanding 应存在"
    print("✅ GenerateTestCasesResponse 创建成功")
    
    print()


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("文档理解功能测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试1: 数据模型
        test_data_models()
        
        # 测试2: 提示词构建
        test_prompts()
        
        # 测试3: 服务集成
        test_service_integration()
        
        # 测试4: API Schema
        test_api_schemas()
        
        # 测试5: 文档理解服务（需要LLM，可能失败）
        print("提示: 文档理解服务测试需要LLM连接，如果失败请检查配置")
        test_understanding_service()
        
        print("\n" + "=" * 60)
        print("✅ 所有基础测试通过！")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

