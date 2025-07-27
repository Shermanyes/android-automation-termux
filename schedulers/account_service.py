# account_service.py
from core.interfaces import IAccountService, ISystemModule
from core.base_classes import SystemModule
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

class AccountService(SystemModule, IAccountService):
    """账号服务实现，管理应用账号和任务状态"""
    
    def __init__(self, db_manager):
        """初始化账号服务
        
        Args:
            db_manager: 数据库管理器实例
        """
        super().__init__("AccountService", "1.0.0")
        self.db = db_manager
        self._logger = logging.getLogger("AccountService")
        
    def initialize(self) -> bool:
        """初始化账号服务"""
        super().initialize()
        self._logger.info("账号服务初始化完成")
        return True
        
    def add_account(self, account_id: str, app_id: str, account_info: Dict[str, Any]) -> bool:
        """添加账号
        
        Args:
            account_id: 账号ID
            app_id: 应用ID
            account_info: 账号信息字典
            
        Returns:
            添加成功返回True，否则False
        """
        try:
            # 检查应用是否存在
            if not self.db.exists("apps", "app_id = ?", (app_id,)):
                self._logger.error(f"添加账号失败：应用 {app_id} 不存在")
                return False
                
            # 检查账号是否已存在
            if self.db.exists("accounts", "account_id = ?", (account_id,)):
                self._logger.warning(f"账号 {account_id} 已存在，更新信息")
                # 更新账号信息
                account_info['app_id'] = app_id
                self.db.update("accounts", account_info, "account_id = ?", (account_id,))
                return True
            
            # 添加账号
            account_data = {
                "account_id": account_id,
                "app_id": app_id,
                "username": account_info.get("username"),
                "password": account_info.get("password"),
                "login_type": account_info.get("login_type", "default"),
                "last_login_time": account_info.get("last_login_time", 0),
                "total_runtime": account_info.get("total_runtime", 0),
                "daily_runtime": account_info.get("daily_runtime", 0),
                "status": account_info.get("status", "active"),
                "extra_data": account_info.get("extra_data")
            }
            
            self.db.insert("accounts", account_data)
            self._logger.info(f"账号 {account_id} 添加成功")
            return True
            
        except Exception as e:
            self._logger.error(f"添加账号失败: {str(e)}")
            return False
    
    def remove_account(self, account_id: str) -> bool:
        """删除账号
        
        Args:
            account_id: 账号ID
            
        Returns:
            删除成功返回True，否则False
        """
        try:
            # 检查账号是否存在
            if not self.db.exists("accounts", "account_id = ?", (account_id,)):
                self._logger.warning(f"账号 {account_id} 不存在")
                return False
                
            # 删除账号相关的任务状态
            self.db.delete("task_status", "account_id = ?", (account_id,))
            
            # 删除账号
            self.db.delete("accounts", "account_id = ?", (account_id,))
            
            self._logger.info(f"账号 {account_id} 删除成功")
            return True
            
        except Exception as e:
            self._logger.error(f"删除账号失败: {str(e)}")
            return False
    
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取账号信息
        
        Args:
            account_id: 账号ID
            
        Returns:
            账号信息字典，不存在返回None
        """
        return self.db.fetch_one("SELECT * FROM accounts WHERE account_id = ?", (account_id,))
    
    def get_account_list(self, app_id: str = None) -> List[Dict[str, Any]]:
        """获取账号列表
        
        Args:
            app_id: 可选的应用ID过滤器
            
        Returns:
            账号信息字典列表
        """
        if app_id:
            return self.db.fetch_all("SELECT * FROM accounts WHERE app_id = ? ORDER BY last_login_time", (app_id,))
        else:
            return self.db.fetch_all("SELECT * FROM accounts ORDER BY app_id, last_login_time")
    
    def get_next_account(self, app_id: str) -> Optional[str]:
        """获取应用的下一个待执行账号
        
        Args:
            app_id: 应用ID
            
        Returns:
            账号ID，无可用账号返回None
        """
        try:
            # 策略：选择最长时间未登录且状态为active的账号
            account = self.db.fetch_one("""
                SELECT account_id, last_login_time 
                FROM accounts 
                WHERE app_id = ? AND status = 'active'
                ORDER BY last_login_time ASC
                LIMIT 1
            """, (app_id,))
            
            if account:
                return account["account_id"]
            return None
            
        except Exception as e:
            self._logger.error(f"获取下一个账号失败: {str(e)}")
            return None
    
    def switch_to_account(self, account_id: str) -> bool:
        """切换到指定账号（仅更新状态，不执行实际登录）
        
        Args:
            account_id: 账号ID
            
        Returns:
            切换成功返回True，否则False
        """
        try:
            # 检查账号是否存在
            account = self.get_account(account_id)
            if not account:
                self._logger.error(f"切换账号失败: 账号 {account_id} 不存在")
                return False
            
            # 更新账号最后登录时间
            current_time = int(time.time())
            self.db.update(
                "accounts", 
                {"last_login_time": current_time}, 
                "account_id = ?", 
                (account_id,)
            )
            
            self._logger.info(f"切换到账号: {account_id}")
            
            # 记录活动
            self.db.log_activity(
                action="switch_account",
                status="success",
                account_id=account_id,
                app_id=account.get("app_id"),
                details=f"切换到账号 {account_id}"
            )
            
            return True
            
        except Exception as e:
            self._logger.error(f"切换账号失败: {str(e)}")
            return False
    
    def update_account_task_status(self, account_id: str, task_id: str, completed: bool) -> bool:
        """更新账号的任务状态
        
        Args:
            account_id: 账号ID
            task_id: 任务ID
            completed: 是否完成
            
        Returns:
            更新成功返回True，否则False
        """
        try:
            current_time = int(time.time())
            
            # 检查记录是否存在
            status_record = self.db.fetch_one(
                "SELECT * FROM task_status WHERE account_id = ? AND task_id = ?",
                (account_id, task_id)
            )
            
            if status_record:
                # 更新现有记录
                update_data = {
                    "completed": 1 if completed else 0,
                    "completion_time": current_time if completed else None,
                    "last_run_time": current_time
                }
                
                self.db.update(
                    "task_status",
                    update_data,
                    "account_id = ? AND task_id = ?",
                    (account_id, task_id)
                )
            else:
                # 创建新记录
                status_data = {
                    "account_id": account_id,
                    "task_id": task_id,
                    "completed": 1 if completed else 0,
                    "completion_time": current_time if completed else None,
                    "last_run_time": current_time,
                    "retry_count": 0
                }
                
                self.db.insert("task_status", status_data)
            
            self._logger.info(f"更新账号 {account_id} 的任务 {task_id} 状态为 {'已完成' if completed else '未完成'}")
            return True
            
        except Exception as e:
            self._logger.error(f"更新任务状态失败: {str(e)}")
            return False
    
    def get_account_task_status(self, account_id: str, task_id: str = None) -> Dict[str, Any]:
        """获取账号的任务状态
        
        Args:
            account_id: 账号ID
            task_id: 可选的任务ID过滤
            
        Returns:
            任务状态字典 {任务ID: 状态信息}
        """
        try:
            if task_id:
                # 获取特定任务状态
                status = self.db.fetch_one(
                    "SELECT * FROM task_status WHERE account_id = ? AND task_id = ?",
                    (account_id, task_id)
                )
                return status or {"account_id": account_id, "task_id": task_id, "completed": 0}
            else:
                # 获取所有任务状态
                status_list = self.db.fetch_all(
                    "SELECT * FROM task_status WHERE account_id = ?",
                    (account_id,)
                )
                
                # 转换为字典格式 {任务ID: 状态}
                result = {}
                for status in status_list:
                    result[status["task_id"]] = status
                
                return result
                
        except Exception as e:
            self._logger.error(f"获取任务状态失败: {str(e)}")
            return {}
    
    def clear_daily_tasks(self, app_id: str = None, account_id: str = None) -> bool:
        """清除每日任务状态
        
        Args:
            app_id: 可选的应用ID过滤
            account_id: 可选的账号ID过滤
            
        Returns:
            清除成功返回True，否则False
        """
        try:
            with self.db.transaction() as tx:
                # 构建SQL查询
                query_parts = ["SELECT ts.status_id FROM task_status ts"]
                query_params = []
                where_clauses = []
                
                # 关联任务表以获取任务类型
                query_parts.append("JOIN tasks t ON ts.task_id = t.task_id")
                where_clauses.append("t.type = 'daily'")
                
                # 添加过滤条件
                if app_id:
                    query_parts.append("JOIN accounts a ON ts.account_id = a.account_id")
                    where_clauses.append("a.app_id = ?")
                    query_params.append(app_id)
                
                if account_id:
                    where_clauses.append("ts.account_id = ?")
                    query_params.append(account_id)
                
                # 组合查询
                query = " ".join(query_parts)
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                # 获取需要重置的任务ID
                status_ids = tx.fetch_all(query, tuple(query_params))
                ids_to_reset = [s["status_id"] for s in status_ids]
                
                if ids_to_reset:
                    # 批量更新状态
                    placeholders = ",".join(["?"] * len(ids_to_reset))
                    tx.execute(
                        f"UPDATE task_status SET completed = 0, completion_time = NULL WHERE status_id IN ({placeholders})",
                        tuple(ids_to_reset)
                    )
                
                # 同时重置账号的每日运行时间
                if app_id:
                    tx.execute(
                        "UPDATE accounts SET daily_runtime = 0 WHERE app_id = ?",
                        (app_id,)
                    )
                elif account_id:
                    tx.execute(
                        "UPDATE accounts SET daily_runtime = 0 WHERE account_id = ?",
                        (account_id,)
                    )
                else:
                    tx.execute("UPDATE accounts SET daily_runtime = 0")
            
            self._logger.info(
                f"已清除每日任务状态: " + 
                (f"应用={app_id} " if app_id else "") + 
                (f"账号={account_id}" if account_id else "所有账号")
            )
            return True
            
        except Exception as e:
            self._logger.error(f"清除每日任务状态失败: {str(e)}")
            return False
            
    def update_account_runtime(self, account_id: str, seconds: int) -> bool:
        """更新账号运行时间
        
        Args:
            account_id: 账号ID
            seconds: 运行时间(秒)
            
        Returns:
            更新成功返回True，否则False
        """
        try:
            account = self.get_account(account_id)
            if not account:
                self._logger.error(f"更新账号运行时间失败: 账号 {account_id} 不存在")
                return False
                
            # 更新总运行时间和每日运行时间
            total_runtime = account.get("total_runtime", 0) + seconds
            daily_runtime = account.get("daily_runtime", 0) + seconds
            
            self.db.update(
                "accounts",
                {"total_runtime": total_runtime, "daily_runtime": daily_runtime},
                "account_id = ?",
                (account_id,)
            )
            
            self._logger.info(f"更新账号 {account_id} 运行时间: +{seconds}秒")
            return True
            
        except Exception as e:
            self._logger.error(f"更新账号运行时间失败: {str(e)}")
            return False
    
    def get_completed_tasks(self, account_id: str, app_id: str = None) -> List[str]:
        """获取账号已完成的任务列表
        
        Args:
            account_id: 账号ID
            app_id: 可选的应用ID过滤
            
        Returns:
            已完成任务ID列表
        """
        try:
            query = """
                SELECT ts.task_id 
                FROM task_status ts
                JOIN tasks t ON ts.task_id = t.task_id
                WHERE ts.account_id = ? AND ts.completed = 1
            """
            params = [account_id]
            
            if app_id:
                query += " AND t.app_id = ?"
                params.append(app_id)
                
            results = self.db.fetch_all(query, tuple(params))
            return [r["task_id"] for r in results]
            
        except Exception as e:
            self._logger.error(f"获取已完成任务列表失败: {str(e)}")
            return []
