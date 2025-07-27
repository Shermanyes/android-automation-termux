"""
任务数据库帮助工具
提供任务特定数据库的访问和管理功能
"""
import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("database.log"), logging.StreamHandler()]
)
logger = logging.getLogger('TaskDatabaseHelper')

class TaskDatabaseHelper:
    """任务数据库帮助工具类"""
    
    def __init__(self):
        """初始化任务数据库帮助工具"""
        self.tasks_dir = "tasks"  # 任务目录
        self.connections = {}     # 数据库连接缓存

    def get_task_list(self) -> List[str]:
        """获取所有任务列表

        Returns:
            任务名称列表
        """
        try:
            if not os.path.exists(self.tasks_dir):
                logger.warning(f"任务目录不存在: {self.tasks_dir}")
                return []

            tasks = []
            for item in os.listdir(self.tasks_dir):
                task_dir = os.path.join(self.tasks_dir, item)
                if os.path.isdir(task_dir) and not item.startswith('__'):
                    # 直接检查任务目录中是否有.db文件
                    has_db = False
                    for file in os.listdir(task_dir):
                        if file.endswith('.db'):
                            has_db = True
                            break

                    # 或者检查db子目录
                    db_dir = os.path.join(task_dir, "db")
                    if not has_db and os.path.exists(db_dir):
                        for file in os.listdir(db_dir):
                            if file.endswith('.db'):
                                has_db = True
                                break

                    # 添加到列表
                    if has_db or os.path.exists(os.path.join(task_dir, "main_task.py")):
                        tasks.append(item)

            logger.info(f"找到任务: {tasks}")
            return tasks
        except Exception as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return []

    def get_task_database_path(self, task_name: str) -> Optional[str]:
        """获取任务数据库路径

        Args:
            task_name: 任务名称

        Returns:
            数据库路径或None
        """
        try:
            # 首先检查任务目录本身是否有数据库
            task_dir = os.path.join(self.tasks_dir, task_name)
            logger.info(f"检查任务目录: {task_dir}")

            if not os.path.exists(task_dir):
                logger.warning(f"任务目录不存在: {task_dir}")
                return None

            # 检查直接位于任务目录下的数据库文件
            for file in os.listdir(task_dir):
                if file.endswith('.db'):
                    db_path = os.path.join(task_dir, file)
                    logger.info(f"找到任务数据库: {db_path}")
                    return db_path

            # 然后检查db子目录
            db_dir = os.path.join(task_dir, "db")
            if os.path.exists(db_dir):
                logger.info(f"检查DB子目录: {db_dir}")
                # 查找数据库文件
                for file in os.listdir(db_dir):
                    if file.endswith('.db'):
                        db_path = os.path.join(db_dir, file)
                        logger.info(f"找到任务数据库: {db_path}")
                        return db_path

            # 如果找不到，尝试使用默认位置
            default_dir_db = os.path.join(db_dir, f"{task_name}.db")
            default_task_db = os.path.join(task_dir, f"{task_name}.db")
            default_automation_db = os.path.join(task_dir, "automation.db")

            logger.info(f"检查默认路径: {default_dir_db}, {default_task_db}, {default_automation_db}")

            # 按优先级返回可能的路径
            if os.path.exists(default_dir_db):
                logger.info(f"使用默认DB目录路径: {default_dir_db}")
                return default_dir_db
            elif os.path.exists(default_task_db):
                logger.info(f"使用默认任务名数据库: {default_task_db}")
                return default_task_db
            elif os.path.exists(default_automation_db):
                logger.info(f"使用默认automation.db: {default_automation_db}")
                return default_automation_db

            # 如果都不存在，创建一个新的数据库
            logger.info(f"所有路径都不存在，将使用默认路径: {default_task_db}")
            return default_task_db

        except Exception as e:
            logger.error(f"获取任务数据库路径失败: {str(e)}")
            return None
    
    def get_db_connection(self, task_name: str = None, db_path: str = None) -> Optional[sqlite3.Connection]:
        """获取数据库连接
        
        Args:
            task_name: 任务名称
            db_path: 可选的数据库路径，将覆盖任务名称
            
        Returns:
            数据库连接或None
        """
        try:
            # 确定数据库路径
            if db_path is None and task_name is not None:
                db_path = self.get_task_database_path(task_name)
            
            if db_path is None:
                logger.error("无法确定数据库路径")
                return None
            
            # 检查数据库文件是否存在，如果不存在则创建
            db_dir = os.path.dirname(db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            
            # 检查连接缓存
            if db_path in self.connections and self.connections[db_path] is not None:
                # 测试连接是否有效
                try:
                    self.connections[db_path].execute("SELECT 1")
                    return self.connections[db_path]
                except:
                    # 连接已关闭，移除缓存
                    del self.connections[db_path]
            
            # 创建新连接
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # 缓存连接
            self.connections[db_path] = conn
            
            return conn
        except Exception as e:
            logger.error(f"获取数据库连接失败: {str(e)}")
            return None
    
    def close_connection(self, task_name: str = None, db_path: str = None) -> bool:
        """关闭数据库连接
        
        Args:
            task_name: 任务名称
            db_path: 可选的数据库路径，将覆盖任务名称
            
        Returns:
            是否成功
        """
        try:
            # 确定数据库路径
            if db_path is None and task_name is not None:
                db_path = self.get_task_database_path(task_name)
            
            if db_path is None:
                return False
            
            # 检查连接缓存
            if db_path in self.connections and self.connections[db_path] is not None:
                self.connections[db_path].close()
                del self.connections[db_path]
                return True
            
            return True
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {str(e)}")
            return False
    
    def get_table_list(self, task_name: str = None, db_path: str = None) -> List[str]:
        """获取数据库表列表
        
        Args:
            task_name: 任务名称
            db_path: 可选的数据库路径，将覆盖任务名称
            
        Returns:
            表名列表
        """
        try:
            conn = self.get_db_connection(task_name, db_path)
            if conn is None:
                return []
            
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            return tables
        except Exception as e:
            logger.error(f"获取表列表失败: {str(e)}")
            return []
    
    def execute_query(self, query: str, params: tuple = None, task_name: str = None, db_path: str = None) -> List[Dict[str, Any]]:
        """执行查询
        
        Args:
            query: SQL查询
            params: 查询参数
            task_name: 任务名称
            db_path: 可选的数据库路径，将覆盖任务名称
            
        Returns:
            查询结果
        """
        try:
            conn = self.get_db_connection(task_name, db_path)
            if conn is None:
                return []
            
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = []
            rows = cursor.fetchall()
            for row in rows:
                result.append({k: row[k] for k in row.keys()})
            
            cursor.close()
            return result
        except Exception as e:
            logger.error(f"执行查询失败: {str(e)}")
            return []
    
    def execute_update(self, query: str, params: tuple = None, task_name: str = None, db_path: str = None) -> int:
        """执行更新
        
        Args:
            query: SQL更新
            params: 更新参数
            task_name: 任务名称
            db_path: 可选的数据库路径，将覆盖任务名称
            
        Returns:
            影响行数
        """
        try:
            conn = self.get_db_connection(task_name, db_path)
            if conn is None:
                return 0
            
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            affected_rows = cursor.rowcount
            cursor.close()
            
            return affected_rows
        except Exception as e:
            logger.error(f"执行更新失败: {str(e)}")
            return 0
    
    def close_all_connections(self) -> bool:
        """关闭所有数据库连接
        
        Returns:
            是否成功
        """
        try:
            for db_path, conn in self.connections.items():
                if conn is not None:
                    conn.close()
            
            self.connections.clear()
            return True
        except Exception as e:
            logger.error(f"关闭所有连接失败: {str(e)}")
            return False
