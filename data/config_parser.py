"""
核心配置解析器
用于解析简洁格式的配置文件并操作系统数据库
支持创建表、添加记录、删除记录、查询等操作
"""
import importlib
import os
import re
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Tuple, Union
from core.interfaces import IConfigParserPlugin

class ConfigParser:
    """配置解析器，处理简洁格式的配置文件并操作系统数据库"""
    
    def __init__(self, db_manager=None):
        """初始化配置解析器
        
        Args:
            db_manager: 数据库管理器，如果为None则创建临时连接
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger("ConfigParser")
        self.current_db_path = None
        self.plugins = {}  # 存储插件实
        
        # 定义系统表的列定义
        self.system_tables = {
            "accounts": {
                "account_id": "TEXT PRIMARY KEY",
                "app_id": "TEXT NOT NULL",
                "username": "TEXT",
                "password": "TEXT",
                "login_type": "TEXT DEFAULT 'default'",
                "last_login_time": "INTEGER",
                "total_runtime": "INTEGER DEFAULT 0",
                "daily_runtime": "INTEGER DEFAULT 0",
                "status": "TEXT DEFAULT 'active'",
                "extra_data": "TEXT"
            },
            "apps": {
                "app_id": "TEXT PRIMARY KEY",
                "name": "TEXT NOT NULL",
                "package_name": "TEXT",
                "priority": "INTEGER DEFAULT 5",
                "time_slice": "INTEGER DEFAULT 3600",
                "daily_limit": "INTEGER DEFAULT 7200",
                "reset_time": "TEXT DEFAULT '04:00'",
                "status": "TEXT DEFAULT 'inactive'",
                "config": "TEXT",
                "last_update": "INTEGER"
            },
            "tasks": {
                "task_id": "TEXT PRIMARY KEY",
                "app_id": "TEXT NOT NULL",
                "name": "TEXT NOT NULL",
                "parent_id": "TEXT",
                "type": "TEXT DEFAULT 'daily'",
                "priority": "INTEGER DEFAULT 5",
                "max_retries": "INTEGER DEFAULT 3",
                "timeout": "INTEGER DEFAULT 300",
                "description": "TEXT",
                "config": "TEXT",
                "handler_class": "TEXT",
                "enabled": "INTEGER DEFAULT 1"
            },
            "settings": {
                "key": "TEXT PRIMARY KEY",
                "value": "TEXT",
                "description": "TEXT"
            }
        }
    
    def parse_file(self, file_path: str, db_path: str = None) -> List[Dict[str, Any]]:
        """解析配置文件并执行操作
        
        Args:
            file_path: 配置文件路径
            db_path: 可选的数据库路径，默认使用系统数据库
            
        Returns:
            操作结果列表
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.logger.error(f"配置文件不存在: {file_path}")
                return [{"status": "error", "message": f"配置文件不存在: {file_path}"}]
                
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # 解析并执行命令
            return self.parse_and_execute(content, db_path)
            
        except Exception as e:
            self.logger.error(f"解析配置文件失败: {str(e)}")
            return [{"status": "error", "message": f"解析配置文件失败: {str(e)}"}]
    
    def parse_and_execute(self, content: str, db_path: str = None) -> List[Dict[str, Any]]:
        """解析配置内容并执行操作
        
        Args:
            content: 配置内容
            db_path: 可选的数据库路径，默认使用系统数据库
            
        Returns:
            操作结果列表
        """
        try:
            self.current_db_path = db_path
            
            # 初始化结果列表
            results = []
            
            # 处理多行配置
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 解析配置行
                result = self._parse_command(line)
                if result:
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"解析并执行配置失败: {str(e)}")
            return [{"status": "error", "message": f"解析并执行配置失败: {str(e)}"}]
        finally:
            # 清除临时数据库连接
            if hasattr(self, 'temp_conn') and self.temp_conn is not None:
                self.temp_conn.close()
                self.temp_conn = None
    
    def _get_db_connection(self):
        """获取数据库连接
        
        Returns:
            数据库连接和游标
        """
        if self.db_manager is not None:
            # 使用系统数据库管理器
            conn_info = self.db_manager._get_connection()
            conn = conn_info["connection"]
            cursor = conn.cursor()
            return conn, cursor, conn_info
        else:
            # 创建临时连接
            if not hasattr(self, 'temp_conn') or self.temp_conn is None:
                db_path = self.current_db_path or "automation.db"
                self.temp_conn = sqlite3.connect(db_path)
                self.temp_conn.row_factory = sqlite3.Row
            return self.temp_conn, self.temp_conn.cursor(), None
    
    def _release_connection(self, conn_info):
        """释放数据库连接
        
        Args:
            conn_info: 连接信息
        """
        if self.db_manager is not None and conn_info is not None:
            self.db_manager._release_connection(conn_info)
    
    def _parse_command(self, command: str) -> Dict[str, Any]:
        """解析单行命令
        
        Args:
            command: 配置命令
            
        Returns:
            操作结果
        """
        # 提取命令类型和表名
        match = re.match(r'(\w+)\[([^\]]+)\](.*)', command)
        if not match:
            return {"status": "error", "message": f"无效的命令格式: {command}"}
            
        cmd_type = match.group(1).lower()
        table_name = match.group(2)
        params_str = match.group(3).strip()
        
        # 根据命令类型执行不同操作
        if cmd_type == 'add':
            return self._handle_add(table_name, params_str)
        elif cmd_type == 'del' or cmd_type == 'delete':
            return self._handle_delete(table_name, params_str)
        elif cmd_type == 'update':
            return self._handle_update(table_name, params_str)
        elif cmd_type == 'create':
            return self._handle_create(table_name, params_str)
        elif cmd_type == 'drop':
            return self._handle_drop(table_name)
        elif cmd_type == 'query':
            return self._handle_query(table_name, params_str)
        elif cmd_type == 'list':
            return self._handle_list(table_name)
        else:
            return {"status": "error", "message": f"未知命令: {cmd_type}"}
    
    def _parse_params(self, params_str: str) -> Dict[str, str]:
        """解析参数字符串
        
        Args:
            params_str: 参数字符串，格式为 "键1:值1; 键2:值2;..."
            
        Returns:
            参数字典
        """
        params = {}
        if not params_str:
            return params
            
        # 按分号分割参数
        parts = params_str.split(';')
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # 按冒号分割键值对
            if ':' in part:
                key, value = part.split(':', 1)
                params[key.strip()] = value.strip()
            else:
                # 没有冒号，视为值本身
                params[part] = ''
                
        return params
    
    def _handle_add(self, table_name: str, params_str: str) -> Dict[str, Any]:
        """处理添加记录操作
        
        Args:
            table_name: 表名
            params_str: 参数字符串
            
        Returns:
            操作结果
        """
        try:
            # 解析参数
            params = self._parse_params(params_str)
            if not params:
                return {"status": "error", "message": "缺少参数"}
                
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    # 如果是系统表，尝试创建
                    if table_name in self.system_tables:
                        self._create_system_table(table_name, cursor)
                    else:
                        return {"status": "error", "message": f"表不存在: {table_name}"}
                
                # 构建INSERT语句
                columns = ", ".join(params.keys())
                placeholders = ", ".join(["?" for _ in params])
                values = list(params.values())
                
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"已向表 {table_name} 添加记录", 
                    "operation": "add",
                    "table": table_name,
                    "record": params
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"添加记录失败: {str(e)}")
            return {"status": "error", "message": f"添加记录失败: {str(e)}"}
    
    def _handle_delete(self, table_name: str, params_str: str) -> Dict[str, Any]:
        """处理删除记录操作
        
        Args:
            table_name: 表名
            params_str: 参数字符串
            
        Returns:
            操作结果
        """
        try:
            # 解析参数
            params = self._parse_params(params_str)
            
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    return {"status": "error", "message": f"表不存在: {table_name}"}
                
                # 构建WHERE子句
                where_clause = " AND ".join([f"{k} = ?" for k in params.keys()])
                values = list(params.values())
                
                if where_clause:
                    sql = f"DELETE FROM {table_name} WHERE {where_clause}"
                else:
                    # 删除所有记录
                    sql = f"DELETE FROM {table_name}"
                
                cursor.execute(sql, values if where_clause else [])
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"已从表 {table_name} 删除记录",
                    "operation": "delete",
                    "table": table_name,
                    "affected_rows": cursor.rowcount
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"删除记录失败: {str(e)}")
            return {"status": "error", "message": f"删除记录失败: {str(e)}"}
    
    def _handle_update(self, table_name: str, params_str: str) -> Dict[str, Any]:
        """处理更新记录操作
        
        Args:
            table_name: 表名
            params_str: 参数字符串
            
        Returns:
            操作结果
        """
        try:
            # 解析参数
            params = self._parse_params(params_str)
            if not params:
                return {"status": "error", "message": "缺少参数"}
            
            # 分离条件和更新值
            condition_key = next(iter(params.keys()))  # 第一个参数作为条件
            condition_value = params[condition_key]
            update_params = {k: v for k, v in params.items() if k != condition_key}
            
            if not update_params:
                return {"status": "error", "message": "缺少更新值"}
            
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    return {"status": "error", "message": f"表不存在: {table_name}"}
                
                # 构建SET子句
                set_clause = ", ".join([f"{k} = ?" for k in update_params.keys()])
                set_values = list(update_params.values())
                
                # 构建WHERE子句
                where_clause = f"{condition_key} = ?"
                where_values = [condition_value]
                
                # 构建完整SQL
                sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
                values = set_values + where_values
                
                cursor.execute(sql, values)
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"已更新表 {table_name} 的记录",
                    "operation": "update",
                    "table": table_name,
                    "affected_rows": cursor.rowcount
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"更新记录失败: {str(e)}")
            return {"status": "error", "message": f"更新记录失败: {str(e)}"}
    
    def _handle_create(self, table_name: str, params_str: str) -> Dict[str, Any]:
        """处理创建表操作
        
        Args:
            table_name: 表名
            params_str: 参数字符串
            
        Returns:
            操作结果
        """
        try:
            # 解析参数
            params = self._parse_params(params_str)
            
            # 对于系统表，使用预定义的列定义
            if table_name in self.system_tables and not params:
                return self._create_system_table(table_name)
            
            if not params:
                return {"status": "error", "message": "缺少列定义"}
            
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否已存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if cursor.fetchone():
                    return {"status": "error", "message": f"表已存在: {table_name}"}
                
                # 构建列定义
                columns = []
                for name, type_def in params.items():
                    columns.append(f"{name} {type_def}")
                
                columns_str = ", ".join(columns)
                
                # 创建表
                sql = f"CREATE TABLE {table_name} ({columns_str})"
                cursor.execute(sql)
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"已创建表 {table_name}",
                    "operation": "create",
                    "table": table_name
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"创建表失败: {str(e)}")
            return {"status": "error", "message": f"创建表失败: {str(e)}"}
    
    def _create_system_table(self, table_name: str, cursor = None) -> Dict[str, Any]:
        """创建系统表
        
        Args:
            table_name: 表名
            cursor: 可选的游标，如果未提供则创建新连接
            
        Returns:
            操作结果
        """
        if table_name not in self.system_tables:
            return {"status": "error", "message": f"未知的系统表: {table_name}"}
        
        # 获取列定义
        columns = self.system_tables[table_name]
        
        release_conn = False
        conn_info = None
        
        try:
            # 如果未提供游标，创建新连接
            if cursor is None:
                conn, cursor, conn_info = self._get_db_connection()
                release_conn = True
            
            # 检查表是否已存在
            cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone():
                return {"status": "success", "message": f"表已存在: {table_name}"}
            
            # 构建列定义
            columns_def = []
            for name, type_def in columns.items():
                columns_def.append(f"{name} {type_def}")
            
            columns_str = ", ".join(columns_def)
            
            # 创建表
            sql = f"CREATE TABLE {table_name} ({columns_str})"
            cursor.execute(sql)
            
            # 如果我们创建了连接，则需要提交
            if release_conn:
                conn.commit()
            
            return {
                "status": "success", 
                "message": f"已创建系统表 {table_name}",
                "operation": "create",
                "table": table_name
            }
            
        finally:
            # 如果我们创建了连接，则需要释放
            if release_conn and conn_info is not None:
                self._release_connection(conn_info)
    
    def _handle_drop(self, table_name: str) -> Dict[str, Any]:
        """处理删除表操作
        
        Args:
            table_name: 表名
            
        Returns:
            操作结果
        """
        try:
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    return {"status": "error", "message": f"表不存在: {table_name}"}
                
                # 删除表
                sql = f"DROP TABLE {table_name}"
                cursor.execute(sql)
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"已删除表 {table_name}",
                    "operation": "drop",
                    "table": table_name
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"删除表失败: {str(e)}")
            return {"status": "error", "message": f"删除表失败: {str(e)}"}
    
    def _handle_query(self, table_name: str, params_str: str) -> Dict[str, Any]:
        """处理查询记录操作
        
        Args:
            table_name: 表名
            params_str: 参数字符串
            
        Returns:
            操作结果
        """
        try:
            # 解析参数
            params = self._parse_params(params_str)
            
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 检查表是否存在
                cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    return {"status": "error", "message": f"表不存在: {table_name}"}
                
                # 构建查询
                if params:
                    # 构建WHERE子句
                    where_clause = " AND ".join([f"{k} = ?" for k in params.keys()])
                    values = list(params.values())
                    
                    sql = f"SELECT * FROM {table_name} WHERE {where_clause}"
                    cursor.execute(sql, values)
                else:
                    # 查询所有记录
                    sql = f"SELECT * FROM {table_name}"
                    cursor.execute(sql)
                
                # 获取结果
                rows = cursor.fetchall()
                
                # 转换为字典列表
                result = []
                for row in rows:
                    result.append({k: row[k] for k in row.keys()})
                
                return {
                    "status": "success", 
                    "message": f"已查询表 {table_name}",
                    "operation": "query",
                    "table": table_name,
                    "records": result,
                    "count": len(result)
                }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"查询记录失败: {str(e)}")
            return {"status": "error", "message": f"查询记录失败: {str(e)}"}
    
    def _handle_list(self, table_name: str) -> Dict[str, Any]:
        """处理列出表操作
        
        Args:
            table_name: 表名或 'all'
            
        Returns:
            操作结果
        """
        try:
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                if table_name.lower() == 'all':
                    # 列出所有表
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    return {
                        "status": "success", 
                        "message": "数据库中的所有表",
                        "operation": "list",
                        "tables": tables
                    }
                else:
                    # 获取指定表的列信息
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = []
                    
                    for row in cursor.fetchall():
                        columns.append({
                            "name": row[1],
                            "type": row[2],
                            "notnull": row[3] == 1,
                            "default": row[4],
                            "pk": row[5] == 1
                        })
                    
                    return {
                        "status": "success", 
                        "message": f"表 {table_name} 的结构",
                        "operation": "list",
                        "table": table_name,
                        "columns": columns
                    }
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"列出表失败: {str(e)}")
            return {"status": "error", "message": f"列出表失败: {str(e)}"}
    
    # 额外的解析器方法，用于特定格式
    
    def parse_coordinates(self, content: str, task_name: str = None) -> bool:
        """[已弃用] 解析坐标配置，请使用插件系统代替
        
        Args:
            content: 配置内容
            task_name: 可选的任务名称
            
        Returns:
            是否成功
        """
        self.logger.warning("parse_coordinates方法已弃用，请使用插件系统")
        
        # 尝试使用坐标插件解析
        if 'coordinates' in self.plugins:
            return self.plugins['coordinates'].parse(content, task_name)
        try:
            # 确定目标数据库
            db_path = None
            if task_name:
                db_path = f"tasks/{task_name}/db/{task_name}.db"
                
            # 创建临时连接
            if db_path:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 确保表存在
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS coordinates (
                    id INTEGER PRIMARY KEY,
                    element_id TEXT NOT NULL,
                    screen TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    description TEXT
                )
                """)
                
                # 清空现有坐标
                cursor.execute("DELETE FROM coordinates")
            else:
                conn, cursor, _ = self._get_db_connection()
            
            # 解析配置
            current_screen = "global"
            
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # 检查是否是屏幕名称
                if line.startswith('[') and line.endswith(']'):
                    current_screen = line[1:-1].strip()
                    continue
                    
                # 解析坐标定义
                if '=' in line:
                    parts = line.split('=', 1)
                    element_id = parts[0].strip()
                    values = parts[1].strip()
                    
                    # 解析坐标值和可选描述
                    values_parts = values.split(',')
                    if len(values_parts) >= 2:
                        x = int(values_parts[0].strip())
                        y = int(values_parts[1].strip())
                        
                        description = None
                        if len(values_parts) > 2:
                            description = ','.join(values_parts[2:]).strip()
                            
                        # 插入数据库
                        cursor.execute(
                            "INSERT INTO coordinates (element_id, screen, x, y, description) VALUES (?, ?, ?, ?, ?)",
                            (element_id, current_screen, x, y, description)
                        )
            
            # 提交更改
            conn.commit()
            
            # 如果是临时连接
            if task_name:
                conn.close()
                
            return True
            
        except Exception as e:
            self.logger.error(f"解析坐标配置失败: {str(e)}")
            return False
    
    def parse_campaign(self, content: str, task_name: str = None) -> bool:
        """[已弃用] 解析征战天下配置，请使用插件系统代替
        
        Args:
            content: 配置内容
            task_name: 可选的任务名称
            
        Returns:
            是否成功
        """
        self.logger.warning("parse_campaign方法已弃用，请使用插件系统")
        try:
            # 确定目标数据库
            db_path = None
            if task_name:
                db_path = f"tasks/{task_name}/db/{task_name}.db"
                
            # 创建临时连接
            if db_path:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 确保表存在
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sweep_chapters (
                    id INTEGER PRIMARY KEY,
                    chapter_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    priority INTEGER NOT NULL
                )
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sweep_stages (
                    id INTEGER PRIMARY KEY,
                    chapter_id TEXT NOT NULL,
                    stage_number INTEGER NOT NULL,
                    priority INTEGER NOT NULL
                )
                """)
                
                # 清空现有数据
                cursor.execute("DELETE FROM sweep_chapters")
                cursor.execute("DELETE FROM sweep_stages")
            else:
                conn, cursor, _ = self._get_db_connection()
            
            # 预处理内容 - 移除可能的 [征战天下] 标签
            content = re.sub(r'^\s*\[[^\]]+\]', '', content).strip()
            
            # 如果使用分号分隔，转换为多行格式
            if ';' in content and ':' in content:
                content = content.replace(';', '\n')
            
            # 解析每一行/条目
            priority = 0
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 解析章节和小节
                if ':' in line:
                    chapter_part, stages_part = line.split(':', 1)
                    chapter_name = chapter_part.strip()
                    
                    # 生成章节ID
                    chapter_id = f"chapter_{priority + 1}"
                    
                    # 插入章节
                    cursor.execute(
                        "INSERT INTO sweep_chapters (chapter_id, name, priority) VALUES (?, ?, ?)",
                        (chapter_id, chapter_name, priority + 1)
                    )
                    
                    # 解析小节
                    stage_parts = stages_part.split(',')
                    for i, stage_part in enumerate(stage_parts):
                        stage_str = stage_part.strip()
                        if not stage_str:
                            continue
                            
                        # 提取数字
                        stage_match = re.search(r'\d+', stage_str)
                        if stage_match:
                            stage_number = int(stage_match.group())
                            
                            # 插入小节
                            cursor.execute(
                                "INSERT INTO sweep_stages (chapter_id, stage_number, priority) VALUES (?, ?, ?)",
                                (chapter_id, stage_number, i + 1)
                            )
                    
                    priority += 1
            
            # 提交更改
            conn.commit()
            
            # 如果是临时连接
            if task_name:
                conn.close()
                
            return True
            
        except Exception as e:
            self.logger.error(f"解析征战天下配置失败: {str(e)}")
            return False
    
    # 便捷方法
    
    def add_account(self, app_id: str, username: str, password: str, 
                   status: str = "active", login_type: str = "default", 
                   extra_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加账号
        
        Args:
            app_id: 应用ID
            username: 用户名
            password: 密码
            status: 状态
            login_type: 登录类型
            extra_data: 额外数据
            
        Returns:
            操作结果
        """
        # 生成账号ID
        import hashlib
        account_id = f"{app_id}_{hashlib.md5(username.encode()).hexdigest()[:8]}"
        
        # 构建命令
        command = f'add[accounts] account_id:{account_id}; app_id:{app_id}; username:{username}; password:{password}; status:{status}; login_type:{login_type}'
        
        if extra_data:
            import json
            extra_data_str = json.dumps(extra_data)
            command += f'; extra_data:{extra_data_str}'
            
        # 执行命令
        return self._parse_command(command)
    
    def add_app(self, app_id: str, name: str, package_name: str, 
               priority: int = 5, time_slice: int = 7200, 
               daily_limit: int = 14400, reset_time: str = "04:00", 
               config: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加应用
        
        Args:
            app_id: 应用ID
            name: 应用名称
            package_name: 包名
            priority: 优先级
            time_slice: 时间片（秒）
            daily_limit: 每日限制（秒）
            reset_time: 重置时间
            config: 配置
            
        Returns:
            操作结果
        """
        # 构建命令
        command = f'add[apps] app_id:{app_id}; name:{name}; package_name:{package_name}; priority:{priority}; time_slice:{time_slice}; daily_limit:{daily_limit}; reset_time:{reset_time}; status:active'
        
        if config:
            import json
            config_str = json.dumps(config)
            command += f'; config:{config_str}'
            
        # 执行命令
        return self._parse_command(command)
    
    def add_task(self, app_id: str, name: str, task_type: str = "daily", 
                priority: int = 5, handler_class: str = None, 
                config: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加任务
        
        Args:
            app_id: 应用ID
            name: 任务名称
            task_type: 任务类型
            priority: 优先级
            handler_class: 处理类
            config: 配置
            
        Returns:
            操作结果
        """
        # 生成任务ID
        import uuid
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # 构建命令
        command = f'add[tasks] task_id:{task_id}; app_id:{app_id}; name:{name}; type:{task_type}; priority:{priority}'
        
        if handler_class:
            command += f'; handler_class:{handler_class}'
            
        if config:
            import json
            config_str = json.dumps(config)
            command += f'; config:{config_str}'
            
        # 执行命令
        return self._parse_command(command)
    
    def get_all_tables(self) -> List[str]:
        """获取所有表名
        
        Returns:
            表名列表
        """
        try:
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 获取所有表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                return tables
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"获取所有表失败: {str(e)}")
            return []
    
    def export_csv(self, table_name: str, file_path: str, 
                 where_clause: str = None, where_params: tuple = None) -> bool:
        """导出表到CSV文件
        
        Args:
            table_name: 表名
            file_path: 文件路径
            where_clause: WHERE子句
            where_params: WHERE参数
            
        Returns:
            是否成功
        """
        try:
            import csv
            
            # 获取数据库连接
            conn, cursor, conn_info = self._get_db_connection()
            
            try:
                # 构建查询
                query = f"SELECT * FROM {table_name}"
                if where_clause:
                    query += f" WHERE {where_clause}"
                    
                # 执行查询
                if where_params:
                    cursor.execute(query, where_params)
                else:
                    cursor.execute(query)
                    
                # 获取列名
                column_names = [description[0] for description in cursor.description]
                
                # 获取所有行
                rows = cursor.fetchall()
                
                # 写入CSV
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # 写入表头
                    writer.writerow(column_names)
                    
                    # 写入数据
                    for row in rows:
                        writer.writerow([row[col] for col in column_names])
                        
                return True
                
            finally:
                # 释放连接
                self._release_connection(conn_info)
                
        except Exception as e:
            self.logger.error(f"导出CSV失败: {str(e)}")
            return False
    
    def import_csv(self, table_name: str, file_path: str, create_table: bool = False) -> bool:
        """从CSV文件导入数据
        
        Args:
            table_name: 表名
            file_path: 文件路径
            create_table: 是否创建表
            
        Returns:
            是否成功
        """
        try:
            import csv
            
            # 读取CSV文件
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                # 读取表头
                header = next(reader)
                
                # 获取数据库连接
                conn, cursor, conn_info = self._get_db_connection()
                
                try:
                    # 检查表是否存在
                    cursor.execute(f"SELECT 1 FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                    table_exists = cursor.fetchone() is not None
                    
                    # 创建表（如果需要）
                    if not table_exists and create_table:
                        # 基本列定义
                        columns = [f"{col} TEXT" for col in header]
                        columns_str = ", ".join(columns)
                        
                        # 创建表
                        cursor.execute(f"CREATE TABLE {table_name} ({columns_str})")
                    
                    # 导入数据
                    for row in reader:
                        # 构建INSERT语句
                        placeholders = ", ".join(["?" for _ in header])
                        columns_str = ", ".join(header)
                        
                        cursor.execute(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})", row)
                    
                    # 提交更改
                    conn.commit()
                    return True
                    
                finally:
                    # 释放连接
                    self._release_connection(conn_info)
                    
        except Exception as e:
            self.logger.error(f"导入CSV失败: {str(e)}")
            return False

    def register_plugin(self, plugin: IConfigParserPlugin) -> bool:
        """注册解析器插件
        
        Args:
            plugin: 实现IConfigParserPlugin接口的插件实例
            
        Returns:
            是否成功
        """
        try:
            plugin_name = plugin.get_name()
            self.plugins[plugin_name] = plugin
            self.logger.info(f"注册配置解析器插件: {plugin_name}")
            return True
        except Exception as e:
            self.logger.error(f"注册插件失败: {str(e)}")
            return False
    
    def parse_with_plugin(self, plugin_name: str, content: str, task_name: str = None, db_path: str = None) -> bool:
        """使用指定插件解析配置
        
        Args:
            plugin_name: 插件名称
            content: 配置内容
            task_name: 可选的任务名称
            db_path: 可选的数据库路径
            
        Returns:
            是否成功
        """
        try:
            if plugin_name not in self.plugins:
                self.logger.error(f"插件不存在: {plugin_name}")
                return False
                
            plugin = self.plugins[plugin_name]
            return plugin.parse(content, task_name, db_path)
        except Exception as e:
            self.logger.error(f"使用插件解析配置失败: {str(e)}")
            return False
    
    def load_plugins_from_task(self, task_name: str) -> bool:
        """从任务模块加载插件
        
        Args:
            task_name: 任务名称
            
        Returns:
            是否成功
        """
        try:
            # 构建任务模块路径
            module_path = f"tasks.{task_name}.config_plugins"
            
            try:
                # 尝试导入插件模块
                plugins_module = importlib.import_module(module_path)
                
                # 查找所有插件类
                for attr_name in dir(plugins_module):
                    attr = getattr(plugins_module, attr_name)
                    # 检查是否是插件类
                    if isinstance(attr, type) and hasattr(attr, 'get_name') and hasattr(attr, 'parse'):
                        # 创建插件实例并注册
                        plugin = attr()
                        self.register_plugin(plugin)
                        
                return True
            except ImportError:
                self.logger.info(f"任务 {task_name} 没有定义配置插件")
                return False
                
        except Exception as e:
            self.logger.error(f"加载任务插件失败: {str(e)}")
            return False

    def detect_format_and_parse(self, content: str, task_name: str = None) -> Dict[str, Any]:
        """自动检测配置格式并使用合适的插件解析
    
    Args:
        content: 配置内容
        task_name: 可选的任务名称
        
    Returns:
        解析结果
    """
    # 方法实现...        # 检查是否是坐标配置
        if re.search(r'^\s*\[[^\]]+\]', content) and '=' in content:
            format_type = 'coordinates'
        # 检查是否是征战天下配置
        elif ':' in content and (',' in content or ';' in content):
            if re.search(r'^\s*\[征战天下\]', content) or ';' in content:
                format_type = 'campaign'
            else:
                format_type = 'general'
        else:
            format_type = 'general'
            
        # 使用检测到的格式解析
        if format_type in self.plugins:
            success = self.parse_with_plugin(format_type, content, task_name)
            return {"format": format_type, "success": success}
        else:
            return {"format": "unknown", "success": False, "error": "没有合适的解析器插件"}
        
