# encoding: utf-8
"""模块层次关系构建相关功能"""
from __future__ import annotations

from typing import Any, Dict, List

from core.engine.base.config import ExtractionConfig
from core.logger import log
from .module_hierarchy import ModuleHierarchyDetector


class ModuleHierarchyBuilder:
    """模块层次关系构建器，负责识别主模块和子模块的关系"""

    def __init__(self, normalize_func):
        """
        初始化层次构建器

        Args:
            normalize_func: 文本标准化函数
        """
        self._normalize_identifier = normalize_func
        self._hierarchy_detector = ModuleHierarchyDetector()

    def build_hierarchy(
        self,
        modules: List[Dict[str, Any]],
        module_positions: Dict[str, int],
        doc_lines: List[str],
    ) -> tuple[List[str], Dict[str, str]]:
        """
        构建模块层次关系

        Args:
            modules: 模块列表（已按位置排序）
            module_positions: 模块位置字典 {module_name: anchor_index}
            doc_lines: 文档行列表

        Returns:
            (main_modules, module_hierarchy)
            - main_modules: 主模块列表
            - module_hierarchy: 模块层次关系字典 {module_name: parent_module_name}
        """
        main_modules: List[str] = []
        module_hierarchy: Dict[str, str] = {}

        # 使用配置化的子模块关键词（通用化，不包含特定业务逻辑）
        from core.engine.base.config import ExtractionConfig
        sub_module_keywords = ExtractionConfig.SUB_MODULE_KEYWORDS

        # 第一步：先识别所有主模块（二级标题或普通文本格式的主模块）
        # 这样可以确保在处理子模块时，主模块列表已经完整
        for module in modules:
            module_name = module.get("name", "")
            if not module_name:
                continue

            anchor_index = module_positions[module_name]
            title_level = self._hierarchy_detector.get_module_title_level(doc_lines, anchor_index)

            # 如果模块是二级标题（##），一定是主模块
            if title_level == 2:
                main_modules.append(module_name)
            # 如果模块不是标题（title_level == 0），且不包含子模块关键词，可能是主模块
            elif title_level == 0:
                # 检查是否包含子模块关键词
                has_sub_keyword = any(keyword in module_name for keyword in sub_module_keywords)
                # 如果不包含子模块关键词，且不是三级标题，可能是主模块
                if not has_sub_keyword:
                    main_modules.append(module_name)

        # 第二步：识别子模块并建立层次关系
        for i, module in enumerate(modules):
            module_name = module.get("name", "")
            if not module_name:
                continue

            # 如果已经是主模块，跳过
            if module_name in main_modules:
                continue

            anchor_index = module_positions[module_name]
            title_level = self._hierarchy_detector.get_module_title_level(doc_lines, anchor_index)

            # 检查是否是子模块（更精确的匹配）
            # 规则：
            # 1. 如果是三级标题（###），且包含子模块关键词，一定是子模块
            # 2. 如果不是标题（title_level == 0），但包含子模块关键词，且位置在前一个主模块之后，也可能是子模块
            is_sub_module = False
            if title_level == 3:
                # 检查是否包含子模块关键词（精确匹配，避免误判）
                for keyword in sub_module_keywords:
                    if keyword in module_name:
                        is_sub_module = True
                        break
                # 如果模块名称很短（<=配置的阈值）且包含关键词，更可能是子模块
                if not is_sub_module and len(module_name) <= ExtractionConfig.SHORT_MODULE_NAME_LENGTH:
                    short_keywords = ExtractionConfig.SHORT_SUB_MODULE_KEYWORDS
                    if any(kw in module_name for kw in short_keywords):
                        is_sub_module = True
            elif title_level == 0:
                # 不是Markdown标题，但可能仍然是子模块（普通文本格式的标题）
                # 检查是否包含子模块关键词，且位置在前一个主模块之后
                for keyword in sub_module_keywords:
                    if keyword in module_name:
                        # 检查文档中位置在当前模块之前的主模块
                        # 优先检查是否是Markdown二级标题（##），如果不是，则检查是否是已识别的主模块
                        found_main_module = False
                        
                        # 方法1：检查是否有Markdown二级标题（扩大搜索范围，因为可能是普通文本格式）
                        search_range = min(anchor_index, ExtractionConfig.SUB_MODULE_MAX_DISTANCE * 2)  # 扩大搜索范围
                        for line_idx in range(anchor_index - 1, max(0, anchor_index - search_range) - 1, -1):
                            line = doc_lines[line_idx].strip()
                            if line.startswith("## ") and not line.startswith("### "):
                                found_main_module = True
                                break
                        
                        # 方法2：如果没有找到Markdown标题，检查是否是已识别的主模块（可能是普通文本格式）
                        # 扩大搜索范围，找到最近的主模块
                        if not found_main_module:
                            best_main_distance = float('inf')
                            for prev_module_name in main_modules:
                                prev_anchor = module_positions.get(prev_module_name)
                                if prev_anchor is not None and prev_anchor < anchor_index:
                                    distance = anchor_index - prev_anchor
                                    # 扩大搜索范围，允许更远的距离
                                    if distance <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE * 2:
                                        if distance < best_main_distance:
                                            best_main_distance = distance
                                            found_main_module = True
                        
                        if found_main_module:
                            is_sub_module = True
                            break

            # 查找可能的主模块（位置在当前模块之前）
            parent_module = None
            if is_sub_module:
                # 优先从sorted_modules中查找（按位置排序，更准确）
                # 查找最近的主模块（可能是Markdown格式或普通文本格式）
                # 策略：找到最近的主模块，且位置在当前模块之前，且距离合理
                best_parent = None
                best_distance = float('inf')
                
                for j in range(i - 1, -1, -1):
                    prev_module = modules[j]
                    prev_name = prev_module.get("name", "")
                    if not prev_name:
                        continue
                    prev_anchor = module_positions[prev_name]
                    prev_title_level = self._hierarchy_detector.get_module_title_level(doc_lines, prev_anchor)
                    distance = anchor_index - prev_anchor

                    # 跳过子模块（已经有父模块的模块）
                    if prev_name in module_hierarchy:
                        continue

                    # 如果前一个模块是二级标题（##），且位置接近（相差不超过配置的最大距离）
                    if prev_title_level == 2 and distance <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE:
                        if distance < best_distance:
                            best_parent = prev_name
                            best_distance = distance
                    # 如果前一个模块已经是主模块（可能是普通文本格式），且位置接近
                    elif prev_name in main_modules and distance <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE:
                        if distance < best_distance:
                            best_parent = prev_name
                            best_distance = distance
                
                if best_parent:
                    parent_module = best_parent

                # 如果sorted_modules中没有找到，直接从文档中查找最近的主模块
                if not parent_module:
                    # 方法1：查找Markdown二级标题
                    for line_idx in range(anchor_index - 1, max(0, anchor_index - ExtractionConfig.SUB_MODULE_MAX_DISTANCE) - 1, -1):
                        line = doc_lines[line_idx].strip()
                        if line.startswith("## ") and not line.startswith("### "):
                            # 找到二级标题，检查是否是已识别的模块
                            heading_text = line.replace("##", "").strip()
                            normalized_heading = self._normalize_identifier(heading_text)
                            # 检查是否是已识别的模块
                            for other_module in modules:
                                other_name = other_module.get("name", "")
                                if not other_name:
                                    continue
                                normalized_other = self._normalize_identifier(other_name)
                                if normalized_heading == normalized_other:
                                    parent_module = other_name
                                    break
                            if parent_module:
                                break
                    
                    # 方法2：如果没有找到Markdown标题，检查已识别的主模块（可能是普通文本格式）
                    if not parent_module:
                        for main_name in main_modules:
                            main_anchor = module_positions.get(main_name)
                            if main_anchor is not None and main_anchor < anchor_index:
                                # 检查位置是否接近（在合理范围内）
                                if anchor_index - main_anchor <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE:
                                    parent_module = main_name
                                    break

            if parent_module:
                module_hierarchy[module_name] = parent_module
            else:
                # 没有父模块，是主模块
                main_modules.append(module_name)

        log.debug(
            "构建模块层次关系: 主模块 %s 个, 子模块 %s 个",
            len(main_modules), len(module_hierarchy)
        )

        return main_modules, module_hierarchy

