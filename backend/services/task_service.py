"""
Task execution service for web application.

Provides background task management using ThreadPoolExecutor for the standalone web version.
"""

import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Dict
import logging

logger = logging.getLogger(__name__)

# Initialize ThreadPoolExecutor for web application - only 1 concurrent job
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="neuroinsight-task")


class TaskResult:
    """Wrapper for task results compatible with both threading and Celery"""
    
    def __init__(self, future: Future, task_id: str):
        self.future = future
        self.task_id = task_id
    
    @property
    def id(self) -> str:
        """Task ID"""
        return self.task_id
    
    def ready(self) -> bool:
        """Check if task is complete"""
        return self.future.done()
    
    def get(self, timeout: float = None) -> Any:
        """Get task result (blocks until complete)"""
        try:
            return self.future.result(timeout=timeout)
        except Exception as e:
            logger.error(f"Task {self.task_id} failed: {e}")
            raise
    
    def cancel(self) -> bool:
        """Attempt to cancel task"""
        return self.future.cancel()


class TaskService:
    """Service for submitting and managing background tasks"""
    
    @staticmethod
    def submit_task(func: Callable, *args, **kwargs) -> TaskResult:
        """
        Submit a task for background execution.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            TaskResult: Object to track task status
        """
        # Generate task ID
        import uuid
        task_id = str(uuid.uuid4())

        logger.info(f"Submitting task {task_id} to executor")

        # Submit to ThreadPoolExecutor
        future = executor.submit(func, *args, **kwargs)

        return TaskResult(future, task_id)
    
    @staticmethod
    def get_executor_stats() -> Dict[str, Any]:
        """Get statistics about the task executor"""
        return {
            "max_workers": executor._max_workers,
            "queue_size": executor._work_queue.qsize(),
            "active_threads": len(executor._threads),
            "mode": "threading",
        }
    
    @staticmethod
    def shutdown(wait: bool = True):
        """Shutdown the task executor"""
        if executor is not None:
            logger.info("Shutting down task executor")
            executor.shutdown(wait=wait)

# Convenience function for direct task submission
def submit_task(func: Callable, *args, **kwargs) -> TaskResult:
    """Submit a background task"""
    return TaskService.submit_task(func, *args, **kwargs)

