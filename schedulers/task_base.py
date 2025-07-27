# schedulers/task_base.py
from typing import Any, Dict, List, Optional
import json
import time
import os

from core.interfaces import ITask
from core.base_classes import Task

class GameTask(Task):
    """Base class for game automation tasks"""
    
    def __init__(self, task_id, name, app_id, parent_id=None, task_type=None):
        """Initialize the task
        
        Args:
            task_id: Task ID
            name: Task name
            app_id: App ID
            parent_id: Parent task ID
            task_type: Task type name for loading resources
        """
        super().__init__(task_id, name, app_id, parent_id)
        self.task_type = task_type or name.lower()
        self.resources_path = f"tasks/{self.task_type}"
        self.config_path = f"{self.resources_path}/config"
        self.templates_path = f"{self.resources_path}/templates"
        self.db_path = f"{self.resources_path}/db/{self.task_type}.db"
        self.monitoring = False
        self.status = {
            "start_time": 0,
            "end_time": 0,
            "current_step": "",
            "progress": 0,
            "total_steps": 0,
            "errors": []
        }
    
    def initialize(self) -> bool:
        """Initialize the task
        
        Returns:
            True if initialization was successful
        """
        self.status["start_time"] = int(time.time())
        self.status["current_step"] = "Initializing"
        
        # Check if resources exist
        if not os.path.exists(self.resources_path):
            self.add_error(f"Resources not found: {self.resources_path}")
            return False
        
        return True
    
    def add_error(self, message: str):
        """Add an error message to status
        
        Args:
            message: Error message
        """
        self.status["errors"].append({
            "time": int(time.time()),
            "message": message
        })
        
    def set_progress(self, step: str, progress: int, total: int = 100):
        """Update progress status
        
        Args:
            step: Current step name
            progress: Current progress value
            total: Total progress value
        """
        self.status["current_step"] = step
        self.status["progress"] = progress
        self.status["total_steps"] = total
    
    def start_monitor(self, config: Dict[str, Any]) -> None:
        """Start task monitoring
        
        Args:
            config: Monitoring configuration
        """
        self.monitoring = True
        self.status["monitoring"] = True
    
    def stop_monitor(self) -> None:
        """Stop task monitoring"""
        self.monitoring = False
        self.status["monitoring"] = False
        self.status["end_time"] = int(time.time())
    
    def get_status(self) -> Dict[str, Any]:
        """Get task status
        
        Returns:
            Status dictionary
        """
        # Update execution time
        if self.status["start_time"] > 0:
            current_time = int(time.time())
            end_time = self.status["end_time"] or current_time
            self.status["execution_time"] = end_time - self.status["start_time"]
        
        return self.status

    def recognize_state(self):
        """识别当前状态，带任务上下文

        Returns:
            状态ID或None
        """
        # 获取状态管理器
        system = self.get_system()
        if not system:
            return None

        state_manager = system.get_module("StateManager")
        if not state_manager:
            return None

        # 调用状态识别，传入任务名称
        return state_manager.recognize_current_scene(self.app_id, self.task_type)

    # 添加此方法，用于获取系统内核实例
    def get_system(self):
        """获取系统内核实例"""
        from core.base_classes import SystemKernel
        return SystemKernel.get_instance()

    # 添加此方法，用于等待指定状态
    def wait_for_state(self, target_state: str, timeout: int = 30, interval: float = 1.0) -> bool:
        """等待指定状态出现

        Args:
            target_state: 目标状态ID
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）

        Returns:
            是否成功等待到指定状态
        """
        import time
        system = self.get_system()
        if not system:
            return False

        device = system.get_module("AndroidDeviceController")
        if not device:
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            current_state = self.recognize_state()
            if current_state == target_state:
                return True

            device.wait(interval)

        return False
