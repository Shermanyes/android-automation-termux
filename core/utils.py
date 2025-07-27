# core/utils.py
import uuid
import time
from typing import Any, Dict, List, Optional, Tuple, Union

def generate_id(prefix: str = '') -> str:
    """Generate a unique ID
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique ID string
    """
    return f"{prefix}{uuid.uuid4().hex}"

def current_timestamp() -> int:
    """Get current timestamp
    
    Returns:
        Current timestamp in seconds
    """
    return int(time.time())
