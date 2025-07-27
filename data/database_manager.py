import sqlite3
import threading
import logging
import os
import json
import time
import sys

# 添加系统路径，确保能导入core模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base_classes import SystemModule
from core.interfaces import IDatabaseManager
from typing import Any, Dict, List, Optional, Tuple, Union

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("database.log"), logging.StreamHandler()]
)
logger = logging.getLogger('database_manager')

class DatabaseManager(SystemModule, IDatabaseManager):
    """优化的SQLite数据库管理器，支持连接池和事务"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "automation.db", *args, **kwargs):
        """单例模式实现"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path: str = "automation.db", pool_size: int = 5):
        """初始化数据库管理器和连接池
        
        Args:
            db_path: SQLite数据库文件路径
            pool_size: 连接池大小
        """
        # 继承父类初始化
        super().__init__("DatabaseManager", "2.0.0")
        
        # 如果已初始化，直接返回
        if self._initialized:
            return
            
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = []
        self.conn_lock = threading.Lock()
        self.schema_version = 1
        
        # 确保数据库路径有.db扩展名
        if not self.db_path.lower().endswith('.db'):
            self.db_path += '.db'
        
        # 检查数据库是否存在
        db_exists = os.path.exists(self.db_path)
        
        # 初始化连接池
        self._init_connection_pool()
        
        # 如果数据库不存在，创建架构
        if not db_exists:
            self._create_schema()
        else:
            # 验证并在需要时升级架构
            self._verify_schema()
            
        self._initialized = True
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def _init_connection_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 返回类似字典的行
            conn.execute("PRAGMA foreign_keys = ON")  # 启用外键支持
            self.connections.append({"connection": conn, "in_use": False})
        logger.debug(f"连接池初始化完成，大小: {self.pool_size}")
    
    def _get_connection(self):
        """从连接池获取可用连接"""
        with self.conn_lock:
            for conn_info in self.connections:
                if not conn_info["in_use"]:
                    conn_info["in_use"] = True
                    return conn_info
            
            # 如果所有连接都在使用中，创建临时连接
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            temp_conn_info = {"connection": conn, "in_use": True, "temporary": True}
            self.connections.append(temp_conn_info)
            logger.warning("所有连接都在使用中，创建临时连接")
            return temp_conn_info
    
    def _release_connection(self, conn_info):
        """释放连接回连接池"""
        with self.conn_lock:
            if conn_info.get("temporary", False):
                conn_info["connection"].close()
                self.connections.remove(conn_info)
                logger.debug("关闭并移除临时连接")
            else:
                conn_info["in_use"] = False
    
    def _create_schema(self):
        """创建数据库架构"""
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            conn.executescript(self._get_schema_creation_script())
            conn.commit()
            logger.info("成功创建数据库架构")
        except Exception as e:
            conn.rollback()
            logger.error(f"创建数据库架构错误: {str(e)}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def _get_schema_creation_script(self):
        """获取创建架构的SQL脚本"""
        return """
        -- 架构版本表
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY
        );
        
        -- 应用表
        CREATE TABLE apps (
            app_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            package_name TEXT,
            priority INTEGER DEFAULT 5,
            time_slice INTEGER DEFAULT 3600,  -- 默认1小时
            daily_limit INTEGER DEFAULT 7200, -- 默认2小时
            reset_time TEXT DEFAULT '04:00',  -- 默认凌晨4点
            status TEXT DEFAULT 'inactive',
            config TEXT,                      -- JSON配置
            last_update INTEGER
        );
        
        -- 账号表
        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            app_id TEXT NOT NULL,
            username TEXT,
            password TEXT,
            login_type TEXT DEFAULT 'default',
            last_login_time INTEGER,
            total_runtime INTEGER DEFAULT 0,
            daily_runtime INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            extra_data TEXT,                  -- JSON数据
            FOREIGN KEY (app_id) REFERENCES apps(app_id)
        );
        
        -- 任务表
        CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            app_id TEXT NOT NULL,
            name TEXT NOT NULL,
            parent_id TEXT,                  -- 父任务ID
            type TEXT DEFAULT 'daily',       -- daily, weekly等
            priority INTEGER DEFAULT 5,
            max_retries INTEGER DEFAULT 3,
            timeout INTEGER DEFAULT 300,     -- 默认5分钟
            description TEXT,
            config TEXT,                     -- JSON配置
            handler_class TEXT,              -- Python类名
            enabled INTEGER DEFAULT 1,       -- 布尔值
            FOREIGN KEY (app_id) REFERENCES apps(app_id),
            FOREIGN KEY (parent_id) REFERENCES tasks(task_id)
        );
        
        -- 任务状态表
        CREATE TABLE task_status (
            status_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            completed INTEGER DEFAULT 0,       -- 布尔值
            completion_time INTEGER,           -- 时间戳
            last_run_time INTEGER,             -- 时间戳
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            execution_data TEXT,               -- JSON数据
            FOREIGN KEY (account_id) REFERENCES accounts(account_id),
            FOREIGN KEY (task_id) REFERENCES tasks(task_id),
            UNIQUE(account_id, task_id)
        );
        
        -- 识别状态表
        CREATE TABLE recognition_states (
            state_id TEXT PRIMARY KEY,
            app_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,              -- text, image
            config TEXT NOT NULL,            -- JSON配置
            FOREIGN KEY (app_id) REFERENCES apps(app_id)
        );
        
        -- 状态转换动作表
        CREATE TABLE actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_state TEXT NOT NULL,
            to_state TEXT NOT NULL,
            name TEXT NOT NULL,
            function_name TEXT NOT NULL,
            params TEXT,                     -- JSON参数
            FOREIGN KEY (from_state) REFERENCES recognition_states(state_id),
            FOREIGN KEY (to_state) REFERENCES recognition_states(state_id)
        );
        
        -- 系统设置表
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT
        );
        
        -- 活动日志表
        CREATE TABLE activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            app_id TEXT,
            account_id TEXT,
            task_id TEXT,
            action TEXT,
            status TEXT,
            details TEXT
        );
        
        -- 插入架构版本
        INSERT INTO schema_version (version) VALUES (1);
        
        -- 创建索引
        CREATE INDEX idx_task_status_account ON task_status(account_id);
        CREATE INDEX idx_task_status_task ON task_status(task_id);
        CREATE INDEX idx_tasks_app ON tasks(app_id);
        CREATE INDEX idx_accounts_app ON accounts(app_id);
        CREATE INDEX idx_activity_log_timestamp ON activity_log(timestamp);
        """
    
    def _verify_schema(self):
        """验证架构版本并在需要时升级"""
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            # 检查schema_version表是否存在
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
            if not cursor.fetchone():
                logger.warning("架构版本表不存在，创建架构")
                self._release_connection(conn_info)
                self._create_schema()
                return
                
            # 获取当前架构版本
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            current_version = row['version'] if row else 0
            
            # 如果需要，升级架构
            if current_version < self.schema_version:
                self._upgrade_schema(conn, current_version)
                
        except Exception as e:
            logger.error(f"验证架构错误: {str(e)}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def _upgrade_schema(self, conn, current_version):
        """将数据库架构升级到最新版本"""
        try:
            # 逐步应用升级
            if current_version < 1:
                # 升级到版本1
                logger.info("升级架构到版本1")
                # 架构创建脚本会在这里
            
            # 更新架构版本
            conn.execute("UPDATE schema_version SET version = ?", (self.schema_version,))
            conn.commit()
            logger.info(f"架构升级到版本 {self.schema_version}")
        except Exception as e:
            conn.rollback()
            logger.error(f"架构升级失败: {str(e)}")
            raise
    
    def execute(self, query: str, params: tuple = None) -> int:
        """执行查询并返回受影响的行数
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            受影响的行数
        """
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, params or ())
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"查询执行错误: {str(e)}, 查询: {query}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def executemany(self, query: str, params_list: List[tuple]) -> int:
        """使用多个参数集执行查询
        
        Args:
            query: SQL查询
            params_list: 参数元组列表
            
        Returns:
            受影响的行数
        """
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"批量查询执行错误: {str(e)}, 查询: {query}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """执行查询并获取一行
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            包含行数据的字典或None
        """
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, params or ())
            row = cursor.fetchone()
            
            if row:
                return {key: row[key] for key in row.keys()}
            return None
            
        except Exception as e:
            logger.error(f"查询执行错误: {str(e)}, 查询: {query}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并获取所有行
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            包含行数据的字典列表
        """
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, params or ())
            rows = cursor.fetchall()
            
            return [{key: row[key] for key in row.keys()} for row in rows]
            
        except Exception as e:
            logger.error(f"查询执行错误: {str(e)}, 查询: {query}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """向表中插入数据
        
        Args:
            table: 表名
            data: 列名和值的字典
            
        Returns:
            插入行的行ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = tuple(data.values())
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            logger.error(f"插入错误: {str(e)}, 表: {table}, 数据: {data}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def update(self, table: str, data: Dict[str, Any], condition: str, condition_params: tuple = None) -> int:
        """更新表中的数据
        
        Args:
            table: 表名
            data: 要更新的列名和值的字典
            condition: WHERE子句
            condition_params: 条件参数
            
        Returns:
            受影响的行数
        """
        set_clause = ', '.join([f"{column} = ?" for column in data.keys()])
        values = tuple(data.values()) + (condition_params or ())
        
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"更新错误: {str(e)}, 表: {table}, 条件: {condition}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def delete(self, table: str, condition: str, condition_params: tuple = None) -> int:
        """从表中删除数据
        
        Args:
            table: 表名
            condition: WHERE子句
            condition_params: 条件参数
            
        Returns:
            受影响的行数
        """
        query = f"DELETE FROM {table} WHERE {condition}"
        
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, condition_params or ())
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"删除错误: {str(e)}, 表: {table}, 条件: {condition}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def transaction(self):
        """返回事务上下文管理器"""
        return Transaction(self)
    
    def exists(self, table: str, condition: str, condition_params: tuple = None) -> bool:
        """检查表中是否存在记录
        
        Args:
            table: 表名
            condition: WHERE子句
            condition_params: 条件参数
            
        Returns:
            如果记录存在则返回True，否则返回False
        """
        query = f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1"
        
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, condition_params or ())
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"存在性检查错误: {str(e)}, 表: {table}, 条件: {condition}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def count(self, table: str, condition: str = "1=1", condition_params: tuple = None) -> int:
        """计算表中的记录数
        
        Args:
            table: 表名
            condition: WHERE子句
            condition_params: 条件参数
            
        Returns:
            记录数
        """
        query = f"SELECT COUNT(*) as count FROM {table} WHERE {condition}"
        
        conn_info = self._get_connection()
        conn = conn_info["connection"]
        
        try:
            cursor = conn.execute(query, condition_params or ())
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            logger.error(f"计数错误: {str(e)}, 表: {table}, 条件: {condition}")
            raise
        finally:
            self._release_connection(conn_info)
    
    def close(self):
        """关闭所有数据库连接"""
        with self.conn_lock:
            for conn_info in self.connections:
                try:
                    conn_info["connection"].close()
                except Exception as e:
                    logger.error(f"关闭连接错误: {str(e)}")
            
            self.connections = []
            logger.info("所有数据库连接已关闭")
    
    def backup(self, backup_path: str) -> bool:
        """创建数据库备份
        
        Args:
            backup_path: 保存备份的路径
            
        Returns:
            如果成功则返回True，否则返回False
        """
        try:
            # 创建用于备份的新连接
            source = sqlite3.connect(self.db_path)
            target = sqlite3.connect(backup_path)
            
            # 备份期间锁定数据库
            with self.conn_lock:
                source.backup(target)
            
            # 关闭连接
            target.close()
            source.close()
            
            logger.info(f"数据库备份创建成功: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"数据库备份失败: {str(e)}")
            return False
    
    def log_activity(self, action: str, status: str, app_id: str = None, account_id: str = None, task_id: str = None, details: str = None):
        """记录活动
        
        Args:
            action: 执行的操作
            status: 操作状态（成功、失败等）
            app_id: 应用ID
            account_id: 账号ID
            task_id: 任务ID
            details: 附加详情
        """
        try:
            timestamp = int(time.time())
            
            self.insert('activity_log', {
                'timestamp': timestamp,
                'app_id': app_id,
                'account_id': account_id,
                'task_id': task_id,
                'action': action,
                'status': status,
                'details': details
            })
        except Exception as e:
            logger.error(f"记录活动失败: {str(e)}")
    
    def export_to_task_db(self, table, conditions, task_name, task_table=None):
        """导出数据到任务数据库
        Args:
            table: 源表名
            conditions: WHERE条件
            task_name: 任务名称
            task_table: 目标表名，为None则与源表同名
        Returns:
            是否成功
        """
        try:
            # 确定目标表名
            if task_table is None:
                task_table = table
                
            # 构建任务数据库路径
            task_db_path = f"tasks/{task_name}/db/{task_name}.db"
            
            # 确保任务数据库目录存在
            os.makedirs(os.path.dirname(task_db_path), exist_ok=True)
            
            # 查询数据
            query = f"SELECT * FROM {table}"
            if conditions:
                query += f" WHERE {conditions}"
                
            rows = self.fetch_all(query)
            
            if not rows:
                return True  # 没有数据需要导出
                
            # 连接任务数据库
            task_conn = sqlite3.connect(task_db_path)
            
            # 创建表（如果不存在）
            # 从第一行数据推断列结构
            columns = list(rows[0].keys())
            col_defs = []
            
            # 使用简单类型推断
            for col in columns:
                value = rows[0][col]
                if isinstance(value, int):
                    col_defs.append(f"{col} INTEGER")
                elif isinstance(value, float):
                    col_defs.append(f"{col} REAL")
                else:
                    col_defs.append(f"{col} TEXT")
                    
            create_sql = f"CREATE TABLE IF NOT EXISTS {task_table} ({', '.join(col_defs)})"
            task_conn.execute(create_sql)
            
            # 导入数据
            for row in rows:
                placeholders = ", ".join(["?"] * len(columns))
                values = [row[col] for col in columns]
                
                insert_sql = f"INSERT INTO {task_table} ({', '.join(columns)}) VALUES ({placeholders})"
                task_conn.execute(insert_sql, values)
                
            task_conn.commit()
            task_conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"导出到任务数据库失败: {str(e)}")
            return False
    
    def export_to_sql(self, output_path: str) -> bool:
        """导出完整数据库到可读的SQL文件
        
        Args:
            output_path: SQL输出文件路径
            
        Returns:
            如果成功则返回True，否则返回False
        """
        try:
            # 获取所有表名
            conn_info = self._get_connection()
            conn = conn_info["connection"]
            
            try:
                # 获取所有表名
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = [row['name'] for row in cursor.fetchall()]
                
                # 打开输出文件
                with open(output_path, 'w', encoding='utf-8') as sql_file:
                    # 写入头部信息
                    sql_file.write("-- 数据库导出\n")
                    sql_file.write(f"-- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    sql_file.write(f"-- 源数据库: {self.db_path}\n\n")
                    
                    # 处理每个表
                    for table in tables:
                        # 写入表创建语句
                        cursor = conn.execute(f"SELECT sql FROM sqlite_master WHERE name = '{table}'")
                        create_stmt = cursor.fetchone()['sql']
                        sql_file.write(f"{create_stmt};\n\n")
                        
                        # 获取表数据
                        cursor = conn.execute(f"SELECT * FROM {table}")
                        rows = cursor.fetchall()
                        
                        # 写入表数据
                        if rows:
                            sql_file.write(f"-- 表 {table} 的数据\n")
                            for row in rows:
                                columns = row.keys()
                                col_str = ', '.join(columns)
                                # 格式化值，字符串加引号
                                values = []
                                for col in columns:
                                    val = row[col]
                                    if val is None:
                                        values.append('NULL')
                                    elif isinstance(val, (int, float)):
                                        values.append(str(val))
                                    else:
                                        # 转义单引号
                                        val_str = str(val).replace("'", "''")
                                        values.append(f"'{val_str}'")
                                val_str = ', '.join(values)
                                
                                sql_file.write(f"INSERT INTO {table} ({col_str}) VALUES ({val_str});\n")
                            sql_file.write("\n")
                
                logger.info(f"数据库成功导出到SQL文件: {output_path}")
                return True
                
            except Exception as e:
                logger.error(f"导出SQL文件时发生错误: {str(e)}")
                return False
            finally:
                self._release_connection(conn_info)
                
        except Exception as e:
            logger.error(f"导出到SQL失败: {str(e)}")
            return False
    
    def import_from_sql(self, sql_file_path: str) -> bool:
        """从SQL文件导入数据
        
        Args:
            sql_file_path: SQL文件路径
            
        Returns:
            如果成功则返回True，否则返回False
        """
        try:
            # 读取SQL文件
            with open(sql_file_path, 'r', encoding='utf-8') as sql_file:
                sql_content = sql_file.read()
            
            # 分割SQL语句
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            # 获取连接
            conn_info = self._get_connection()
            conn = conn_info["connection"]
            
            try:
                # 执行每条SQL语句
                for stmt in statements:
                    if stmt.strip() and not stmt.startswith('--'):
                        conn.execute(stmt)
                
                # 提交更改
                conn.commit()
                logger.info(f"成功从SQL文件导入数据: {sql_file_path}")
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"导入SQL文件时发生错误: {str(e)}")
                return False
            finally:
                self._release_connection(conn_info)
                
        except Exception as e:
            logger.error(f"从SQL导入失败: {str(e)}")
            return False
    
    def initialize(self) -> bool:
        """初始化模块
        
        Returns:
            如果初始化成功则返回True，否则返回False
        """
        # 模块已在__init__中初始化
        return self._initialized
        
    def shutdown(self) -> bool:
        """关闭模块
        
        Returns:
            如果关闭成功则返回True，否则返回False
        """
        try:
            self.close()
            return True
        except Exception as e:
            logger.error(f"关闭数据库管理器失败: {str(e)}")
            return False
            
    @property
    def is_initialized(self) -> bool:
        """检查模块是否已初始化
        
        Returns:
            如果模块已初始化则返回True，否则返回False
        """
        return self._initialized

    def get_table_list(self) -> List[str]:
        """获取数据库中所有表的列表

        Returns:
            数据库中所有表名的列表
        """
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            tables = self.fetch_all(query)
            return [table['name'] for table in tables]
        except Exception as e:
            logger.error(f"查询表列表失败: {str(e)}")
            return []


