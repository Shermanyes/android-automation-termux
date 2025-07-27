#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SQLite数据库导入工具：从SQL文件导入数据到数据库
"""

import os
import sys
import argparse
import logging
import re
import sqlite3
from typing import List

# 添加系统路径，确保能导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("import.log"), logging.StreamHandler()]
)
logger = logging.getLogger('sql_import_tool')

class SQLImporter:
    """SQLite数据库导入工具"""
    
    def __init__(self, db_path: str):
        """初始化导入工具
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = db_path
        self.connection = None
        
    def connect(self):
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            return False
            
    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            
    def parse_sql_file(self, sql_path: str) -> List[str]:
        """解析SQL文件，提取SQL语句
        
        Args:
            sql_path: SQL文件路径
            
        Returns:
            SQL语句列表
        """
        try:
            with open(sql_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 移除注释
            content = re.sub(r'--.*?\n', '\n', content)
            
            # 分割SQL语句
            statements = []
            buffer = ''
            
            for line in content.splitlines():
                line = line.strip()
                
                if not line:
                    continue
                    
                buffer += line + ' '
                
                if line.endswith(';'):
                    statements.append(buffer.strip())
                    buffer = ''
            
            # 如果还有未处理的内容
            if buffer.strip():
                statements.append(buffer.strip())
                
            return statements
            
        except Exception as e:
            logger.error(f"解析SQL文件失败: {str(e)}")
            return []
            
    def execute_statement(self, statement: str) -> bool:
        """执行单条SQL语句
        
        Args:
            statement: SQL语句
            
        Returns:
            是否执行成功
        """
        if not statement.strip():
            return True
            
        try:
            self.connection.execute(statement)
            return True
        except Exception as e:
            logger.error(f"执行SQL语句失败: {str(e)}\nSQL: {statement}")
            return False
            
    def import_from_sql(self, sql_path: str, continue_on_error: bool = False) -> bool:
        """从SQL文件导入数据
        
        Args:
            sql_path: SQL文件路径
            continue_on_error: 出错时是否继续（默认为False）
            
        Returns:
            是否导入成功
        """
        if not os.path.exists(sql_path):
            logger.error(f"SQL文件不存在: {sql_path}")
            return False
            
        if not self.connection:
            if not self.connect():
                return False
                
        try:
            # 解析SQL文件
            statements = self.parse_sql_file(sql_path)
            
            if not statements:
                logger.warning(f"SQL文件中没有找到有效的SQL语句: {sql_path}")
                return False
                
            # 开始事务
            self.connection.execute("BEGIN TRANSACTION")
            
            # 禁用外键约束（以便于导入）
            self.connection.execute("PRAGMA foreign_keys = OFF")
            
            # 执行所有语句
            success = True
            for i, stmt in enumerate(statements):
                if not self.execute_statement(stmt):
                    success = False
                    if not continue_on_error:
                        logger.error(f"导入失败，停止于语句 {i+1}/{len(statements)}")
                        self.connection.rollback()
                        return False
            
            # 提交事务
            if success or continue_on_error:
                self.connection.commit()
                logger.info(f"成功导入SQL文件: {sql_path}")
                
                # 重新启用外键约束
                self.connection.execute("PRAGMA foreign_keys = ON")
                return True
            else:
                self.connection.rollback()
                return False
                
        except Exception as e:
            logger.error(f"导入SQL文件失败: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            self.disconnect()
            
    def import_from_sql_with_backup(self, sql_path: str, continue_on_error: bool = False) -> bool:
        """从SQL文件导入数据，并创建备份
        
        Args:
            sql_path: SQL文件路径
            continue_on_error: 出错时是否继续（默认为False）
            
        Returns:
            是否导入成功
        """
        # 检查数据库是否存在
        if os.path.exists(self.db_path):
            # 创建备份
            backup_path = f"{self.db_path}.bak"
            try:
                import shutil
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"已创建数据库备份: {backup_path}")
            except Exception as e:
                logger.error(f"创建数据库备份失败: {str(e)}")
                return False
                
        # 执行导入
        return self.import_from_sql(sql_path, continue_on_error)


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="SQLite数据库导入工具")
    parser.add_argument('--db', required=True, help='SQLite数据库路径')
    parser.add_argument('--sql', required=True, help='输入SQL文件路径')
    parser.add_argument('--force', action='store_true', help='出错时继续执行')
    parser.add_argument('--no-backup', action='store_true', help='不创建备份')
    
    args = parser.parse_args()
    
    importer = SQLImporter(args.db)
    
    if args.no_backup:
        result = importer.import_from_sql(args.sql, args.force)
    else:
        result = importer.import_from_sql_with_backup(args.sql, args.force)
        
    if result:
        print(f"SQL文件 {args.sql} 成功导入到数据库 {args.db}")
        return 0
    else:
        print("导入失败，请查看日志获取更多信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
