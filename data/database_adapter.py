import sqlite3
import pyodbc
import threading
import logging
import os
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from core.base_classes import SystemModule
from core.interfaces import IDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("database.log"), logging.StreamHandler()]
)
logger = logging.getLogger('database_manager')

class DatabaseAdapter:
    """数据库适配器基类，定义通用接口"""
    
    def connect(self):
        """建立数据库连接"""
        raise NotImplementedError
    
    def disconnect(self):
        """断开数据库连接"""
        raise NotImplementedError
    
    def execute(self, query: str, params=None) -> int:
        """执行SQL语句并返回影响的行数"""
        raise NotImplementedError
    
    def executemany(self, query: str, params_list: List) -> int:
        """执行多条SQL语句并返回影响的行数"""
        raise NotImplementedError
    
    def fetch_one(self, query: str, params=None) -> Optional[Dict[str, Any]]:
        """执行查询并返回单条记录"""
        raise NotImplementedError
    
    def fetch_all(self, query: str, params=None) -> List[Dict[str, Any]]:
        """执行查询并返回所有记录"""
        raise NotImplementedError
    
    def commit(self):
        """提交事务"""
        raise NotImplementedError
    
    def rollback(self):
        """回滚事务"""
        raise NotImplementedError
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表结构信息"""
        raise NotImplementedError


class SQLiteAdapter(DatabaseAdapter):
    """SQLite数据库适配器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.connected = False
    
    def connect(self):
        if not self.connected:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connected = True
        return self.connection
    
    def disconnect(self):
        if self.connected and self.connection:
            self.connection.close()
            self.connected = False
    
    def execute(self, query: str, params=None) -> int:
        conn = self.connect()
        try:
            cursor = conn.execute(query, params or ())
            return cursor.rowcount
        except Exception as e:
            logger.error(f"SQLite执行错误: {str(e)}, Query: {query}")
            raise
    
    def executemany(self, query: str, params_list: List) -> int:
        conn = self.connect()
        try:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
        except Exception as e:
            logger.error(f"SQLite批量执行错误: {str(e)}, Query: {query}")
            raise
    
    def fetch_one(self, query: str, params=None) -> Optional[Dict[str, Any]]:
        conn = self.connect()
        try:
            cursor = conn.execute(query, params or ())
            row = cursor.fetchone()
            if row:
                return {key: row[key] for key in row.keys()}
            return None
        except Exception as e:
            logger.error(f"SQLite查询错误: {str(e)}, Query: {query}")
            raise
    
    def fetch_all(self, query: str, params=None) -> List[Dict[str, Any]]:
        conn = self.connect()
        try:
            cursor = conn.execute(query, params or ())
            rows = cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
        except Exception as e:
            logger.error(f"SQLite查询错误: {str(e)}, Query: {query}")
            raise
    
    def commit(self):
        if self.connected and self.connection:
            self.connection.commit()
    
    def rollback(self):
        if self.connected and self.connection:
            self.connection.rollback()
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        query = f"PRAGMA table_info({table_name})"
        return self.fetch_all(query)


