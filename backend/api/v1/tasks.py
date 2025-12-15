# encoding: utf-8
"""任务管理路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shared.logger import log
from models import TaskStatusResponse

from domain.task.manager import get_task_manager

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    查询任务状态。
    
    客户端应定期轮询此接口直到任务状态为 completed 或 failed。
    """
    task_manager = get_task_manager()
    task_info = task_manager.get_task_status(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    return TaskStatusResponse(**task_info)