class Transaction:
    """数据库事务上下文管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化事务管理器
        
        Args:
            db_manager: DatabaseManager实例
        """
        self.db_manager = db_manager
        self.conn_info = None
        self.conn = None
    
    def __enter__(self):
        """开始事务"""
        self.conn_info = self.db_manager._get_connection()
        self.conn = self.conn_info["connection"]
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """结束事务"""
        if exc_type is None:
            # 没有异常，提交事务
            self.conn.commit()
        else:
            # 发生异常，回滚事务
            self.conn.rollback()
            logger.error(f"事务回滚，原因: {str(exc_val)}")
        
        # 释放连接
        self.db_manager._release_connection(self.conn_info)
        return False  # 不抑制异常
    
    def execute(self, query: str, params: tuple = None) -> int:
        """在事务中执行查询
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            受影响的行数
        """
        cursor = self.conn.execute(query, params or ())
        return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """在事务中执行查询并获取一行
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            包含行数据的字典或None
        """
        cursor = self.conn.execute(query, params or ())
        row = cursor.fetchone()
        
        if row:
            return {key: row[key] for key in row.keys()}
        return None
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """在事务中执行查询并获取所有行
        
        Args:
            query: SQL查询
            params: 查询参数
            
        Returns:
            包含行数据的字典列表
        """
        cursor = self.conn.execute(query, params or ())
        rows = cursor.fetchall()
        
        return [{key: row[key] for key in row.keys()} for row in rows]
    
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """在事务中向表中插入数据
        
        Args:
            table: 表名
            data: 列名和值的字典
            
        Returns:
            插入行的行ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = tuple(data.values())
        
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        cursor = self.conn.execute(query, values)
        return cursor.lastrowid
