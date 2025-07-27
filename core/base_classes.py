from abc import ABC, abstractmethod
import logging
import threading
import time
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from core.interfaces import (
    ISystemModule, IDatabaseManager, IDeviceController,
    IScreenRecognizer, ITask, ITaskManager, IAppScheduler,
    IAccountService, IStateManager, ISystemKernel
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("system.log"), logging.StreamHandler()]
)

class SystemModule(ISystemModule):
    """Base class for all system modules"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        """Initialize system module
        
        Args:
            name: Module name
            version: Module version
        """
        self._name = name
        self._version = version
        self._initialized = False
        self._logger = logging.getLogger(name)
    
    def initialize(self) -> bool:
        """Initialize the module
        
        Returns:
            True if initialization successful, False otherwise
        """
        self._initialized = True
        self._logger.info(f"Module {self._name} v{self._version} initialized")
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the module
        
        Returns:
            True if shutdown successful, False otherwise
        """
        self._initialized = False
        self._logger.info(f"Module {self._name} v{self._version} shutdown")
        return True
    
    @property
    def is_initialized(self) -> bool:
        """Check if module is initialized
        
        Returns:
            True if module is initialized, False otherwise
        """
        return self._initialized
    
    @property
    def name(self) -> str:
        """Get module name
        
        Returns:
            Module name
        """
        return self._name
    
    @property
    def version(self) -> str:
        """Get module version
        
        Returns:
            Module version
        """
        return self._version
    
    def log_info(self, message: str):
        """Log an info message
        
        Args:
            message: Message to log
        """
        self._logger.info(message)
    
    def log_warning(self, message: str):
        """Log a warning message
        
        Args:
            message: Message to log
        """
        self._logger.warning(message)
    
    def log_error(self, message: str):
        """Log an error message
        
        Args:
            message: Message to log
        """
        self._logger.error(message)
    
    def log_debug(self, message: str):
        """Log a debug message
        
        Args:
            message: Message to log
        """
        self._logger.debug(message)


