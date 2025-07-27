from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
import time

class ISystemModule(ABC):
    """Base interface for all system modules"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the module
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """Shutdown the module
        
        Returns:
            True if shutdown successful, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if module is initialized
        
        Returns:
            True if module is initialized, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get module name
        
        Returns:
            Module name
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Get module version
        
        Returns:
            Module version
        """
        pass


class IDatabaseManager(ISystemModule):
    """Database manager interface"""
    
    @abstractmethod
    def execute(self, query: str, params: tuple = None) -> int:
        """Execute a query and return the number of affected rows
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def executemany(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets
        
        Args:
            query: SQL query
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute a query and fetch one row
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Dictionary with row data or None
        """
        pass
    
    @abstractmethod
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and fetch all rows
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of dictionaries with row data
        """
        pass
    
    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert data into a table
        
        Args:
            table: Table name
            data: Dictionary of column names and values
            
        Returns:
            Row ID of the inserted row
        """
        pass
    
    @abstractmethod
    def update(self, table: str, data: Dict[str, Any], condition: str, condition_params: tuple = None) -> int:
        """Update data in a table
        
        Args:
            table: Table name
            data: Dictionary of column names and values to update
            condition: WHERE clause
            condition_params: Parameters for the condition
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def delete(self, table: str, condition: str, condition_params: tuple = None) -> int:
        """Delete data from a table
        
        Args:
            table: Table name
            condition: WHERE clause
            condition_params: Parameters for the condition
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def exists(self, table: str, condition: str, condition_params: tuple = None) -> bool:
        """Check if records exist in a table
        
        Args:
            table: Table name
            condition: WHERE clause
            condition_params: Parameters for the condition
            
        Returns:
            True if records exist, False otherwise
        """
        pass
    
    @abstractmethod
    def count(self, table: str, condition: str = "1=1", condition_params: tuple = None) -> int:
        """Count records in a table
        
        Args:
            table: Table name
            condition: WHERE clause
            condition_params: Parameters for the condition
            
        Returns:
            Record count
        """
        pass
    
    @abstractmethod
    def transaction(self):
        """Return a transaction context manager"""
        pass
    
    @abstractmethod
    def backup(self, backup_path: str) -> bool:
        """Create a backup of the database
        
        Args:
            backup_path: Path to save the backup
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def log_activity(self, action: str, status: str, app_id: str = None, account_id: str = None, task_id: str = None, details: str = None):
        """Log an activity
        
        Args:
            action: Action performed
            status: Status of the action (success, failure, etc.)
            app_id: Application ID
            account_id: Account ID
            task_id: Task ID
            details: Additional details
        """
        pass


class IDeviceController(ISystemModule):
    """Device controller interface"""
    
    @abstractmethod
    def take_screenshot(self, filename: str = None):
        """Take a screenshot
        
        Args:
            filename: Optional file to save screenshot
            
        Returns:
            Image object if filename is None, otherwise True/False
        """
        pass
    
    @abstractmethod
    def tap(self, x: int, y: int) -> bool:
        """Tap at the specified coordinates
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """Swipe from one point to another
        
        Args:
            x1: Starting X coordinate
            y1: Starting Y coordinate
            x2: Ending X coordinate
            y2: Ending Y coordinate
            duration: Swipe duration in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def input_text(self, text: str) -> bool:
        """Input text
        
        Args:
            text: Text to input
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def press_key(self, keycode: int) -> bool:
        """Press a key
        
        Args:
            keycode: Key code
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def back(self) -> bool:
        """Press back button
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def home(self) -> bool:
        """Press home button
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start_app(self, package_name: str) -> bool:
        """Start an application
        
        Args:
            package_name: Package name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def stop_app(self, package_name: str) -> bool:
        """Stop an application
        
        Args:
            package_name: Package name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def wait(self, seconds: float) -> None:
        """Wait for specified seconds
        
        Args:
            seconds: Seconds to wait
        """
        pass


class IScreenRecognizer(ISystemModule):
    """Screen recognizer interface"""
    
    @abstractmethod
    def find_image(self, template_path: str, threshold: float = 0.8, roi: tuple = None):
        """Find an image on the screen
        
        Args:
            template_path: Path to template image
            threshold: Match threshold (0.0-1.0)
            roi: Region of interest (x1, y1, x2, y2)
            
        Returns:
            Tuple (center_x, center_y, width, height) if found, None otherwise
        """
        pass
    
    @abstractmethod
    def find_text(self, text: str, lang: str = None, config: str = None, roi: tuple = None, threshold: float = 0.6):
        """Find text on the screen
        
        Args:
            text: Text to find
            lang: OCR language
            config: OCR config
            roi: Region of interest (x1, y1, x2, y2)
            threshold: Text match threshold
            
        Returns:
            Tuple (x, y, width, height) if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_screen_text(self, lang: str = 'chi_sim+eng') -> str:
        """Get all text from the screen
        
        Args:
            lang: OCR language
            
        Returns:
            Recognized text
        """
        pass
    
    @abstractmethod
    def recognize_scene(self, scene_configs: Dict[str, Any]) -> Optional[str]:
        """Recognize the current scene
        
        Args:
            scene_configs: Dictionary of scene configurations
            
        Returns:
            Scene name if recognized, None otherwise
        """
        pass


class ITask(ABC):
    """Task interface"""
    
    @abstractmethod
    def execute(self) -> bool:
        """Execute the task
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start_monitor(self, config: Dict[str, Any]) -> None:
        """Start task monitoring
        
        Args:
            config: Task configuration
        """
        pass
    
    @abstractmethod
    def stop_monitor(self) -> None:
        """Stop task monitoring"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get task status
        
        Returns:
            Task status dictionary
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get task name
        
        Returns:
            Task name
        """
        pass
    
    @property
    @abstractmethod
    def task_id(self) -> str:
        """Get unique task ID
        
        Returns:
            Task ID
        """
        pass
    
    @property
    @abstractmethod
    def app_id(self) -> str:
        """Get associated app ID
        
        Returns:
            App ID
        """
        pass
    
    @property
    @abstractmethod
    def parent_id(self) -> Optional[str]:
        """Get parent task ID
        
        Returns:
            Parent task ID or None
        """
        pass


class ITaskManager(ISystemModule):
    """Task manager interface"""
    
    @abstractmethod
    def register_task(self, task_class, task_config: Dict[str, Any] = None) -> str:
        """Register a task
        
        Args:
            task_class: Task class
            task_config: Task configuration
            
        Returns:
            Task ID
        """
        pass
    
    @abstractmethod
    def unregister_task(self, task_id: str) -> bool:
        """Unregister a task
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def execute_task(self, task_id: str) -> bool:
        """Execute a task
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def execute_task_async(self, task_id: str) -> bool:
        """Execute a task asynchronously
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task started, False otherwise
        """
        pass
    
    @abstractmethod
    def stop_task(self, task_id: str) -> bool:
        """Stop a running task
        
        Args:
            task_id: Task ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_task_status(self, task_id: str, account_id: str = None) -> Dict[str, Any]:
        """Get task status
        
        Args:
            task_id: Task ID
            account_id: Optional account ID
            
        Returns:
            Task status dictionary
        """
        pass
    
    @abstractmethod
    def update_task_status(self, task_id: str, account_id: str, status: Dict[str, Any]) -> bool:
        """Update task status
        
        Args:
            task_id: Task ID
            account_id: Account ID
            status: Status dictionary
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_next_task(self, app_id: str, account_id: str) -> Optional[str]:
        """Get next task to execute
        
        Args:
            app_id: App ID
            account_id: Account ID
            
        Returns:
            Task ID or None
        """
        pass
    
    @abstractmethod
    def get_task_list(self, app_id: str = None, parent_id: str = None) -> List[Dict[str, Any]]:
        """Get list of tasks
        
        Args:
            app_id: Optional app ID filter
            parent_id: Optional parent task ID filter
            
        Returns:
            List of task dictionaries
        """
        pass


class IAppScheduler(ISystemModule):
    """Application scheduler interface"""
    
    @abstractmethod
    def register_app(self, app_id: str, app_config: Dict[str, Any]) -> bool:
        """Register an application
        
        Args:
            app_id: App ID
            app_config: App configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def unregister_app(self, app_id: str) -> bool:
        """Unregister an application
        
        Args:
            app_id: App ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Start the scheduler
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Stop the scheduler
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_next_app(self) -> Optional[str]:
        """Get next app to execute
        
        Returns:
            App ID or None
        """
        pass
    
    @abstractmethod
    def update_app_runtime(self, app_id: str, seconds: int) -> bool:
        """Update app runtime
        
        Args:
            app_id: App ID
            seconds: Runtime in seconds
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def switch_to_app(self, app_id: str) -> bool:
        """Switch to a specific app
        
        Args:
            app_id: App ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_app_status(self, app_id: str) -> Dict[str, Any]:
        """Get app status
        
        Args:
            app_id: App ID
            
        Returns:
            App status dictionary
        """
        pass
    
    @abstractmethod
    def get_app_list(self) -> List[Dict[str, Any]]:
        """Get list of registered apps
        
        Returns:
            List of app dictionaries
        """
        pass


class IAccountService(ISystemModule):
    """Account service interface"""
    
    @abstractmethod
    def add_account(self, account_id: str, app_id: str, account_info: Dict[str, Any]) -> bool:
        """Add an account
        
        Args:
            account_id: Account ID
            app_id: App ID
            account_info: Account information
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def remove_account(self, account_id: str) -> bool:
        """Remove an account
        
        Args:
            account_id: Account ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account information
        
        Args:
            account_id: Account ID
            
        Returns:
            Account dictionary or None
        """
        pass
    
    @abstractmethod
    def get_account_list(self, app_id: str = None) -> List[Dict[str, Any]]:
        """Get list of accounts
        
        Args:
            app_id: Optional app ID filter
            
        Returns:
            List of account dictionaries
        """
        pass
    
    @abstractmethod
    def get_next_account(self, app_id: str) -> Optional[str]:
        """Get next account for an app
        
        Args:
            app_id: App ID
            
        Returns:
            Account ID or None
        """
        pass
    
    @abstractmethod
    def switch_to_account(self, account_id: str) -> bool:
        """Switch to a specific account
        
        Args:
            account_id: Account ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def update_account_task_status(self, account_id: str, task_id: str, completed: bool) -> bool:
        """Update account's task status
        
        Args:
            account_id: Account ID
            task_id: Task ID
            completed: True if task completed, False otherwise
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_account_task_status(self, account_id: str, task_id: str = None) -> Dict[str, Any]:
        """Get account's task status
        
        Args:
            account_id: Account ID
            task_id: Optional task ID filter
            
        Returns:
            Dictionary with task status information
        """
        pass
    
    @abstractmethod
    def clear_daily_tasks(self, app_id: str = None, account_id: str = None) -> bool:
        """Clear daily tasks
        
        Args:
            app_id: Optional app ID filter
            account_id: Optional account ID filter
            
        Returns:
            True if successful, False otherwise
        """
        pass


class IStateManager(ISystemModule):
    """State manager interface"""
    
    @abstractmethod
    def register_state(self, state_id: str, app_id: str, recognition_config: Dict[str, Any], callback=None) -> bool:
        """Register a state
        
        Args:
            state_id: State ID
            app_id: App ID
            recognition_config: State recognition configuration
            callback: Optional callback function
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def unregister_state(self, state_id: str) -> bool:
        """Unregister a state
        
        Args:
            state_id: State ID
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start_monitoring(self, interval: float = 2.0) -> bool:
        """Start state monitoring
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def stop_monitoring(self) -> bool:
        """Stop state monitoring
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_current_state(self) -> Optional[str]:
        """Get current state
        
        Returns:
            Current state ID or None
        """
        pass
    
    @abstractmethod
    def recognize_current_scene(self, app_id: str = None) -> Optional[str]:
        """Recognize current scene
        
        Args:
            app_id: Optional app ID filter
            
        Returns:
            Scene state ID or None
        """
        pass


class ISystemKernel(ISystemModule):
    """System kernel interface"""
    
    @abstractmethod
    def get_module(self, module_name: str) -> Optional[ISystemModule]:
        """Get a system module
        
        Args:
            module_name: Module name
            
        Returns:
            Module instance or None
        """
        pass
    
    @abstractmethod
    def register_module(self, module: ISystemModule) -> bool:
        """Register a system module
        
        Args:
            module: Module instance
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def unregister_module(self, module_name: str) -> bool:
        """Unregister a system module
        
        Args:
            module_name: Module name
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Start the system
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Stop the system
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if system is running
        
        Returns:
            True if running, False otherwise
        """
        pass
# 在interfaces.py末尾添加这段代码

class IConfigParserPlugin(ABC):
    """配置解析器插件接口"""
    
    @abstractmethod
    def get_name(self) -> str:
        """获取解析器名称
        
        Returns:
            解析器名称
        """
        pass
    
    @abstractmethod
    def parse(self, content: str, task_name: str = None, db_path: str = None) -> bool:
        """解析配置内容
        
        Args:
            content: 配置内容
            task_name: 可选的任务名称，用于存储到任务数据库
            db_path: 可选的数据库路径
            
        Returns:
            是否成功
        """
        pass
