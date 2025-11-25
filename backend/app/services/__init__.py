# encoding: utf-8
"""服务层，封装对 ai_demo_core 的调用。"""

from .test_case_service import AIDemoTestCaseService
from .knowledge_base_service import KnowledgeBaseService

__all__ = ["AIDemoTestCaseService", "KnowledgeBaseService"]
