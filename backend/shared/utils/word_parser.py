# encoding: utf-8
"""Word 文档解析工具。"""
from __future__ import annotations

import io
from typing import Any, Dict

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph


def parse_word_document(file_content: bytes) -> Dict[str, Any]:
    """
    解析 Word 文档（.docx 格式）并提取文本内容。

    Args:
        file_content: Word 文档的二进制内容

    Returns:
        包含解析结果的字典：
        - text: 提取的完整文本内容
        - total_paragraphs: 段落总数
        - total_headings: 标题数量
        - structure: 文档结构信息（可选）
    """
    try:
        # 将字节内容转换为文件对象
        doc_file = io.BytesIO(file_content)
        doc = Document(doc_file)

        # 提取文本和统计信息
        paragraphs = []
        headings = []
        total_paragraphs = 0
        total_headings = 0

        # 遍历文档中的所有元素（段落和表格）
        for element in doc.element.body:
            if isinstance(element, CT_P):
                # 段落
                paragraph = Paragraph(element, doc)
                text = paragraph.text.strip()
                if text:
                    paragraphs.append(text)
                    total_paragraphs += 1
                    # 检查是否是标题（样式以 Heading 开头）
                    if paragraph.style.name.startswith('Heading'):
                        headings.append(text)
                        total_headings += 1
            elif isinstance(element, CT_Tbl):
                # 表格
                table = Table(element, doc)
                table_text = _extract_table_text(table)
                if table_text:
                    paragraphs.append(table_text)
                    total_paragraphs += 1

        # 合并所有文本
        full_text = '\n\n'.join(paragraphs)

        return {
            'text': full_text,
            'total_paragraphs': total_paragraphs,
            'total_headings': total_headings,
            'structure': {
                'headings': headings[:10],  # 只保留前10个标题作为预览
            } if headings else None,
        }
    except Exception as e:
        raise ValueError(f"解析 Word 文档失败: {str(e)}") from e


def _extract_table_text(table: Table) -> str:
    """提取表格中的文本内容。"""
    rows_text = []
    for row in table.rows:
        cells_text = []
        for cell in row.cells:
            cell_text = cell.text.strip()
            if cell_text:
                cells_text.append(cell_text)
        if cells_text:
            rows_text.append(' | '.join(cells_text))
    return '\n'.join(rows_text) if rows_text else ''

