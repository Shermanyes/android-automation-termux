from core.interfaces import IAppScheduler, ISystemModule
from core.base_classes import SystemModule
import threading
import time
import logging
from typing import Dict, List, Optional, Any
import utils

class AppScheduler(SystemModule, IAppScheduler):
    """应用调度器，负责多应用的优先级调度和时间片轮转"""
    
    def __init__(self, db_manager, task_manager, account_service, device_controller):
        """初始化应用调度器
        
        参数:
            db_manager: 数据库管理器实例
            task_manager: 任务管理器实例
            account_service: 账号服务实例
            device_controller: 设备控制器实例
        """
        super().__init__("AppScheduler", "1.0.0")
        self.db_manager = db_manager
        self.task_manager = task_manager
        self.account_service = account_service
        self.device_controller = device_controller
        
        self.running = False
        self.scheduler_thread = None
        self.current_app = None
        self.app_start_time = 0
        self.lock = threading.Lock()
    
    def initialize(self) -> bool:
        """初始化应用调度器"""
        if self.is_initialized:
            return True
            
        self.log_info("正在初始化应用调度器...")
        
        # 检查数据库中已存在的应用
        apps = self.db_manager.fetch_all("SELECT * FROM apps")
        if apps:
            self.log_info(f"已加载 {len(apps)} 个应用")
        
        # 启动任务状态检查线程
        self._start_status_check()
        
        return super().initialize()
    
    def shutdown(self) -> bool:
        """关闭应用调度器"""
        if not self.is_initialized:
            return True
            
        self.log_info("正在关闭应用调度器...")
        
        # 停止调度
        self.stop()
        
        return super().shutdown()
    
    def register_app(self, app_id: str, app_config: Dict[str, Any]) -> bool:
        """注册应用
        
        参数:
            app_id: 应用ID
            app_config: 应用配置
            
        返回:
            成功返回True，否则返回False
        """
        with self.lock:
            try:
                # 检查应用是否已存在
                exists = self.db_manager.exists("apps", "app_id = ?", (app_id,))
                
                if exists:
                    # 更新现有应用
                    self.db_manager.update("apps", app_config, "app_id = ?", (app_id,))
                    self.log_info(f"已更新应用: {app_id}")
                else:
                    # 创建新应用
                    app_config['app_id'] = app_id
                    if 'time_slice' not in app_config:
                        app_config['time_slice'] = 7200  # 默认2小时
                    if 'daily_limit' not in app_config:
                        app_config['daily_limit'] = 14400  # 默认4小时
                    if 'reset_time' not in app_config:
                        app_config['reset_time'] = "04:00"  # 默认4:00 AM
                    
                    self.db_manager.insert("apps", app_config)
                    self.log_info(f"已注册应用: {app_id}")
                
                return True
            except Exception as e:
                self.log_error(f"注册应用失败: {str(e)}")
                return False
    
    def unregister_app(self, app_id: str) -> bool:
        """注销应用
        
        参数:
            app_id: 应用ID
            
        返回:
            成功返回True，否则返回False
        """
        with self.lock:
            try:
                # 检查应用是否存在
                exists = self.db_manager.exists("apps", "app_id = ?", (app_id,))
                
                if not exists:
                    self.log_warning(f"应用不存在: {app_id}")
                    return False
                
                # 删除应用
                self.db_manager.delete("apps", "app_id = ?", (app_id,))
                self.log_info(f"已注销应用: {app_id}")
                
                return True
            except Exception as e:
                self.log_error(f"注销应用失败: {str(e)}")
                return False
    
    def start(self) -> bool:
        """启动应用调度器
        
        返回:
            成功返回True，否则返回False
        """
        with self.lock:
            if self.running:
                self.log_warning("应用调度器已在运行")
                return True
            
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            
            self.log_info("应用调度器已启动")
            return True
    
    def stop(self) -> bool:
        """停止应用调度器
        
        返回:
            成功返回True，否则返回False
        """
        with self.lock:
            if not self.running:
                return True
            
            self.running = False
            if self.scheduler_thread:
                self.scheduler_thread.join(timeout=5)
                self.scheduler_thread = None
            
            self.log_info("应用调度器已停止")
            return True
    
    def get_next_app(self) -> Optional[str]:
        """获取下一个应用
        
        返回:
            应用ID或None
        """
        with self.lock:
            try:
                # 按优先级排序应用
                apps = self.db_manager.fetch_all(
                    "SELECT app_id, priority, daily_limit, status FROM apps WHERE status != 'disabled' ORDER BY priority"
                )
                
                if not apps:
                    self.log_warning("没有可用的应用")
                    return None
                
                # 获取应用运行时间
                for app in apps:
                    app_id = app['app_id']
                    
                    # 获取今日运行时间
                    accounts = self.db_manager.fetch_all(
                        "SELECT SUM(daily_runtime) as total_runtime FROM accounts WHERE app_id = ?",
                        (app_id,)
                    )
                    
                    daily_runtime = accounts[0]['total_runtime'] if accounts and accounts[0]['total_runtime'] else 0
                    app['daily_runtime'] = daily_runtime
                    
                    # 检查是否已达到每日限制
                    if daily_runtime >= app['daily_limit']:
                        continue
                    
                    # 检查任务状态
                    app_tasks = self.task_manager.get_task_list(app_id)
                    if not app_tasks:
                        continue
                    
                    # 检查是否所有任务都已完成
                    all_completed = True
                    for task in app_tasks:
                        # 获取能执行此任务的账号
                        accounts = self.account_service.get_account_list(app_id)
                        for account in accounts:
                            status = self.task_manager.get_task_status(task['task_id'], account['account_id'])
                            if not status or not status.get('completed', False):
                                all_completed = False
                                break
                        if not all_completed:
                            break
                    
                    # 跳过已完成所有任务的应用
                    if all_completed:
                        continue
                    
                    return app_id
                
                # 所有应用都已完成任务或达到限制
                return None
                
            except Exception as e:
                self.log_error(f"获取下一个应用失败: {str(e)}")
                return None
    
    def update_app_runtime(self, app_id: str, seconds: int) -> bool:
        """更新应用运行时间
        
        参数:
            app_id: 应用ID
            seconds: 运行时间（秒）
            
        返回:
            成功返回True，否则返回False
        """
        try:
            # 获取当前活动账号
            account = self.account_service.get_current_account()
            if not account:
                self.log_warning(f"没有活动账号，无法更新应用 {app_id} 的运行时间")
                return False
            
            account_id = account['account_id']
            
            # 更新账号运行时间
            self.db_manager.execute(
                "UPDATE accounts SET daily_runtime = daily_runtime + ?, total_runtime = total_runtime + ? WHERE account_id = ?",
                (seconds, seconds, account_id)
            )
            
            self.log_info(f"应用 {app_id} 的运行时间已更新: +{seconds}秒")
            return True
        except Exception as e:
            self.log_error(f"更新应用运行时间失败: {str(e)}")
            return False
    
    def switch_to_app(self, app_id: str) -> bool:
        """切换到指定应用
        
        参数:
            app_id: 应用ID
            
        返回:
            成功返回True，否则返回False
        """
        with self.lock:
            try:
                # 检查应用是否存在
                app = self.db_manager.fetch_one(
                    "SELECT app_id, package_name FROM apps WHERE app_id = ?",
                    (app_id,)
                )
                
                if not app:
                    self.log_warning(f"应用不存在: {app_id}")
                    return False
                
                # 停止当前应用
                if self.current_app:
                    # 更新当前应用运行时间
                    runtime = int(time.time() - self.app_start_time)
                    self.update_app_runtime(self.current_app, runtime)
                    
                    # 停止当前应用
                    current_app = self.db_manager.fetch_one(
                        "SELECT package_name FROM apps WHERE app_id = ?",
                        (self.current_app,)
                    )
                    
                    if current_app and current_app['package_name']:
                        self.device_controller.stop_app(current_app['package_name'])
                
                # 切换到新应用
                if app['package_name']:
                    self.device_controller.start_app(app['package_name'])
                    self.device_controller.wait(5)  # 等待应用启动
                
                # 更新当前应用
                self.current_app = app_id
                self.app_start_time = time.time()
                
                # 更新应用状态
                self.db_manager.update(
                    "apps",
                    {"status": "active", "last_update": int(time.time())},
                    "app_id = ?",
                    (app_id,)
                )
                
                self.log_info(f"已切换到应用: {app_id}")
                return True
            except Exception as e:
                self.log_error(f"切换应用失败: {str(e)}")
                return False
    
    def get_app_status(self, app_id: str) -> Dict[str, Any]:
        """获取应用状态
        
        参数:
            app_id: 应用ID
            
        返回:
            应用状态字典
        """
        try:
            # 获取应用基本信息
            app = self.db_manager.fetch_one(
                "SELECT * FROM apps WHERE app_id = ?",
                (app_id,)
            )
            
            if not app:
                return {"status": "not_found", "message": f"应用 {app_id} 不存在"}
            
            # 获取应用账号信息
            accounts = self.db_manager.fetch_all(
                "SELECT account_id, SUM(daily_runtime) as daily_runtime FROM accounts WHERE app_id = ? GROUP BY account_id",
                (app_id,)
            )
            
            # 计算总运行时间
            total_daily_runtime = sum(acc['daily_runtime'] or 0 for acc in accounts)
            
            # 获取应用任务状态
            tasks = self.task_manager.get_task_list(app_id)
            task_status = {}
            
            for task in tasks:
                task_id = task['task_id']
                # 获取每个账号的任务状态
                account_statuses = {}
                
                for account in accounts:
                    account_id = account['account_id']
                    status = self.task_manager.get_task_status(task_id, account_id)
                    account_statuses[account_id] = status['completed'] if status else False
                
                # 计算完成率
                completed_count = sum(1 for status in account_statuses.values() if status)
                total_count = len(account_statuses)
                completion_rate = (completed_count / total_count) * 100 if total_count > 0 else 0
                
                task_status[task_id] = {
                    "name": task['name'],
                    "completed_count": completed_count,
                    "total_count": total_count,
                    "completion_rate": completion_rate,
                    "account_statuses": account_statuses
                }
            
            # 构建并返回状态信息
            result = {
                **app,
                "is_current": app_id == self.current_app,
                "daily_runtime": total_daily_runtime,
                "remaining_time": app['daily_limit'] - total_daily_runtime,
                "accounts_count": len(accounts),
                "tasks_status": task_status
            }
            
            return result
        except Exception as e:
            self.log_error(f"获取应用状态失败: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_app_list(self) -> List[Dict[str, Any]]:
        """获取应用列表
        
        返回:
            应用字典列表
        """
        try:
            apps = self.db_manager.fetch_all("SELECT * FROM apps ORDER BY priority")
            
            # 添加运行时间信息
            for app in apps:
                app_id = app['app_id']
                
                # 获取账号运行时间
                accounts = self.db_manager.fetch_all(
                    "SELECT SUM(daily_runtime) as daily_runtime FROM accounts WHERE app_id = ?",
                    (app_id,)
                )
                
                daily_runtime = accounts[0]['daily_runtime'] if accounts and accounts[0]['daily_runtime'] else 0
                app['daily_runtime'] = daily_runtime
                app['remaining_time'] = app['daily_limit'] - daily_runtime
                app['is_current'] = app_id == self.current_app
            
            return apps
        except Exception as e:
            self.log_error(f"获取应用列表失败: {str(e)}")
            return []
    
    def _scheduler_loop(self):
        """调度循环"""
        self.log_info("调度循环已启动")
        
        while self.running:
            try:
                # 1. 检查定时重置
                self._check_daily_reset()
                
                # 2. 检查是否需要切换应用
                current_time = time.time()
                
                if self.current_app:
                    # 计算当前应用已运行时间
                    runtime = int(current_time - self.app_start_time)
                    app = self.db_manager.fetch_one(
                        "SELECT time_slice FROM apps WHERE app_id = ?",
                        (self.current_app,)
                    )
                    
                    # 如果超过时间片或没有活动任务，切换应用
                    time_slice = app['time_slice'] if app else 7200  # 默认2小时
                    
                    if runtime >= time_slice:
                        self.log_info(f"应用 {self.current_app} 已达到时间片限制，准备切换")
                        next_app = self.get_next_app()
                        
                        if next_app and next_app != self.current_app:
                            self.switch_to_app(next_app)
                    
                    # 检查当前应用是否有活动任务
                    has_active_task = self.task_manager.has_active_tasks(self.current_app)
                    
                    if not has_active_task:
                        # 检查是否还有未完成的任务
                        next_task = self.task_manager.get_next_task(self.current_app, self.account_service.get_current_account()['account_id'])
                        
                        if not next_task:
                            # 没有更多任务，尝试切换账号
                            next_account = self.account_service.get_next_account(self.current_app)
                            
                            if not next_account:
                                # 没有更多账号，切换应用
                                self.log_info(f"应用 {self.current_app} 的所有账号都已完成任务，准备切换")
                                next_app = self.get_next_app()
                                
                                if next_app and next_app != self.current_app:
                                    self.switch_to_app(next_app)
                            else:
                                # 切换到下一个账号
                                self.account_service.switch_to_account(next_account)
                        else:
                            # 执行下一个任务
                            self.task_manager.execute_task_async(next_task)
                
                else:
                    # 没有当前应用，选择一个应用
                    next_app = self.get_next_app()
                    if next_app:
                        self.switch_to_app(next_app)
                    
                # 等待下一次检查
                time.sleep(30)  # 每30秒检查一次
                
            except Exception as e:
                self.log_error(f"调度循环出错: {str(e)}")
                time.sleep(60)  # 出错后等待1分钟
    
    def _check_daily_reset(self):
        """检查每日重置"""
        try:
            # 获取当前时间
            current_time = utils.get_current_time_string()
            
            # 获取需要重置的应用
            apps = self.db_manager.fetch_all(
                "SELECT app_id, reset_time FROM apps"
            )
            
            for app in apps:
                app_id = app['app_id']
                reset_time = app['reset_time']
                
                # 检查上次重置时间
                last_reset = self.db_manager.fetch_one(
                    "SELECT value FROM settings WHERE key = ?",
                    (f"last_reset_{app_id}",)
                )
                
                last_reset_date = last_reset['value'] if last_reset else None
                current_date = utils.current_date_string()
                
                # 如果当前时间已过重置时间，且今天还未重置
                if utils.is_time_now_after(current_time, reset_time) and current_date != last_reset_date:
                    # 执行重置
                    self.log_info(f"重置应用 {app_id} 的每日任务状态")
                    
                    # 重置账号的每日运行时间
                    self.db_manager.execute(
                        "UPDATE accounts SET daily_runtime = 0 WHERE app_id = ?",
                        (app_id,)
                    )
                    
                    # 重置每日任务状态
                    self.task_manager.reset_daily_tasks(app_id)
                    
                    # 更新最后重置时间
                    if last_reset:
                        self.db_manager.update(
                            "settings",
                            {"value": current_date},
                            "key = ?",
                            (f"last_reset_{app_id}",)
                        )
                    else:
                        self.db_manager.insert(
                            "settings",
                            {
                                "key": f"last_reset_{app_id}",
                                "value": current_date,
                                "description": f"应用 {app_id} 的上次重置日期"
                            }
                        )
        except Exception as e:
            self.log_error(f"检查每日重置出错: {str(e)}")


            # 在AppScheduler类中添加以下方法
    def get_app_task_directory(self, app_id):
        """获取应用任务目录
        Args:
            app_id: 应用ID
        Returns:
            任务目录路径
        """
        return f"tasks/{app_id.lower()}"

    def load_app_config(self, app_id, config_name=None):
        """加载应用特定配置
        Args:
            app_id: 应用ID
            config_name: 配置名称，为None则加载默认配置
        Returns:
            应用配置
        """
        if config_name is None:
            config_name = "app_config.json"
            
        config_path = os.path.join(self.get_app_task_directory(app_id), "config", config_name)
        return utils.load_json_file(config_path, {})

    def get_current_app_id(self) -> Optional[str]:
        """获取当前正在运行的应用ID"""
        return self.current_app_id

    def _start_status_check(self):
        """启动状态检查线程"""
        def status_check_loop():
            while self.is_initialized:
                try:
                    # 检查重置时间
                    self._check_daily_reset()
                    
                    # 日志当前状态
                    if self.current_app:
                        runtime = int(time.time() - self.app_start_time)
                        self.log_debug(f"当前应用: {self.current_app}, 运行时间: {runtime}秒")
                    
                    # 每10分钟检查一次
                    time.sleep(600)
                    
                except Exception as e:
                    self.log_error(f"状态检查出错: {str(e)}")
                    time.sleep(60)
        
        # 启动线程
        thread = threading.Thread(target=status_check_loop)
        thread.daemon = True
        thread.start()
