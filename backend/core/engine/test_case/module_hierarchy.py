"""模块层级识别相关功能"""
from __future__ import annotations

from typing import Dict, List

from core.engine.base.config import ExtractionConfig


class ModuleHierarchyDetector:
    """模块层级检测器，负责识别主模块和子模块的关系"""

    @staticmethod
    def get_module_title_level(doc_lines: List[str], anchor_index: int) -> int:
        """
        检查模块在文档中的标题级别

        Args:
            doc_lines: 文档行列表
            anchor_index: 模块锚点位置

        Returns:
            2表示##（二级标题），3表示###（三级标题），0表示未找到
        """
        if anchor_index >= len(doc_lines):
            return 0
        line = doc_lines[anchor_index].strip()
        if line.startswith("## "):
            return 2
        elif line.startswith("### "):
            return 3
        return 0

    @staticmethod
    def detect_hierarchy(
        modules: List[Dict],
        module_positions: Dict[str, int],
        doc_lines: List[str],
    ) -> tuple[List[str], Dict[str, str]]:
        """
        识别主模块和子模块的关系

        Args:
            modules: 模块列表
            module_positions: 模块位置字典 {module_name: anchor_index}
            doc_lines: 文档行列表

        Returns:
            (main_modules, module_hierarchy)
            - main_modules: 主模块名称列表
            - module_hierarchy: {module_name: parent_module_name} 字典
        """
        # 按位置排序，确保处理顺序正确
        sorted_modules = sorted(modules, key=lambda m: module_positions.get(m.get("name", ""), 999999))

        main_modules: List[str] = []
        module_hierarchy: Dict[str, str] = {}

        # 更精确的子模块关键词：必须是独立的子功能单元
        # 注意：避免误判，如"睡眠类型详情区域"中的"详情"不应该触发子模块判断
        sub_module_keywords = ["半弹窗", "弹窗", "设置", "规则定义", "算法规则", "文案解释"]

        for i, module in enumerate(sorted_modules):
            module_name = module.get("name", "")
            if not module_name:
                continue

            anchor_index = module_positions[module_name]
            title_level = ModuleHierarchyDetector.get_module_title_level(doc_lines, anchor_index)

            # 如果模块是二级标题（##），一定是主模块
            if title_level == 2:
                main_modules.append(module_name)
                continue

            # 检查是否是子模块（更精确的匹配）
            # 必须是：1) 包含子模块关键词 2) 且是三级标题（###）
            is_sub_module = False
            if title_level == 3:
                # 检查是否包含子模块关键词（精确匹配，避免误判）
                for keyword in sub_module_keywords:
                    if keyword in module_name:
                        is_sub_module = True
                        break
                # 如果模块名称很短（<=配置的阈值）且包含关键词，更可能是子模块
                if not is_sub_module and len(module_name) <= ExtractionConfig.SHORT_MODULE_NAME_LENGTH:
                    short_keywords = ["弹窗", "设置", "规则", "定义", "解释"]
                    if any(kw in module_name for kw in short_keywords):
                        is_sub_module = True

            # 查找可能的主模块（位置在当前模块之前，且是二级标题）
            parent_module = None
            if is_sub_module:
                for j in range(i - 1, -1, -1):
                    prev_module = sorted_modules[j]
                    prev_name = prev_module.get("name", "")
                    if not prev_name:
                        continue
                    prev_anchor = module_positions[prev_name]
                    prev_title_level = ModuleHierarchyDetector.get_module_title_level(doc_lines, prev_anchor)

                    # 如果前一个模块是二级标题（##），且位置接近（相差不超过配置的最大距离）
                    if prev_title_level == 2 and anchor_index - prev_anchor <= ExtractionConfig.SUB_MODULE_MAX_DISTANCE:
                        parent_module = prev_name
                        break

            if parent_module:
                module_hierarchy[module_name] = parent_module
            else:
                # 没有父模块，是主模块
                main_modules.append(module_name)

        return main_modules, module_hierarchy