class Task(ITask):
    """Base task class"""
    
    def __init__(self, task_id: str, name: str, app_id: str, parent_id: str = None):
        """Initialize task
        
        Args:
            task_id: Task ID
            name: Task name
            app_id: Associated app ID
            parent_id: Parent task ID
        """
        self._task_id = task_id
        self._name = name
        self._app_id = app_id
        self._parent_id = parent_id
        self._monitor_thread = None
        self._monitor_running = False
        self._logger = logging.getLogger(f"Task-{name}")
    
    @property
    def name(self) -> str:
        """Get task name
        
        Returns:
            Task name
        """
        return self._name
    
    @property
    def task_id(self) -> str:
        """Get unique task ID
        
        Returns:
            Task ID
        """
        return self._task_id
    
    @property
    def app_id(self) -> str:
        """Get associated app ID
        
        Returns:
            App ID
        """
        return self._app_id
    
    @property
    def parent_id(self) -> Optional[str]:
        """Get parent task ID
        
        Returns:
            Parent task ID or None
        """
        return self._parent_id
    
    def start_monitor(self, config: Dict[str, Any]) -> None:
        """Start task monitoring
        
        Args:
            config: Task configuration
        """
        if self._monitor_thread and self._monitor_running:
            return
            
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(config,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        self._logger.info(f"Task monitoring started: {self._name}")
    
    def stop_monitor(self) -> None:
        """Stop task monitoring"""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        self._logger.info(f"Task monitoring stopped: {self._name}")
    
    def _monitor_loop(self, config: Dict[str, Any]) -> None:
        """Monitor loop implementation
        
        Args:
            config: Task configuration
        """
        # Base implementation does nothing, should be overridden by subclasses
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get task status
        
        Returns:
            Task status dictionary
        """
        return {
            "task_id": self._task_id,
            "name": self._name,
            "app_id": self._app_id,
            "parent_id": self._parent_id
        }
    
    def log(self, message: str):
        """Log a message
        
        Args:
            message: Message to log
        """
        self._logger.info(f"[{self._name}] {message}")


class ModuleRegistry:
    """Registry for system modules"""
    
    def __init__(self):
        """Initialize module registry"""
        self._modules = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger("ModuleRegistry")
    
    def register_module(self, module: ISystemModule) -> bool:
        """Register a module
        
        Args:
            module: Module instance
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if module.name in self._modules:
                self._logger.warning(f"Module already registered: {module.name}")
                return False
                
            self._modules[module.name] = module
            self._logger.info(f"Module registered: {module.name} v{module.version}")
            return True
    
    def unregister_module(self, module_name: str) -> bool:
        """Unregister a module
        
        Args:
            module_name: Module name
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if module_name not in self._modules:
                self._logger.warning(f"Module not registered: {module_name}")
                return False
                
            del self._modules[module_name]
            self._logger.info(f"Module unregistered: {module_name}")
            return True
    
    def get_module(self, module_name: str) -> Optional[ISystemModule]:
        """Get a module
        
        Args:
            module_name: Module name
            
        Returns:
            Module instance or None
        """
        return self._modules.get(module_name)
    
    def get_all_modules(self) -> Dict[str, ISystemModule]:
        """Get all modules
        
        Returns:
            Dictionary of module names and instances
        """
        return self._modules.copy()
    
    def get_module_by_interface(self, interface_class) -> List[ISystemModule]:
        """Get modules implementing a specific interface
        
        Args:
            interface_class: Interface class
            
        Returns:
            List of modules implementing the interface
        """
        return [m for m in self._modules.values() if isinstance(m, interface_class)]


class SystemKernel(ISystemKernel):
    """System kernel implementation"""
    
    def __init__(self):
        """Initialize system kernel"""
        self._name = "SystemKernel"
        self._version = "1.0.0"
        self._registry = ModuleRegistry()
        self._running = False
        self._initialized = False
        self._logger = logging.getLogger("SystemKernel")
    
    def initialize(self) -> bool:
        """Initialize the kernel
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
            
        self._logger.info("Initializing system kernel...")
        self._initialized = True
        self._logger.info("System kernel initialized")
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the kernel
        
        Returns:
            True if shutdown successful, False otherwise
        """
        if not self._initialized:
            return True
            
        self._logger.info("Shutting down system kernel...")
        
        # Stop if running
        if self._running:
            self.stop()
        
        # Shutdown all modules in reverse dependency order
        modules = self._registry.get_all_modules()
        for module_name in reversed(list(modules.keys())):
            module = modules[module_name]
            try:
                module.shutdown()
            except Exception as e:
                self._logger.error(f"Error shutting down module {module_name}: {str(e)}")
        
        self._initialized = False
        self._logger.info("System kernel shutdown complete")
        return True
    
    @property
    def is_initialized(self) -> bool:
        """Check if kernel is initialized
        
        Returns:
            True if kernel is initialized, False otherwise
        """
        return self._initialized
    
    @property
    def name(self) -> str:
        """Get kernel name
        
        Returns:
            Kernel name
        """
        return self._name
    
    @property
    def version(self) -> str:
        """Get kernel version
        
        Returns:
            Kernel version
        """
        return self._version
    
    def get_module(self, module_name: str) -> Optional[ISystemModule]:
        """Get a system module
        
        Args:
            module_name: Module name
            
        Returns:
            Module instance or None
        """
        return self._registry.get_module(module_name)
    
    def register_module(self, module: ISystemModule) -> bool:
        """Register a system module
        
        Args:
            module: Module instance
            
        Returns:
            True if successful, False otherwise
        """
        return self._registry.register_module(module)
    
    def unregister_module(self, module_name: str) -> bool:
        """Unregister a system module
        
        Args:
            module_name: Module name
            
        Returns:
            True if successful, False otherwise
        """
        return self._registry.unregister_module(module_name)
    
    def start(self) -> bool:
        """Start the system
        
        Returns:
            True if successful, False otherwise
        """
        if self._running:
            return True
            
        if not self._initialized:
            if not self.initialize():
                return False
        
        self._logger.info("Starting system...")
        
        # Initialize all modules
        modules = self._registry.get_all_modules()
        for module_name, module in modules.items():
            try:
                if not module.is_initialized:
                    if not module.initialize():
                        self._logger.error(f"Failed to initialize module: {module_name}")
                        return False
            except Exception as e:
                self._logger.error(f"Error initializing module {module_name}: {str(e)}")
                return False
        
        self._running = True
        self._logger.info("System started")
        return True
    
    def stop(self) -> bool:
        """Stop the system
        
        Returns:
            True if successful, False otherwise
        """
        if not self._running:
            return True
            
        self._logger.info("Stopping system...")
        
        # Get AppScheduler module if available
        app_scheduler = None
        for module in self._registry.get_module_by_interface(IAppScheduler):
            app_scheduler = module
            break
        
        # Stop the app scheduler if available
        if app_scheduler:
            try:
                app_scheduler.stop()
            except Exception as e:
                self._logger.error(f"Error stopping AppScheduler: {str(e)}")
        
        self._running = False
        self._logger.info("System stopped")
        return True
    
    def is_running(self) -> bool:
        """Check if system is running
        
        Returns:
            True if running, False otherwise
        """
        return self._running
    
        # 在Task类中添加以下方法
    def get_task_resource_path(self, resource_type, resource_name):
        """获取任务资源路径
        Args:
            resource_type: 资源类型 (templates, config, db等)
            resource_name: 资源名称
        Returns:
            资源完整路径
        """
        task_dir = f"tasks/{self.app_id.lower()}"
        return os.path.join(task_dir, resource_type, resource_name)

    def load_task_config(self, config_name):
        """加载任务特定配置
        Args:
            config_name: 配置文件名
        Returns:
            配置数据字典
        """
        config_path = self.get_task_resource_path("config", config_name)
        return utils.load_json_file(config_path, {})

    def get_context(self) -> Dict[str, Any]:
        """获取系统上下文信息"""
        context = {
            'current_app_id': None,
            'current_task_name': None
        }

        # 获取当前应用ID
        app_scheduler = self.get_module("AppScheduler")
        if app_scheduler:
            context['current_app_id'] = app_scheduler.get_current_app_id()

        # 获取当前任务名称
        task_manager = self.get_module("TaskManager")
        if task_manager:
            context['current_task_name'] = task_manager.get_current_task()

        return context
