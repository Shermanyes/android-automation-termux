#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SQLite数据库导出工具：将数据库导出为可读的SQL文件
"""

import os
import sys
import argparse
import logging
import time
import sqlite3
from typing import List, Dict, Any

# 添加系统路径，确保能导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("export.log"), logging.StreamHandler()]
)
logger = logging.getLogger('sql_export_tool')

class SQLExporter:
    """SQLite数据库导出工具"""
    
    def __init__(self, db_path: str):
        """初始化导出工具
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            return False
            
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            
    def get_tables(self) -> List[str]:
        """获取所有表名
        
        Returns:
            表名列表
        """
        if not self.connection:
            if not self.connect():
                return []
                
        try:
            cursor = self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row['name'] for row in cursor.fetchall()]
            return tables
        except Exception as e:
            logger.error(f"获取表名失败: {str(e)}")
            return []
            
    def get_table_schema(self, table: str) -> str:
        """获取表的创建语句
        
        Args:
            table: 表名
            
        Returns:
            表创建SQL语句
        """
        if not self.connection:
            if not self.connect():
                return ""
                
        try:
            cursor = self.connection.execute(
                f"SELECT sql FROM sqlite_master WHERE name = '{table}'"
            )
            row = cursor.fetchone()
            return row['sql'] if row else ""
        except Exception as e:
            logger.error(f"获取表结构失败: {str(e)}")
            return ""
            
    def get_table_data(self, table: str) -> List[Dict[str, Any]]:
        """获取表的所有数据
        
        Args:
            table: 表名
            
        Returns:
            包含行数据的字典列表
        """
        if not self.connection:
            if not self.connect():
                return []
                
        try:
            cursor = self.connection.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]
        except Exception as e:
            logger.error(f"获取表数据失败: {str(e)}")
            return []
            
    def format_value(self, value) -> str:
        """格式化SQL值
        
        Args:
            value: 要格式化的值
            
        Returns:
            格式化后的SQL值字符串
        """
        if value is None:
            return 'NULL'
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            # 转义单引号
            val_str = str(value).replace("'", "''")
            return f"'{val_str}'"
            
    def export_to_sql(self, output_path: str, include_data: bool = True, tables: List[str] = None) -> bool:
        """导出数据库到SQL文件
        
        Args:
            output_path: 输出文件路径
            include_data: 是否包含数据（默认为True）
            tables: 要导出的表名列表（默认为所有表）
            
        Returns:
            如果导出成功则返回True，否则返回False
        """
        try:
            if not self.connection:
                if not self.connect():
                    return False
                    
            # 获取要导出的表
            all_tables = self.get_tables()
            
            if tables:
                # 过滤出存在的表
                export_tables = [t for t in tables if t in all_tables]
                if not export_tables:
                    logger.error(f"指定的表不存在: {tables}")
                    return False
            else:
                export_tables = all_tables
                
            # 打开输出文件
            with open(output_path, 'w', encoding='utf-8') as sql_file:
                # 写入头部信息
                sql_file.write("-- 自动化系统数据库导出\n")
                sql_file.write(f"-- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                sql_file.write(f"-- 源数据库: {self.db_path}\n")
                sql_file.write("-- 导出工具: SQL导出工具\n\n")
                
                # 添加PRAGMA语句
                sql_file.write("PRAGMA foreign_keys = OFF;\n")
                sql_file.write("BEGIN TRANSACTION;\n\n")
                
                # 处理每个表
                for table in export_tables:
                    # 写入表注释
                    sql_file.write(f"-- 表 {table}\n")
                    
                    # 删除表（如果存在）
                    sql_file.write(f"DROP TABLE IF EXISTS {table};\n")
                    
                    # 写入表创建语句
                    create_stmt = self.get_table_schema(table)
                    sql_file.write(f"{create_stmt};\n\n")
                    
                    # 导出数据（如果需要）
                    if include_data:
                        rows = self.get_table_data(table)
                        if rows:
                            sql_file.write(f"-- 表 {table} 的数据\n")
                            for row in rows:
                                columns = row.keys()
                                col_str = ', '.join(columns)
                                # 格式化值
                                values = [self.format_value(row[col]) for col in columns]
                                val_str = ', '.join(values)
                                
                                sql_file.write(f"INSERT INTO {table} ({col_str}) VALUES ({val_str});\n")
                            sql_file.write("\n")
                
                # 结束事务
                sql_file.write("COMMIT;\n")
                sql_file.write("PRAGMA foreign_keys = ON;\n")
                
            logger.info(f"成功导出数据库到 {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出数据库失败: {str(e)}")
            return False
        finally:
            self.disconnect()


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="SQLite数据库导出工具")
    parser.add_argument('--db', required=True, help='SQLite数据库路径')
    parser.add_argument('--output', required=True, help='输出SQL文件路径')
    parser.add_argument('--schema-only', action='store_true', help='仅导出架构，不包含数据')
    parser.add_argument('--tables', nargs='+', help='要导出的表名列表（默认为所有表）')
    
    args = parser.parse_args()
    
    exporter = SQLExporter(args.db)
    if exporter.export_to_sql(args.output, not args.schema_only, args.tables):
        print(f"数据库成功导出到 {args.output}")
        return 0
    else:
        print("导出失败，请查看日志获取更多信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
