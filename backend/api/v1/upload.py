# encoding: utf-8
"""文件上传路由"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from shared.logger import log
from models import WordUploadResponse

from shared.utils import parse_word_document

router = APIRouter(tags=["upload"])


@router.post("/upload/word", response_model=WordUploadResponse)
async def upload_word_document(file: UploadFile = File(...)) -> WordUploadResponse:
    """
    上传并解析 Word 文档（.docx 格式）。

    Args:
        file: 上传的 Word 文档文件

    Returns:
        WordUploadResponse: 包含解析后的文本内容和统计信息
    """
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="仅支持 .docx 格式的 Word 文档")

    try:
        # 读取文件内容
        file_content = await file.read()

        # 验证文件大小（限制为 10MB）
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制（最大 10MB），当前文件大小: {len(file_content) / 1024 / 1024:.2f}MB"
            )

        # 解析 Word 文档
        result = parse_word_document(file_content)

        log.info(
            f"成功解析 Word 文档: {file.filename}, "
            f"段落数: {result['total_paragraphs']}, "
            f"标题数: {result['total_headings']}"
        )

        return WordUploadResponse(**result)
    except HTTPException:
        raise
    except ValueError as exc:
        log.exception(f"解析 Word 文档失败: {file.filename}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception(f"上传 Word 文档失败: {file.filename}")
        raise HTTPException(status_code=500, detail=f"上传 Word 文档失败: {exc}") from exc

