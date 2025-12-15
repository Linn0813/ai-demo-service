# encoding: utf-8
"""
文本分割器，用于将长文本分割成较小的块。
"""
from __future__ import annotations

from typing import List


class TextSplitter:
    """文本分割器，将长文本分割成适合向量化的块。"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        """
        初始化文本分割器。

        Args:
            chunk_size: 每个块的最大字符数
            chunk_overlap: 块之间的重叠字符数
            separators: 分割符列表（按优先级排序），默认使用换行符和句号
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", ".", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """
        将文本分割成块。

        Args:
            text: 输入文本

        Returns:
            文本块列表
        """
        if not text or len(text) <= self.chunk_size:
            return [text] if text else []

        chunks = []
        start = 0

        while start < len(text):
            # 确定当前块的结束位置
            end = start + self.chunk_size

            if end >= len(text):
                # 到达文本末尾
                chunks.append(text[start:])
                break

            # 尝试在分隔符处分割
            best_split = end
            for separator in self.separators:
                if separator:
                    # 向前查找分隔符
                    pos = text.rfind(separator, start, end)
                    if pos != -1:
                        best_split = pos + len(separator)
                        break
                else:
                    # 空字符串分隔符，直接在当前位置分割
                    best_split = end
                    break

            # 提取块
            chunk = text[start:best_split].strip()
            if chunk:
                chunks.append(chunk)

            # 移动到下一个块的开始位置（考虑重叠）
            start = max(start + 1, best_split - self.chunk_overlap)

        return chunks