class AccessAdapter(DatabaseAdapter):
    """Access数据库适配器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.connected = False
        
        # 确保数据库文件存在
        if not os.path.exists(db_path):
            self._create_empty_access_db()
    
    def _create_empty_access_db(self):
        """创建空的Access数据库文件"""
        # 此方法在需要时实现，可以使用pyodbc或其他工具创建空数据库
        # 如果Python环境中没有直接创建Access数据库的方法，可以使用预先创建的模板文件
        logger.info(f"创建新的Access数据库: {self.db_path}")
        try:
            # 使用预先创建的空模板文件
            template_path = os.path.join(os.path.dirname(__file__), "templates", "empty.accdb")
            if os.path.exists(template_path):
                import shutil
                shutil.copy(template_path, self.db_path)
                logger.info(f"从模板创建Access数据库成功: {self.db_path}")
            else:
                logger.warning(f"Access数据库模板不存在: {template_path}")
        except Exception as e:
            logger.error(f"创建Access数据库失败: {str(e)}")
            raise
    
    def connect(self):
        if not self.connected:
            try:
                # 使用ODBC驱动连接Access
                conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={self.db_path};'
                self.connection = pyodbc.connect(conn_str)
                self.connected = True
                logger.info(f"已连接到Access数据库: {self.db_path}")
            except Exception as e:
                logger.error(f"连接Access数据库失败: {str(e)}")
                raise
        return self.connection
    
    def disconnect(self):
        if self.connected and self.connection:
            self.connection.close()
            self.connected = False
            logger.info("已断开Access数据库连接")
    
    def execute(self, query: str, params=None) -> int:
        conn = self.connect()
        try:
            # 转换SQLite查询为Access兼容的查询
            query = self._convert_query_to_access(query)
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.commit()  # Access需要提交才能保存更改
            return cursor.rowcount
        except Exception as e:
            self.rollback()
            logger.error(f"Access执行错误: {str(e)}, Query: {query}")
            raise
    
    def executemany(self, query: str, params_list: List) -> int:
        conn = self.connect()
        try:
            # 转换SQLite查询为Access兼容的查询
            query = self._convert_query_to_access(query)
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            self.commit()  # Access需要提交才能保存更改
            return cursor.rowcount
        except Exception as e:
            self.rollback()
            logger.error(f"Access批量执行错误: {str(e)}, Query: {query}")
            raise
    
    def fetch_one(self, query: str, params=None) -> Optional[Dict[str, Any]]:
        conn = self.connect()
        try:
            # 转换SQLite查询为Access兼容的查询
            query = self._convert_query_to_access(query)
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # 获取列名
            columns = [column[0] for column in cursor.description]
            
            row = cursor.fetchone()
            if row:
                # 将元组转换为字典
                return {columns[i]: row[i] for i in range(len(columns))}
            return None
        except Exception as e:
            logger.error(f"Access查询错误: {str(e)}, Query: {query}")
            raise
    
    def fetch_all(self, query: str, params=None) -> List[Dict[str, Any]]:
        conn = self.connect()
        try:
            # 转换SQLite查询为Access兼容的查询
            query = self._convert_query_to_access(query)
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # 获取列名
            columns = [column[0] for column in cursor.description]
            
            result = []
            for row in cursor.fetchall():
                # 将每行元组转换为字典
                result.append({columns[i]: row[i] for i in range(len(columns))})
            return result
        except Exception as e:
            logger.error(f"Access查询错误: {str(e)}, Query: {query}")
            raise
    
    def commit(self):
        if self.connected and self.connection:
            self.connection.commit()
    
    def rollback(self):
        if self.connected and self.connection:
            self.connection.rollback()
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        # Access不支持PRAGMA，使用系统表获取结构信息
        query = f"""
        SELECT 
            column_name as name, 
            data_type as type,
            character_maximum_length as length,
            is_nullable
        FROM 
            information_schema.columns
        WHERE 
            table_name = '{table_name}'
        """
        try:
            return self.fetch_all(query)
        except:
            # 如果上述方法失败，尝试另一种方式
            try:
                # 通过查询数据获取列信息
                query = f"SELECT TOP 1 * FROM [{table_name}]"
                conn = self.connect()
                cursor = conn.cursor()
                cursor.execute(query)
                
                columns = []
                for column in cursor.description:
                    columns.append({
                        "name": column[0],
                        "type": self._get_type_name(column[1]),
                        "notnull": 0,  # 默认允许NULL
                        "dflt_value": None
                    })
                return columns
            except Exception as e:
                logger.error(f"获取Access表结构失败: {str(e)}")
                return []
    
    def _get_type_name(self, type_code) -> str:
        """根据类型代码返回类型名称"""
        # pyodbc类型映射
        types = {
            pyodbc.SQL_CHAR: "TEXT",
            pyodbc.SQL_VARCHAR: "TEXT",
            pyodbc.SQL_LONGVARCHAR: "TEXT",
            pyodbc.SQL_WCHAR: "TEXT",
            pyodbc.SQL_WVARCHAR: "TEXT",
            pyodbc.SQL_WLONGVARCHAR: "TEXT",
            pyodbc.SQL_DECIMAL: "NUMERIC",
            pyodbc.SQL_NUMERIC: "NUMERIC",
            pyodbc.SQL_SMALLINT: "INTEGER",
            pyodbc.SQL_INTEGER: "INTEGER",
            pyodbc.SQL_REAL: "REAL",
            pyodbc.SQL_FLOAT: "REAL",
            pyodbc.SQL_DOUBLE: "REAL",
            pyodbc.SQL_BIT: "INTEGER",
            pyodbc.SQL_TINYINT: "INTEGER",
            pyodbc.SQL_BIGINT: "INTEGER",
            pyodbc.SQL_BINARY: "BLOB",
            pyodbc.SQL_VARBINARY: "BLOB",
            pyodbc.SQL_LONGVARBINARY: "BLOB",
            pyodbc.SQL_TYPE_DATE: "DATE",
            pyodbc.SQL_TYPE_TIME: "TIME",
            pyodbc.SQL_TYPE_TIMESTAMP: "TIMESTAMP"
        }
        return types.get(type_code, "TEXT")
    
    def _convert_query_to_access(self, query: str) -> str:
        """将SQLite SQL转换为Access兼容的SQL"""
        # 替换SQLite特定语法
        query = query.replace("PRAGMA foreign_keys = ON", "")
        query = query.replace("AUTOINCREMENT", "AUTO_INCREMENT")
        
        # SQLite使用单引号，Access通常使用方括号标识表和列名
        # 这里的转换可能需要更复杂的SQL解析器，这只是简单示例
        
        return query
