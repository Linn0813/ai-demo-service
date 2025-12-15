# encoding: utf-8
"""异步任务管理器。"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import threading

from shared.logger import log


class TaskStatus(str, Enum):
    """任务状态枚举。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    """异步任务管理器。"""
    
    def __init__(self, max_workers: int = 4):
        """
        初始化任务管理器。
        
        Args:
            max_workers: 最大并发工作线程数
        """
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cleanup_thread = None
        self._running = True
        
    def submit_task(
        self,
        task_func: Callable,
        *args,
        task_type: str = "unknown",
        **kwargs
    ) -> str:
        """
        提交异步任务。
        
        Args:
            task_func: 要执行的任务函数
            *args: 任务函数的参数
            task_type: 任务类型（用于日志）
            **kwargs: 任务函数的关键字参数
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        
        task_info = {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "task_type": task_type,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "progress": None,
        }
        
        with self._lock:
            self._tasks[task_id] = task_info
        
        # 提交任务到线程池
        future = self._executor.submit(self._execute_task, task_id, task_func, *args, **kwargs)
        
        # 保存future以便后续查询
        with self._lock:
            self._tasks[task_id]["future"] = future
        
        log.info(f"任务已提交: {task_id} (类型: {task_type})")
        return task_id
    
    def _execute_task(self, task_id: str, task_func: Callable, *args, **kwargs):
        """执行任务的内部方法。"""
        try:
            with self._lock:
                task_info = self._tasks.get(task_id)
                if not task_info:
                    log.error(f"任务不存在: {task_id}")
                    return
                task_info["status"] = TaskStatus.RUNNING
                task_info["started_at"] = datetime.now()
            
            log.info(f"任务开始执行: {task_id}")
            
            # 执行任务函数
            result = task_func(*args, **kwargs)
            
            # 更新任务状态
            with self._lock:
                task_info = self._tasks.get(task_id)
                if task_info:
                    task_info["status"] = TaskStatus.COMPLETED
                    task_info["completed_at"] = datetime.now()
                    task_info["result"] = result
            
            log.info(f"任务执行完成: {task_id}")
            
        except Exception as e:
            log.exception(f"任务执行失败: {task_id}")
            with self._lock:
                task_info = self._tasks.get(task_id)
                if task_info:
                    task_info["status"] = TaskStatus.FAILED
                    task_info["completed_at"] = datetime.now()
                    task_info["error"] = str(e)
    
    def update_progress(self, task_id: str, progress_info: Dict[str, Any]) -> bool:
        """
        更新任务进度。
        
        Args:
            task_id: 任务ID
            progress_info: 进度信息字典，包含：
                - stage: 当前阶段（如 "extracting_modules", "generating_test_cases"）
                - progress: 进度百分比 (0-100)
                - current: 当前处理项索引
                - total: 总项数
                - message: 进度消息
                - current_item: 当前处理项名称
                
        Returns:
            是否更新成功
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                log.warning(f"任务不存在，无法更新进度: {task_id}")
                return False
            
            # 合并进度信息
            if task_info.get("progress") is None:
                task_info["progress"] = {}
            task_info["progress"].update(progress_info)
            
            log.debug(f"任务进度更新: {task_id} - {progress_info.get('message', '')}")
            return True
    
    def update_partial_result(self, task_id: str, partial_result: Dict[str, Any]) -> bool:
        """
        更新部分结果（用于实时展示）。
        
        Args:
            task_id: 任务ID
            partial_result: 部分结果字典
            
        Returns:
            是否更新成功
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return False
            
            task_info["partial_result"] = partial_result
            log.debug(f"任务部分结果更新: {task_id}")
            return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态。
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息，如果任务不存在则返回None
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return None
                
            # 返回任务信息的副本（移除future对象）
            result = {
                "task_id": task_info["task_id"],
                "status": task_info["status"].value if isinstance(task_info["status"], TaskStatus) else task_info["status"],
                "task_type": task_info["task_type"],
                "created_at": task_info["created_at"].isoformat() if task_info["created_at"] else None,
                "started_at": task_info["started_at"].isoformat() if task_info["started_at"] else None,
                "completed_at": task_info["completed_at"].isoformat() if task_info["completed_at"] else None,
                "result": task_info.get("result"),
                "error": task_info.get("error"),
                "progress": task_info.get("progress"),
                "partial_result": task_info.get("partial_result"),  # 新增：部分结果
            }
            return result
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """
        获取任务结果（仅当任务完成时）。
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务结果，如果任务未完成或不存在则返回None
        """
        with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return None
            
            if task_info["status"] == TaskStatus.COMPLETED:
                return task_info.get("result")
            elif task_info["status"] == TaskStatus.FAILED:
                raise Exception(task_info.get("error", "任务执行失败"))
            else:
                return None
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        清理旧任务（超过指定时间的已完成或失败任务）。
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        if not self._running:
            return
            
        with self._lock:
            now = datetime.now()
            to_remove = []
            
            for task_id, task_info in self._tasks.items():
                if task_info["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    if task_info["completed_at"]:
                        age = (now - task_info["completed_at"]).total_seconds() / 3600
                        if age > max_age_hours:
                            to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._tasks[task_id]
                log.debug(f"已清理旧任务: {task_id}")
    
    def shutdown(self):
        """关闭任务管理器。"""
        self._running = False
        self._executor.shutdown(wait=True)
        log.info("任务管理器已关闭")


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例。"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(max_workers=4)
    return _task_manager
