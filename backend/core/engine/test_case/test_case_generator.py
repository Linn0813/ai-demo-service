"""测试用例生成器"""

import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from core.engine.base.config import RE_JSON_CASE, ExtractionConfig
from core.engine.base.debug_recorder import record_ai_debug
from .extractors import FunctionModuleExtractor, _parse_json_with_fallback
from core.engine.base.llm_service import LLMService
from .prompts import build_generation_prompt, build_function_point_extraction_prompt
from .validators import clean_test_cases, repair_expected_results, run_static_validation
from core.logger import log


class TestCaseGenerator:
    """测试用例生成器"""

    _BANNED_STEP_KEYWORDS = [
        "后台",
        "后端",
        "数据库",
        "接口",
        "API",
        "神策",
        "投放管理",
        "脚本",
        "运营",
    ]
    _WAIT_PATTERN = re.compile(r"等待\s*\d+\s*天")

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.extractor = FunctionModuleExtractor(llm_service)

    # === 功能模块提取 ===
    def extract_function_modules_with_content(self, requirement_doc: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.extractor.extract_function_modules_with_content(requirement_doc, run_id=run_id)

    def extract_function_points_with_content(self, requirement_doc: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.extractor.extract_function_points_with_content(requirement_doc, run_id=run_id)

    # === 功能点识别（在模块内识别子功能点）===
    def extract_function_points_from_module(
        self,
        module_name: str,
        module_content: str,
    ) -> List[Dict[str, Any]]:
        """
        从功能模块中提取子功能点

        Args:
            module_name: 功能模块名称
            module_content: 功能模块的需求文档内容

        Returns:
            功能点列表
        """
        if not ExtractionConfig.ENABLE_FUNCTION_POINT_EXTRACTION:
            return []

        try:
            prompt = build_function_point_extraction_prompt(module_name, module_content)
            log.debug(f"  提取功能点 Prompt (模块: {module_name})")

            response_text = self.llm_service.generate(prompt)
            response_text = response_text.strip()

            # 清理响应文本
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            # 解析JSON
            parsed = _parse_json_with_fallback(response_text)
            function_points = parsed.get("function_points", [])

            log.info(f"  从模块 '{module_name}' 中提取到 {len(function_points)} 个功能点")
            return function_points

        except Exception as e:
            log.warning(f"  提取功能点失败 (模块: {module_name}): {str(e)}")
            return []

    # === 复杂度评估 ===
    @staticmethod
    def assess_module_complexity(module_content: str) -> bool:
        """
        评估模块复杂度，判断是否需要识别功能点

        Args:
            module_content: 功能模块的需求文档内容

        Returns:
            True 表示复杂模块，需要识别功能点；False 表示简单模块，直接生成
        """
        if not ExtractionConfig.ENABLE_FUNCTION_POINT_EXTRACTION:
            return False

        # 检查内容长度
        content_length = len(module_content)
        if content_length < ExtractionConfig.COMPLEX_MODULE_THRESHOLD:
            return False

        # 检查是否包含多个明显的功能点标识（如"存在"、"无"、"支持"等）
        # 这里可以添加更复杂的启发式规则
        indicators = ["存在", "无", "支持", "不支持", "条件", "规则", "限制", "场景"]
        indicator_count = sum(1 for indicator in indicators if indicator in module_content)

        # 如果内容较长且包含多个功能点标识，认为是复杂模块
        if content_length >= ExtractionConfig.COMPLEX_MODULE_THRESHOLD and indicator_count >= 2:
            return True

        return False

    # === 生成单个模块的测试用例 ===
    @staticmethod
    def _build_single_point_prompt(function_point: str, doc_snippet: str) -> str:
        return f"""你是一位测试工程师。请根据需求文档为功能点"{function_point}"生成测试用例。

**重要：只输出JSON格式，不要任何其他文字！**

【需求文档】
{doc_snippet}

【功能点】
{function_point}

【要求】
1. 只生成与"{function_point}"相关的测试用例
2. 必须严格按照需求文档中的内容生成，不能编造
3. **测试用例中的expected_result字段必须逐字引用需求文档中的原句，不能改写、总结或意译**
4. 不能添加需求文档中没有的功能、按钮、操作
5. **输出必须全部使用简体中文，禁止出现繁体字或「」等繁体标点**
6. **用例中涉及的页面/模块名称必须与需求文档保持一致，不得自行更换页面位置**
7. **所有测试步骤必须是App端可执行的实际操作，禁止出现"登录后台""查看数据库""手动投放"等后台或运营动作**
8. **避免写入无法执行的描述（例如"等待7天"），遇到时改写为可执行的验证步骤或拆分为前置条件**

【生成规则】
- 仔细阅读需求文档中关于"{function_point}"的所有描述
- 为每个UI元素、交互逻辑、业务规则、限制条件生成测试用例
- **expected_result必须从需求文档中直接复制完整的句子，不能修改任何文字**
- 如果需求文档写"点击关闭直接消失"，expected_result必须写"点击关闭直接消失"（不能写成"点击关闭按钮后弹窗消失"）
- 直接引用需求文档中的按钮名称、字段名称、标题文字
- **每个测试用例的steps必须至少包含2-3条明确的操作步骤，每一步都要描述具体的用户操作**
- **步骤要详细具体，例如："1. 打开App，进入觉知页"、"2. 查看Banner是否显示"、"3. 点击【去评分】按钮"**
- **不要将多个操作合并为一个步骤，每个步骤只描述一个操作**
- 输出结构化且详尽，确保覆盖正常流程、边界场景与约束条件

【输出格式】
{{
  "test_cases": [
    {{
      "case_name": "用例名称",
      "description": "用例描述",
      "preconditions": "前置条件",
      "steps": ["步骤1：具体操作", "步骤2：具体操作", "步骤3：验证结果"],
      "expected_result": "预期结果（必须逐字复制需求文档中的原句，不能改写）",
      "priority": "high"
    }}
  ]
}}

**再次强调：只输出JSON，不要任何其他文字！**"""

    def generate_test_cases_for_point(
        self,
        requirement_doc: str,
        function_point: str,
        fp_data: Optional[Dict] = None,
    ) -> Tuple[List[Dict], List[str], str]:
        """
        为单个功能点生成测试用例

        Args:
            requirement_doc: 需求文档内容
            function_point: 功能点名称
            fp_data: 功能点数据（包含定位线索）

        Returns:
            测试用例列表
        """
        if fp_data and fp_data.get("_user_matched_content"):
            doc_snippet = fp_data["_user_matched_content"]
        else:
            doc_snippet = self.extractor.extract_relevant_section(requirement_doc, function_point, fp_data)

        prompt = self._build_single_point_prompt(function_point, doc_snippet)

        try:
            # 打印发送给模型的完整Prompt（用于调试）
            log.debug(f"  [完整Prompt]")
            log.debug(f"  {'='*60}")
            log.debug(f"  {prompt}")
            log.debug(f"  {'='*60}\n")

            response_text = self.llm_service.generate(prompt)

            # 解析JSON
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            # 清理控制字符（JSON不允许的控制字符）
            # 移除除了换行符、制表符、回车符之外的控制字符
            import string
            control_chars = ''.join(chr(i) for i in range(32) if chr(i) not in '\n\r\t')
            for char in control_chars:
                response_text = response_text.replace(char, '')

            # 修复JSON格式问题
            response_text = re.sub(r'"expected[^"]*":', '"expected_result":', response_text)
            response_text = re.sub(r'<\|[^|]+\|>', '', response_text)

            # 使用统一的JSON解析函数，增强容错能力
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # 如果标准解析失败，尝试使用容错解析
                log.debug(f"标准JSON解析失败，尝试容错解析...")
                result = _parse_json_with_fallback(response_text)
            test_cases = result.get("test_cases", [])
            # 先进行静态校验（包括格式修复）
            warnings = run_static_validation(
                function_point,
                test_cases,
                doc_snippet,
                self.extractor.normalize_text,
                self.extractor.fix_traditional_punctuation,
            )
            # 然后进行深度修复（替换为原文），避免重复修复
            repair_logs = repair_expected_results(
                function_point,
                test_cases,
                doc_snippet,
                self.extractor.normalize_text,
                self.extractor.fix_traditional_punctuation,
                skip_already_fixed=True,
            )
            if repair_logs:
                warnings.extend(repair_logs)
            filtered_cases, post_warnings = self._post_validate_test_cases(function_point, test_cases)
            if post_warnings:
                warnings.extend(post_warnings)
            return filtered_cases, warnings, doc_snippet
        except json.JSONDecodeError as e:
            log.warning(f"  ⚠ 功能点 '{function_point}' JSON解析失败: {str(e)}")
            log.debug(f"  原始响应（前1000字符）:")
            log.debug(f"  {response_text[:1000]}")
            return [], [f"JSON解析失败: {str(e)}"], doc_snippet
        except Exception as e:
            log.warning(f"  ⚠ 功能点 '{function_point}' 生成失败: {str(e)}")
            return [], [f"生成失败: {str(e)}"], doc_snippet

    def _post_validate_test_cases(
        self,
        function_point: str,
        test_cases: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        if not test_cases:
            return test_cases, []

        filtered_cases: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for idx, case in enumerate(test_cases, start=1):
            steps = case.get("steps")
            if not isinstance(steps, list):
                warnings.append(f"[{function_point}] 第{idx}条用例 steps 字段格式异常，已丢弃")
                continue

            normalized_steps = [str(step).strip() for step in steps if str(step).strip()]

            # 如果步骤数不足，尝试自动补全或拆分
            if len(normalized_steps) < 2:
                # 尝试拆分第一个步骤（如果它包含多个操作）
                if normalized_steps and len(normalized_steps[0]) > 30:
                    first_step = normalized_steps[0]
                    # 尝试按标点符号拆分
                    split_chars = ["，", "、", ",", "；", ";", "。", ".", "然后", "接着", "再"]
                    for split_char in split_chars:
                        if split_char in first_step:
                            parts = [p.strip() for p in first_step.split(split_char) if p.strip()]
                            if len(parts) >= 2:
                                normalized_steps = parts + normalized_steps[1:]
                                warnings.append(f"[{function_point}] 第{idx}条用例步骤已自动拆分")
                                break

                # 如果仍然不足2步，尝试从描述或预期结果中提取步骤
                if len(normalized_steps) < 2:
                    description = case.get("description", "")
                    expected_result = case.get("expected_result", "")

                    # 从描述中提取可能的步骤
                    if description:
                        desc_parts = [p.strip() for p in re.split(r"[，,。.；;]", description) if len(p.strip()) > 5]
                        if desc_parts and len(normalized_steps) == 1:
                            # 如果只有一个步骤，尝试添加一个验证步骤
                            normalized_steps.append(f"验证{expected_result[:20] if expected_result else '结果'}")
                            warnings.append(f"[{function_point}] 第{idx}条用例已自动补全验证步骤")

                    # 如果仍然不足2步，丢弃
                    if len(normalized_steps) < 2:
                        warnings.append(f"[{function_point}] 第{idx}条用例 steps 少于2步，已丢弃")
                        continue

            # 检查是否包含禁止的操作
            if any(self._contains_banned_action(step) for step in normalized_steps):
                warnings.append(f"[{function_point}] 第{idx}条用例包含后台/不可执行操作，已丢弃")
                continue

            # 检查是否包含"等待X天"的描述
            if any(self._WAIT_PATTERN.search(step) for step in normalized_steps):
                # 尝试将"等待X天"改为前置条件或验证步骤
                fixed_steps = []
                for step in normalized_steps:
                    if self._WAIT_PATTERN.search(step):
                        # 将等待描述移到前置条件或改为验证步骤
                        wait_match = self._WAIT_PATTERN.search(step)
                        if wait_match:
                            # 改为验证步骤："验证X天后Banner是否自动消失"
                            fixed_step = step.replace(wait_match.group(), "验证Banner是否自动消失")
                            fixed_steps.append(fixed_step)
                            warnings.append(f"[{function_point}] 第{idx}条用例已修复'等待X天'描述")
                        else:
                            fixed_steps.append(step)
                    else:
                        fixed_steps.append(step)
                normalized_steps = fixed_steps

            case["steps"] = normalized_steps
            filtered_cases.append(case)

        return filtered_cases, warnings

    def _contains_banned_action(self, text: str) -> bool:
        normalized_text = text.lower()
        for keyword in self._BANNED_STEP_KEYWORDS:
            if keyword.lower() in normalized_text:
                return True
        return False

    def _generate_single_point_wrapper(self, requirement_doc: str, fp_data: Dict, idx: int, total: int) -> Tuple[str, List[Dict], List[str], str]:
        """
        包装方法，用于并发处理单个功能模块（支持智能两阶段生成）

        Args:
            requirement_doc: 需求文档内容
            fp_data: 功能模块数据
            idx: 当前索引
            total: 总数量

        Returns:
            (module_name, test_cases, warnings, doc_snippet)
        """
        module_name = fp_data.get("name", "")
        try:
            log.debug(f"[{idx}/{total}] 正在处理模块: {module_name}")

            # 获取模块内容
            if fp_data.get("_user_matched_content"):
                module_content = fp_data["_user_matched_content"]
            else:
                module_content = self.extractor.extract_relevant_section(requirement_doc, module_name, fp_data)

            # 评估模块复杂度
            is_complex = self.assess_module_complexity(module_content)

            all_test_cases = []
            all_warnings = []

            if is_complex:
                # 复杂模块：先识别功能点，再为每个功能点生成测试用例
                log.info(f"[{idx}/{total}] 模块 '{module_name}' 被识别为复杂模块，开始提取功能点...")
                function_points = self.extract_function_points_from_module(module_name, module_content)

                if len(function_points) >= ExtractionConfig.MIN_FUNCTION_POINTS_FOR_EXTRACTION:
                    # 为每个功能点生成测试用例
                    log.info(f"[{idx}/{total}] 为模块 '{module_name}' 的 {len(function_points)} 个功能点生成测试用例...")
                    for fp_idx, fp in enumerate(function_points, 1):
                        fp_name = fp.get("name", "")
                        if not fp_name:
                            continue

                        # 构建功能点数据
                        fp_data_for_generation = {
                            "name": fp_name,
                            "keywords": fp.get("keywords", []),
                            "exact_phrases": fp.get("exact_phrases", []),
                            "section_hint": module_name,
                            "_user_matched_content": module_content,  # 使用模块内容作为上下文
                        }

                        try:
                            test_cases, warnings, _ = self.generate_test_cases_for_point(
                                requirement_doc, fp_name, fp_data_for_generation
                            )
                            all_test_cases.extend(test_cases)
                            all_warnings.extend(warnings)
                            log.debug(f"    功能点 '{fp_name}': 生成 {len(test_cases)} 个测试用例")
                        except Exception as e:
                            log.warning(f"    功能点 '{fp_name}' 生成失败: {str(e)}")
                            all_warnings.append(f"功能点 '{fp_name}' 生成失败: {str(e)}")

                    log.info(f"[{idx}/{total}] ✓ {module_name}: 通过功能点识别生成 {len(all_test_cases)} 个测试用例")
                else:
                    # 功能点数量不足，回退到直接生成
                    log.info(f"[{idx}/{total}] 模块 '{module_name}' 功能点数量不足 ({len(function_points)} < {ExtractionConfig.MIN_FUNCTION_POINTS_FOR_EXTRACTION})，回退到直接生成")
                    all_test_cases, all_warnings, _ = self.generate_test_cases_for_point(
                        requirement_doc, module_name, fp_data
                    )
            else:
                # 简单模块：直接生成测试用例
                log.debug(f"[{idx}/{total}] 模块 '{module_name}' 被识别为简单模块，直接生成测试用例")
                all_test_cases, all_warnings, _ = self.generate_test_cases_for_point(
                    requirement_doc, module_name, fp_data
                )

            if all_test_cases:
                log.info(f"[{idx}/{total}] ✓ {module_name}: 生成 {len(all_test_cases)} 个测试用例")
            else:
                log.warning(f"[{idx}/{total}] ⚠ {module_name}: 未生成测试用例")

            if all_warnings:
                for warn in all_warnings:
                    log.debug(f"    • {module_name}: {warn}")

            return module_name, all_test_cases, all_warnings, module_content

        except Exception as e:
            log.error(f"[{idx}/{total}] ✗ {module_name}: 处理失败 - {str(e)}")
            return module_name, [], [f"处理失败: {str(e)}"], ""

    def generate_test_cases(
        self,
        requirement_doc: str,
        limit: Optional[int] = None,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        confirmed_function_points: Optional[List[Dict[str, Any]]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict:
        """
        生成测试用例 - 为每个功能模块分别生成

        Args:
            requirement_doc: 需求文档内容
            limit: 限制功能模块数量
            max_workers: 最大并发数
            progress_callback: 进度回调函数
            confirmed_function_points: 用户确认后的功能模块列表（如果提供，跳过提取步骤）
                                     注意：参数名保持为 function_points 以兼容前端，但实际处理的是功能模块

        Returns:
            包含测试用例的字典
        """
        log.debug("正在生成测试用例...")
        run_id = trace_id or uuid4().hex

        # 并发数合理性检查：限制在1-20之间，防止资源耗尽
        if max_workers < 1:
            log.warning(f"并发数 {max_workers} 过小，调整为 1")
            max_workers = 1
        elif max_workers > 20:
            log.warning(f"并发数 {max_workers} 过大，调整为 20 以防止资源耗尽")
            max_workers = 20

        def notify(event: Dict[str, Any]) -> None:
            if not progress_callback:
                return
            try:
                progress_callback(event)
            except Exception as callback_error:  # noqa: BLE001
                log.warning(f"进度回调执行失败: {callback_error}")

        # 如果提供了已确认的功能模块，直接使用；否则提取功能模块
        if confirmed_function_points:
            log.info(f"使用提供的 {len(confirmed_function_points)} 个功能模块生成测试用例")
            # 将确认后的功能模块转换为内部格式
            function_points_data = []
            for module in confirmed_function_points:
                fp_data = {
                    "name": module.get("name", ""),
                    "keywords": module.get("keywords", []),
                    "exact_phrases": module.get("exact_phrases", []),
                    "section_hint": module.get("section_hint", ""),
                }
                # 如果用户手动指定了匹配内容，使用用户指定的内容
                if module.get("matched_content"):
                    # 这里可以存储用户指定的内容，后续生成时使用
                    fp_data["_user_matched_content"] = module.get("matched_content")
                function_points_data.append(fp_data)

            notify({
                "type": "function_points",
                "total": len(function_points_data),
            })
        else:
            notify({
                "type": "status",
                "stage": "extract_function_points",
                "message": "正在提取功能模块...",
            })

            # 第一步：提取功能模块（带定位线索）
            function_points_data = self.extractor.extract_function_modules(requirement_doc, run_id=run_id)

        if not function_points_data:
            log.warning("⚠ 未能提取功能模块，使用传统方式生成...")
            notify({
                "type": "status",
                "stage": "single_pass_generation",
                "message": "未提取到功能模块，改为整体生成。",
            })
            # 如果没有提取到功能点，使用原来的方式
            prompt = build_generation_prompt(requirement_doc)
            # 打印发送给模型的完整Prompt（用于调试）
            log.debug(f"[完整Prompt]")
            log.debug(f"{'='*60}")
            log.debug(f"{prompt}")
            log.debug(f"{'='*60}\n")
            response_text = self.llm_service.generate(prompt)
            # 继续原有的解析逻辑
            result = self._parse_response(response_text)
            try:
                record_ai_debug(
                    "generate_test_cases_fallback",
                    {
                        "model": getattr(self.llm_service, "model", None),
                        "base_url": getattr(self.llm_service, "base_url", None),
                        "requirement_doc": requirement_doc,
                        "requirement_doc_length": len(requirement_doc or ""),
                        "parameters": {
                            "limit": limit,
                            "max_workers": max_workers,
                            "confirmed_function_points": confirmed_function_points,
                        },
                        "result": result,
                    },
                    run_id=run_id,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("记录整体生成调试信息失败: %s", exc)
            notify({
                "type": "completed",
                "result": result,
            })
            return result

        notify({
            "type": "function_points",
            "total": len(function_points_data),
        })

        # 第二步：为每个功能点分别生成测试用例
        all_test_cases = []
        per_point_cases: Dict[str, Dict[str, Any]] = {}
        total_points = len(function_points_data)

        # 测试模式：随机选择N个功能点（用于快速测试）
        effective_limit = limit if limit is not None else None
        if effective_limit and effective_limit > 0:
            if len(function_points_data) > effective_limit:
                # 随机选择N个功能点
                selected_points = random.sample(function_points_data, effective_limit)
                function_points_data = selected_points
                log.warning(f"⚠ 限制功能模块数量：随机选择 {effective_limit} 个功能模块进行生成\n")
            else:
                log.warning(f"⚠ 功能模块总数({len(function_points_data)})少于限制数({effective_limit})，处理所有功能模块\n")

        actual_points = len(function_points_data)
        notify({
            "type": "status",
            "stage": "generate_per_point",
            "message": f"开始生成 {actual_points} 个功能模块的测试用例...",
        })
        log.info(f"第二步：为 {actual_points} 个功能模块分别生成测试用例（并发处理，最大并发数: {max_workers}）...\n")

        # 使用线程池并发处理功能点
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_fp = {
                executor.submit(self._generate_single_point_wrapper, requirement_doc, fp_data, idx, actual_points): fp_data
                for idx, fp_data in enumerate(function_points_data, 1)
            }

            # 收集结果（按完成顺序）
            completed = 0
            for future in as_completed(future_to_fp):
                completed += 1
                try:
                    function_point_name, test_cases, warnings, doc_snippet = future.result()
                    per_point_cases[function_point_name] = {
                        "test_cases": test_cases,
                        "warnings": warnings,
                        "source": doc_snippet
                    }
                    if test_cases:
                        all_test_cases.extend(test_cases)
                    log.info(f"  [{completed}/{actual_points}] 已完成: {function_point_name}\n")
                    notify({
                        "type": "function_point_completed",
                        "name": function_point_name,
                        "index": completed,
                        "total": actual_points,
                        "test_cases": test_cases,
                        "warnings": warnings,
                    })
                except Exception as e:
                    fp_data = future_to_fp[future]
                    function_point_name = fp_data.get("name", "")
                    log.error(f"  [{completed}/{actual_points}] ✗ {function_point_name}: 发生异常 - {str(e)}\n")
                    per_point_cases[function_point_name] = {
                        "test_cases": [],
                        "warnings": [f"处理异常: {str(e)}"],
                        "source": ""
                    }
                    notify({
                        "type": "function_point_failed",
                        "name": function_point_name,
                        "index": completed,
                        "total": actual_points,
                        "error": str(e),
                    })

        # 清理测试用例中的临时标记字段
        cleaned_test_cases = clean_test_cases(all_test_cases)
        cleaned_per_point_cases = {}
        for fp_name, fp_data in per_point_cases.items():
            cleaned_fp_data = fp_data.copy()
            if "test_cases" in cleaned_fp_data:
                cleaned_fp_data["test_cases"] = clean_test_cases(cleaned_fp_data["test_cases"])
            cleaned_per_point_cases[fp_name] = cleaned_fp_data

        result = {
            "test_cases": cleaned_test_cases,
            "by_function_point": cleaned_per_point_cases,
            "meta": {
                "total_function_points": total_points,
                "processed_function_points": actual_points,
                "limit": effective_limit or 0,
                "total_warnings": sum(len(data.get("warnings", []) or []) for data in per_point_cases.values())
            }
        }
        log.info(f"✓ 总共生成 {len(cleaned_test_cases)} 个测试用例")
        try:
            record_ai_debug(
                "generate_test_cases",
                {
                    "model": getattr(self.llm_service, "model", None),
                    "base_url": getattr(self.llm_service, "base_url", None),
                    "requirement_doc": requirement_doc,
                    "requirement_doc_length": len(requirement_doc or ""),
                    "parameters": {
                        "limit": limit,
                        "max_workers": max_workers,
                        "confirmed_function_points": confirmed_function_points,
                    },
                    "function_points": function_points_data,
                    "per_point_cases": cleaned_per_point_cases,
                    "test_cases": cleaned_test_cases,
                    "meta": result.get("meta"),
                },
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("记录测试用例生成调试信息失败: %s", exc)
        notify({
            "type": "completed",
            "result": result,
        })
        return result

    def _parse_response(self, response_text: str) -> Dict:
        """
        解析模型响应（原有逻辑）

        Args:
            response_text: 模型响应文本

        Returns:
            包含测试用例的字典
        """

        # 解析JSON响应
        try:
            # 尝试提取JSON部分（去除可能的markdown代码块标记）
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # 移除markdown代码块标记
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            # 尝试找到JSON对象
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            # 清理控制字符（JSON不允许的控制字符）
            import string
            control_chars = ''.join(chr(i) for i in range(32) if chr(i) not in '\n\r\t')
            for char in control_chars:
                response_text = response_text.replace(char, '')

            # 修复常见的JSON格式问题
            # 1. 修复被截断的字段名（如 expected<|redacted...|> 应该修复为 expected_result）
            response_text = re.sub(r'"expected[^"]*":', '"expected_result":', response_text)
            # 2. 修复其他可能的截断标记
            response_text = re.sub(r'<\|[^|]+\|>', '', response_text)
            # 3. 移除末尾不完整的字段
            lines = response_text.split('\n')
            cleaned_lines = []
            for line in lines:
                # 如果行包含不完整的字段（有引号开始但没有冒号），跳过
                if '":' in line or line.strip() in ['{', '}', '[', ']', ','] or not line.strip():
                    cleaned_lines.append(line)
                elif line.strip().startswith('"') and ':' not in line:
                    # 可能是被截断的字段，尝试修复或跳过
                    if 'expected' in line.lower():
                        cleaned_lines.append('            "expected_result": "",')
                    # 否则跳过这行
                else:
                    cleaned_lines.append(line)
            response_text = '\n'.join(cleaned_lines)

            # 尝试找到最后一个完整的JSON对象
            # 如果JSON不完整，尝试修复
            brace_count = response_text.count('{') - response_text.count('}')
            if brace_count > 0:
                # 缺少右括号，补充
                response_text += '\n' + '}' * brace_count
            elif brace_count < 0:
                # 多余的右括号，移除最后一个
                for _ in range(-brace_count):
                    last_brace = response_text.rfind('}')
                    if last_brace != -1:
                        response_text = response_text[:last_brace] + response_text[last_brace+1:]

            # 使用统一的JSON解析函数，增强容错能力
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # 如果标准解析失败，尝试使用容错解析
                log.debug("标准JSON解析失败，尝试容错解析...")
                result = _parse_json_with_fallback(response_text)

            # 验证结果格式
            if "test_cases" not in result:
                raise ValueError("响应中缺少'test_cases'字段")

            # 清理临时标记字段
            result["test_cases"] = clean_test_cases(result.get("test_cases", []))

            log.info(f"✓ 成功生成 {len(result.get('test_cases', []))} 个测试用例")
            return result

        except json.JSONDecodeError as e:
            log.warning(f"⚠ JSON解析遇到问题，尝试修复...")
            # 尝试更激进的修复：提取所有完整的测试用例
            try:
                # 使用预编译的正则表达式提取所有测试用例
                matches = RE_JSON_CASE.findall(response_text)
                if matches:
                    fixed_cases = []
                    for match in matches:
                        try:
                            case = json.loads(match)
                            # 确保必要字段存在
                            if 'case_name' in case:
                                if 'expected_result' not in case:
                                    case['expected_result'] = ''
                                fixed_cases.append(case)
                        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                            continue
                    if fixed_cases:
                        # 清理临时标记字段
                        cleaned_cases = clean_test_cases(fixed_cases)
                        result = {"test_cases": cleaned_cases}
                        log.info(f"✓ 成功修复并生成 {len(cleaned_cases)} 个测试用例")
                        return result
            except (json.JSONDecodeError, re.error, ValueError):
                pass

            log.error(f"✗ JSON解析失败: {str(e)}")
            log.debug(f"原始响应内容（前500字符）:")
            log.debug(f"原始响应内容: {response_text[:500]}")
            raise ValueError(f"无法解析LLM返回的JSON格式: {str(e)}")
        except Exception as e:
            log.error(f"✗ 生成测试用例失败: {str(e)}")
            raise
