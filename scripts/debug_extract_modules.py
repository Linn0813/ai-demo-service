"""调试脚本：验证功能模块提取与原文匹配"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，便于脚本直接运行
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 注意：此脚本已迁移到独立项目 ai_demo_service
# 如需使用，请从 ai_demo_service 项目中运行，或更新导入路径为：
# from ai_demo_core.engine.extractors import FunctionModuleExtractor
# from ai_demo_core.engine.llm_service import LLMService

# 临时兼容：尝试从新项目导入
try:
    import sys
    from pathlib import Path
    ai_demo_path = Path(__file__).resolve().parents[1] / "ai_demo_service" / "src"
    if str(ai_demo_path) not in sys.path:
        sys.path.insert(0, str(ai_demo_path))
    from ai_demo_core.engine.extractors import FunctionModuleExtractor
    from ai_demo_core.engine.llm_service import LLMService
except ImportError:
    print("错误：无法导入AI模块。")
    print("请确保 ai_demo_service 项目已正确安装，或从 ai_demo_service 目录运行此脚本。")
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="调试功能模块提取逻辑")
    parser.add_argument(
        "requirement_file",
        nargs="?",
        default="scripts/example_requirement.txt",
        help="需求文档路径，默认使用脚本目录下的 example_requirement.txt",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="LLM 服务地址，默认 http://localhost:11434",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="指定的模型名称（可选，默认使用 LLMService 内部默认值）",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="可选：输出结果到指定 JSON 文件",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    requirement_path = Path(args.requirement_file)
    if not requirement_path.is_file():
        raise FileNotFoundError(f"未找到需求文档: {requirement_path}")

    requirement_doc = requirement_path.read_text(encoding="utf-8")

    llm_service = LLMService(base_url=args.base_url, model=args.model)
    extractor = FunctionModuleExtractor(llm_service)

    modules = extractor.extract_function_modules_with_content(requirement_doc)

    print(f"共识别到 {len(modules)} 个功能模块\n")
    for idx, module in enumerate(modules, start=1):
        print(f"[{idx}] {module['name']} (置信度: {module.get('match_confidence','unknown')})")
        if module.get("description"):
            print(f"  描述: {module['description'][:120]}")
        print(f"  原文片段长度: {len(module.get('matched_content',''))}")
        print('-' * 60)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.write_text(json.dumps(modules, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"模块信息已写入 {output_path}")


if __name__ == "__main__":
    main()
