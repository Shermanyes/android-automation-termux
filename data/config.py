import os
import json
import logging
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("config.log"), logging.StreamHandler()]
)
logger = logging.getLogger('config')

class Config:
    """System configuration handler"""
    
    _instance = None
    
    def __new__(cls, config_path: str = "config.json"):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration manager
        
        Args:
            config_path: Path to the configuration file
        """
        if self._initialized:
            return
            
        self.config_path = config_path
        self.config = {}
        self.load_config()
        self._initialized = True
    
    def load_config(self) -> bool:
        """Load configuration from file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from: {self.config_path}")
                return True
            else:
                self.config = {
                    "database": {
                        "path": "automation.db",
                        "pool_size": 5
                    },
                    "device": {
                        "type": "emulator",
                        "instance_index": 0,
                        "ld_path": "D:\\计算机辅助\\leidian\\LDPlayer9\\ld.exe",
                        "ldconsole_path": "D:\\计算机辅助\\leidian\\LDPlayer9\\ldconsole.exe"
                    },
                    "recognition": {
                        "ocr_lang": "chi_sim+eng",
                        "ocr_config": "--psm 6",
                        "match_threshold": 0.8
                    },
                    "scheduling": {
                        "default_time_slice": 7200,  # 2 hours
                        "default_daily_limit": 14400,  # 4 hours
                        "default_reset_time": "04:00"
                    },
                    "logging": {
                        "level": "INFO",
                        "file": "automation.log"
                    }
                }
                self.save_config()
                logger.info(f"Default configuration created at: {self.config_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            return False
    
    def save_config(self) -> bool:
        """Save configuration to file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info(f"Configuration saved to: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value
        
        Args:
            key: Configuration key (supports dot notation for nested values)
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value
        
        Args:
            key: Configuration key (supports dot notation for nested values)
            value: Value to set
            
        Returns:
            True if successful, False otherwise
        """
        keys = key.split('.')
        config = self.config
        try:
            # Navigate to the deepest dict
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
                
            # Set the value
            config[keys[-1]] = value
            return True
        except Exception as e:
            logger.error(f"Failed to set configuration: {str(e)}")
            return False
    
    def update(self, config_dict: Dict[str, Any]) -> bool:
        """Update configuration with a dictionary
        
        Args:
            config_dict: Dictionary with configuration values
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._deep_update(self.config, config_dict)
            return True
        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}")
            return False
    
    def _deep_update(self, d: Dict[str, Any], u: Dict[str, Any]) -> None:
        """Recursively update a dictionary
        
        Args:
            d: Dictionary to update
            u: Dictionary with new values
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
