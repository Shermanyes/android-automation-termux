import os
import time
import sqlite3
import logging
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 修改导入路径
from core.base_classes import Task

class GameTask(Task):
    """三国杀游戏任务基类"""
    
    def __init__(self, task_id, name, app_id, parent_id=None, game_name="three_kingdoms"):
        super().__init__(task_id, name, app_id, parent_id)
        self.db_path = f"tasks/{game_name}/db/{game_name}.db"  # 修正db路径
        self.game_name = game_name
        self.state_manager = None
        self.device = None
        self.recognizer = None
        self.coordinates = {}
        self.current_state = None
        self._logger = logging.getLogger(f"{game_name}.{name}")
        
    # 其余代码保持不变
    
    def _get_device_controller(self):
        """获取设备控制器"""
        try:
            # 修正导入路径
            from components.device_controller import AndroidDeviceController
            
            # 尝试从主控获取
            kernel = self._get_system_kernel()
            if kernel:
                device = kernel.get_module("AndroidDeviceController")
                if device and device.is_initialized:
                    return device
                    
            # 如果无法从主控获取，创建新实例
            device = AndroidDeviceController()
            if not device.is_initialized:
                device.initialize()
            return device
            
        except Exception as e:
            self.log_error(f"获取设备控制器失败: {str(e)}")
            return None
            
    def _get_screen_recognizer(self):
        """获取屏幕识别器"""
        try:
            # 修正导入路径
            from components.screen_recognizer import ScreenRecognizer
            
            # 尝试从主控获取
            kernel = self._get_system_kernel()
            if kernel:
                recognizer = kernel.get_module("ScreenRecognizer")
                if recognizer and recognizer.is_initialized:
                    return recognizer
                    
            # 如果无法从主控获取，创建新实例
            device = self._get_device_controller()
            if not device:
                return None
                
            recognizer = ScreenRecognizer(device)
            if not recognizer.is_initialized:
                recognizer.initialize()
            return recognizer
            
        except Exception as e:
            self.log_error(f"获取屏幕识别器失败: {str(e)}")
            return None
            
    def _get_database_manager(self):
        """获取数据库管理器"""
        try:
            # 修正导入路径
            from data.database_manager import DatabaseManager
            
            # 尝试从主控获取
            kernel = self._get_system_kernel()
            if kernel:
                db_manager = kernel.get_module("DatabaseManager")
                if db_manager and db_manager.is_initialized:
                    return db_manager
                    
            # 如果无法从主控获取，创建新实例
            db_manager = DatabaseManager()
            if not db_manager.is_initialized:
                db_manager.initialize()
            return db_manager
            
        except Exception as e:
            self.log_error(f"获取数据库管理器失败: {str(e)}")
            return None
            
    def _get_system_kernel(self):
        """获取系统内核"""
        try:
            # 修正导入路径
            from core.base_classes import SystemKernel
            kernel = SystemKernel()
            if kernel.is_initialized:
                return kernel
            return None
        except Exception:
            return None
