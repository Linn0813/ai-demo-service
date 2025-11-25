# encoding: utf-8
"""模块验证和过滤相关功能"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core.logger import log


class ModuleValidator:
    """模块验证器，负责验证和过滤模块"""

    # 明显来自prompt而非需求文档的词汇
    PROMPT_KEYWORDS = ["功能模块定义", "提取要求", "输出格式", "重要要求", "关键词提取"]

    # 通用词列表，这些词不应该单独作为验证依据
    GENERIC_WORDS = {"模块", "功能", "系统", "定义", "要求", "格式", "管理器", "管理"}

    # 明显是子功能的模式
    SUB_FUNCTION_PATTERNS = [
        r"^(存在|无|有|没有).*数据$",  # "存在有效数据"、"无有效数据"等
        r"^(存在|无|有|没有).*$",  # "存在数据"、"无工作日数据"等（但排除主模块）
    ]

    # 主模块关键词（这些模块不应该被过滤）
    MAIN_MODULE_KEYWORDS = ["判断条件", "状态", "详情", "设置", "弹窗", "卡片", "信息"]

    @staticmethod
    def validate_modules(
        modules: List[Dict[str, Any]],
        requirement_doc: str,
    ) -> List[Dict[str, Any]]:
        """
        验证模块是否在需求文档中存在

        Args:
            modules: 待验证的模块列表
            requirement_doc: 需求文档内容

        Returns:
            验证通过的模块列表
        """
        validated_modules = []

        for module in modules:
            module_name = module.get("name", "").strip()
            if not module_name:
                continue

            # 如果模块名称明显来自prompt，直接过滤
            if any(pk in module_name for pk in ModuleValidator.PROMPT_KEYWORDS):
                log.warning(
                    "过滤掉来自prompt的模块: '%s' (不是需求文档中的内容)",
                    module_name
                )
                continue

            # 检查模块名称或其关键词是否在文档中出现
            name_in_doc = module_name in requirement_doc

            # 提取模块名称中的关键词（去除"模块"等通用词）
            name_parts = re.split(r'[模块功能系统定义要求格式管理]', module_name)
            name_keywords = [
                kw.strip() for kw in name_parts
                if kw and len(kw.strip()) >= 2 and kw.strip() not in ModuleValidator.GENERIC_WORDS
            ]

            # 如果模块名称包含多个词，要求至少有一个完整的、非通用的词组在文档中
            name_keywords_in_doc = any(
                kw in requirement_doc and len(kw) >= 3 and kw not in ModuleValidator.GENERIC_WORDS
                for kw in name_keywords
            ) if name_keywords else False

            keywords_in_doc = any(
                kw in requirement_doc and len(kw) >= 3
                for kw in module.get("keywords", [])
                if kw and len(kw) >= 2
            )

            exact_phrases_in_doc = any(
                phrase in requirement_doc
                for phrase in module.get("exact_phrases", [])
                if phrase and len(phrase) >= 3
            )

            # 验证逻辑：至少满足以下条件之一
            is_valid = (
                name_in_doc or
                (name_keywords_in_doc and name_keywords) or
                keywords_in_doc or
                exact_phrases_in_doc
            )

            if is_valid:
                validated_modules.append(module)
            else:
                log.warning(
                    "过滤掉臆造的模块: '%s' (在需求文档中未找到相关提及)",
                    module_name
                )

        if len(validated_modules) < len(modules):
            log.info(
                "验证后保留 %s/%s 个模块（过滤掉 %s 个臆造模块）",
                len(validated_modules),
                len(modules),
                len(modules) - len(validated_modules)
            )

        return validated_modules

    @staticmethod
    def filter_sub_function_modules(
        modules: List[Dict[str, Any]],
        requirement_doc: str,
    ) -> List[Dict[str, Any]]:
        """
        基于规则过滤掉明显是子功能的模块

        规则：
        1. 状态类模块（如"存在有效数据"、"无有效数据"）应该归属于"判断条件"或"状态"模块
        2. 数据类模块（如"存在数据"、"无工作日数据"）应该归属于相关模块
        3. 如果模块名称是其他模块的子集，且位置接近，应该合并

        Args:
            modules: 待过滤的模块列表
            requirement_doc: 需求文档内容（用于上下文判断）

        Returns:
            过滤后的模块列表
        """
        if not modules:
            return []

        filtered = []
        for module in modules:
            module_name = module.get("name", "").strip()
            if not module_name:
                continue

            # 检查是否包含主模块关键词（如果是"判断条件"、"状态"等，不应该过滤）
            if any(keyword in module_name for keyword in ModuleValidator.MAIN_MODULE_KEYWORDS):
                filtered.append(module)
                continue

            # 检查是否是明显子功能
            is_sub_function = False
            for pattern in ModuleValidator.SUB_FUNCTION_PATTERNS:
                if re.match(pattern, module_name):
                    is_sub_function = True
                    log.info(
                        "过滤掉子功能模块: '%s' (匹配模式: %s)",
                        module_name, pattern
                    )
                    break

            if not is_sub_function:
                filtered.append(module)

        if len(filtered) < len(modules):
            log.info(
                "基于规则过滤: 保留 %s/%s 个模块（过滤掉 %s 个子功能模块）",
                len(filtered), len(modules), len(modules) - len(filtered)
            )

        return filtered

