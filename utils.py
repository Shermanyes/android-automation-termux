import time
import os
import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("utils.log"), logging.StreamHandler()]
)
logger = logging.getLogger('utils')

def generate_id(prefix: str = "") -> str:
    """Generate a unique ID
    
    Args:
        prefix: ID prefix
        
    Returns:
        Unique ID
    """
    return f"{prefix}{uuid.uuid4().hex[:16]}"

def current_timestamp() -> int:
    """Get current UNIX timestamp
    
    Returns:
        Current timestamp in seconds
    """
    return int(time.time())

def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert UNIX timestamp to datetime
    
    Args:
        timestamp: UNIX timestamp
        
    Returns:
        Datetime object
    """
    return datetime.fromtimestamp(timestamp)

def datetime_to_timestamp(dt: datetime) -> int:
    """Convert datetime to UNIX timestamp
    
    Args:
        dt: Datetime object
        
    Returns:
        UNIX timestamp
    """
    return int(dt.timestamp())

def parse_time_string(time_str: str) -> Tuple[int, int]:
    """Parse time string in HH:MM format
    
    Args:
        time_str: Time string in HH:MM format
        
    Returns:
        Tuple of (hours, minutes)
    """
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}")
    
    hours = int(parts[0])
    minutes = int(parts[1])
    
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid time values: {time_str}")
    
    return (hours, minutes)

def format_time_string(hours: int, minutes: int) -> str:
    """Format hours and minutes as HH:MM
    
    Args:
        hours: Hours (0-23)
        minutes: Minutes (0-59)
        
    Returns:
        Time string in HH:MM format
    """
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid time values: {hours}:{minutes}")
    
    return f"{hours:02d}:{minutes:02d}"

def is_time_between(current_time: str, start_time: str, end_time: str) -> bool:
    """Check if current time is between start and end time
    
    Args:
        current_time: Current time in HH:MM format
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format
        
    Returns:
        True if current time is between start and end time, False otherwise
    """
    current_hours, current_minutes = parse_time_string(current_time)
    start_hours, start_minutes = parse_time_string(start_time)
    end_hours, end_minutes = parse_time_string(end_time)
    
    current_minutes_total = current_hours * 60 + current_minutes
    start_minutes_total = start_hours * 60 + start_minutes
    end_minutes_total = end_hours * 60 + end_minutes
    
    if end_minutes_total < start_minutes_total:  # Crossing midnight
        return current_minutes_total >= start_minutes_total or current_minutes_total <= end_minutes_total
    else:
        return start_minutes_total <= current_minutes_total <= end_minutes_total

def get_current_time_string() -> str:
    """Get current time as HH:MM string
    
    Returns:
        Current time in HH:MM format
    """
    now = datetime.now()
    return format_time_string(now.hour, now.minute)

def load_json_file(file_path: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    """Load JSON from file
    
    Args:
        file_path: JSON file path
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Dictionary with JSON data
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return default or {}
    except Exception as e:
        logger.error(f"Failed to load JSON file {file_path}: {str(e)}")
        return default or {}

def save_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    """Save dictionary as JSON file
    
    Args:
        file_path: JSON file path
        data: Dictionary to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON file {file_path}: {str(e)}")
        return False

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Retry decorator for functions
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
        exceptions: Exceptions to catch
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed: {str(e)}. Retrying in {current_delay:.2f} seconds...")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
        return wrapper
    return decorator

def ensure_dir_exists(directory):
    """确保目录存在，不存在则创建
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)

def get_task_path(task_name):
    """获取任务模块路径
    Args:
        task_name: 任务名称
    Returns:
        任务模块路径
    """
    return f"tasks/{task_name.lower()}"

def load_simple_config(file_path, default=None):
    """加载简单格式的配置文件
    Args:
        file_path: 文件路径
        default: 默认值
    Returns:
        解析后的配置
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        result = {}
        section = None
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1].strip()
                result[section] = {}
                continue
                
            if '=' in line and section is not None:
                key, value = line.split('=', 1)
                result[section][key.strip()] = value.strip()
                
        return result
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
        return default or {}

class RateLimiter:
    """Rate limiter for function calls"""
    
    def __init__(self, max_calls: int, period: float):
        """Initialize rate limiter
        
        Args:
            max_calls: Maximum number of calls
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = threading.Lock()
    
    def __call__(self, func):
        """Decorator implementation"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.lock:
                now = time.time()
                
                # Remove old calls
                self.calls = [t for t in self.calls if now - t < self.period]
                
                # Check if we're under the limit
                if len(self.calls) >= self.max_calls:
                    sleep_time = self.period - (now - self.calls[0])
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        now = time.time()
                        self.calls = [t for t in self.calls if now - t < self.period]
                
                # Add the current call
                self.calls.append(now)
                
                # Execute the function
                return func(*args, **kwargs)
                
        return wrapper

# Import wraps for decorator functions
from functools import wraps
