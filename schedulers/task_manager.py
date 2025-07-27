import logging
import threading
import time
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import importlib
import inspect

from core.interfaces import ITaskManager, ITask
from core.base_classes import SystemModule, Task
from data.database_manager import DatabaseManager
from core.utils import generate_id, current_timestamp

class TaskManager(SystemModule):
    """任务管理系统，负责任务注册、状态跟踪和执行调度"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        """初始化任务管理系统"""
        super().__init__("TaskManager", "1.0.0")
        self.db_manager = db_manager or DatabaseManager()
        self.tasks = {}  # 运行时任务实例字典
        self.active_tasks = {}  # 当前执行的任务
        self.task_threads = {}  # 任务执行线程
        self.task_lock = threading.Lock()
    
    def initialize(self) -> bool:
        """初始化任务管理系统"""
        if self.is_initialized:
            return True
            
        self.log_info("初始化任务管理系统...")
        
        # 创建必要的数据库表(如果还不存在)
        # 任务表和任务状态表在DatabaseManager中已创建
        
        # 加载已注册的任务类
        self._load_registered_tasks()
        
        return super().initialize()
    
    def _load_registered_tasks(self):
        """从数据库加载已注册的任务类"""
        try:
            tasks = self.db_manager.fetch_all(
               "SELECT * FROM tasks WHERE enabled = 1"
            )
        
            for task_info in tasks:
            # 检查是否有handler_class
                if task_info['handler_class']:
                    try:
                        handler_class = task_info['handler_class']
                    
                    # 处理只有类名的情况
                        if '.' not in handler_class:
                            self.log_warning(f"任务 {task_info['task_id']} 的handler_class不完整: {handler_class}")
                        # 尝试在常见模块中查找
                            possible_modules = [
                                f"tasks.three_kingdoms.sub_tasks.{handler_class.lower()}.{handler_class}",
                                f"tasks.three_kingdoms.{handler_class.lower()}.{handler_class}"
                            ]
                        
                            found = False
                            for module_path in possible_modules:
                                try:
                                # 尝试导入
                                    parts = module_path.rsplit('.', 1)
                                    if len(parts) == 2:
                                        module_name, class_name = parts
                                        module = importlib.import_module(module_name)
                                        if hasattr(module, class_name):
                                        # 找到了类，更新数据库
                                            self.db_manager.update(
                                                'tasks',
                                                {'handler_class': module_path},
                                                'task_id = ?',
                                                (task_info['task_id'],)
                                            )
                                            handler_class = module_path
                                            found = True
                                            self.log_info(f"已自动修复任务 {task_info['task_id']} 的handler_class为: {module_path}")
                                            break
                                except:
                                    continue
                        
                            if not found:
                                self.log_error(f"无法自动修复任务 {task_info['task_id']} 的handler_class")
                                continue
                    
                    # 尝试动态导入任务处理类
                        module_path, class_name = handler_class.rsplit('.', 1)
                        module = importlib.import_module(module_path)
                        task_class = getattr(module, class_name)
                    
                    # 将任务类添加到运行时任务字典
                        self.tasks[task_info['task_id']] = {
                            'class': task_class,
                            'info': task_info,
                            'instance': None
                        }
                    
                        self.log_info(f"已加载任务类: {task_info['name']} ({task_info['task_id']})")
                    except Exception as e:
                        self.log_error(f"无法加载任务类 {task_info['handler_class']}: {str(e)}")
        
            self.log_info(f"共加载 {len(self.tasks)} 个任务")
        
        except Exception as e:
            self.log_error(f"加载注册任务时出错: {str(e)}")
    
    def register_task(self, task_class, task_config: Dict[str, Any] = None) -> str:
        """注册一个任务
        
        Args:
            task_class: 任务类
            task_config: 任务配置
            
        Returns:
            任务ID
        """
        # 检查任务类是否实现了ITask接口
        if not issubclass(task_class, ITask):
            self.log_error(f"任务类 {task_class.__name__} 必须实现ITask接口")
            raise ValueError(f"任务类 {task_class.__name__} 必须实现ITask接口")
        
        # 生成任务配置
        config = task_config or {}
        task_name = config.get('name', task_class.__name__)
        app_id = config.get('app_id', '')
        
        if not app_id:
            self.log_error("必须指定app_id")
            raise ValueError("必须指定app_id")
        
        # 生成任务ID
        task_id = config.get('task_id', generate_id(f"task_{task_name}_"))
        
        # 创建任务数据
        task_data = {
            'task_id': task_id,
            'app_id': app_id,
            'name': task_name,
            'parent_id': config.get('parent_id'),
            'type': config.get('type', 'daily'),
            'priority': config.get('priority', 5),
            'max_retries': config.get('max_retries', 3),
            'timeout': config.get('timeout', 300),
            'description': config.get('description', ''),
            'config': json.dumps(config.get('config', {})),
            'handler_class': f"{task_class.__module__}.{task_class.__name__}",
            'enabled': 1
        }
        
        try:
            # 检查任务是否已存在
            existing = self.db_manager.fetch_one(
                "SELECT task_id FROM tasks WHERE task_id = ?", 
                (task_id,)
            )
            
            if existing:
                # 更新现有任务
                self.db_manager.update(
                    'tasks',
                    task_data,
                    'task_id = ?',
                    (task_id,)
                )
                self.log_info(f"已更新任务: {task_name} ({task_id})")
            else:
                # 插入新任务
                self.db_manager.insert('tasks', task_data)
                self.log_info(f"已注册任务: {task_name} ({task_id})")
            
            # 将任务类添加到运行时任务字典
            self.tasks[task_id] = {
                'class': task_class,
                'info': task_data,
                'instance': None
            }
            
            return task_id
            
        except Exception as e:
            self.log_error(f"注册任务时出错: {str(e)}")
            raise
    
    def unregister_task(self, task_id: str) -> bool:
        """注销一个任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            成功返回True，否则返回False
        """
        try:
            # 检查任务是否正在执行
            if task_id in self.active_tasks:
                self.log_warning(f"任务 {task_id} 正在执行中，无法注销")
                return False
            
            # 从数据库中删除任务
            self.db_manager.update(
                'tasks',
                {'enabled': 0},
                'task_id = ?',
                (task_id,)
            )
            
            # 从运行时任务字典中移除
            if task_id in self.tasks:
                del self.tasks[task_id]
                
            self.log_info(f"已注销任务: {task_id}")
            return True
            
        except Exception as e:
            self.log_error(f"注销任务时出错: {str(e)}")
            return False
    
    def execute_task(self, task_id: str) -> bool:
        """执行一个任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            成功返回True，否则返回False
        """
        try:
            # 检查任务是否存在
            if task_id not in self.tasks:
                self.log_error(f"任务 {task_id} 不存在")
                return False
            
            task_info = self.tasks[task_id]
            task_class = task_info['class']
            
            # 获取任务配置
            config = {}
            if task_info['info']['config']:
                config = json.loads(task_info['info']['config'])
            
            # 创建任务实例
            task_instance = task_class(
                task_id,
                task_info['info']['name'],
                task_info['info']['app_id'],
                task_info['info']['parent_id']
            )
            
            # 启动任务监控
            task_instance.start_monitor(config)
            
            # 执行任务
            result = task_instance.execute()
            
            # 停止任务监控
            task_instance.stop_monitor()
            
            # 记录任务执行结果
            self._update_task_execution_result(task_id, None, result)
            
            return result
            
        except Exception as e:
            self.log_error(f"执行任务时出错: {str(e)}")
            self._update_task_execution_result(task_id, None, False, error=str(e))
            return False
    
    def execute_task_async(self, task_id: str) -> bool:
        """异步执行一个任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            成功启动返回True，否则返回False
        """
        with self.task_lock:
            try:
                # 检查任务是否存在
                if task_id not in self.tasks:
                    self.log_error(f"任务 {task_id} 不存在")
                    return False
                
                # 检查任务是否已在执行
                if task_id in self.active_tasks:
                    self.log_warning(f"任务 {task_id} 已在执行中")
                    return False
                
                task_info = self.tasks[task_id]
                task_class = task_info['class']
                
                # 获取任务配置
                config = {}
                if task_info['info']['config']:
                    config = json.loads(task_info['info']['config'])
                
                # 创建任务实例
                task_instance = task_class(
                    task_id,
                    task_info['info']['name'],
                    task_info['info']['app_id'],
                    task_info['info']['parent_id']
                )
                
                # 保存任务实例
                self.tasks[task_id]['instance'] = task_instance
                self.active_tasks[task_id] = task_instance
                
                # 创建执行线程
                thread = threading.Thread(
                    target=self._task_thread_function,
                    args=(task_id, task_instance, config)
                )
                thread.daemon = True
                
                # 保存线程引用
                self.task_threads[task_id] = thread
                
                # 启动线程
                thread.start()
                
                self.log_info(f"已异步启动任务: {task_id}")
                return True
                
            except Exception as e:
                self.log_error(f"异步启动任务时出错: {str(e)}")
                
                # 清理
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
                    
                return False
    
    def _task_thread_function(self, task_id: str, task_instance: ITask, config: Dict[str, Any]):
        """任务执行线程
        
        Args:
            task_id: 任务ID
            task_instance: 任务实例
            config: 任务配置
        """
        try:
            # 获取任务信息
            task_info = self.tasks[task_id]['info']
            
            # 获取账号ID（从当前执行上下文）
            account_id = self._get_current_account_id(task_id)
            
            # 启动任务监控
            task_instance.start_monitor(config)
            
            # 获取最大重试次数
            max_retries = task_info['max_retries']
            retry_count = 0
            result = False
            
            # 执行任务，支持重试
            while retry_count <= max_retries and not result:
                try:
                    self.log_info(f"执行任务 {task_id}" + 
                                 (f" (重试 {retry_count}/{max_retries})" if retry_count > 0 else ""))
                    
                    result = task_instance.execute()
                    
                    if not result and retry_count < max_retries:
                        retry_count += 1
                        self.log_warning(f"任务 {task_id} 执行失败，准备重试")
                        time.sleep(2)  # 重试前等待
                    
                except Exception as e:
                    self.log_error(f"任务 {task_id} 执行出错: {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        self.log_warning(f"任务 {task_id} 执行出错，准备重试")
                        time.sleep(2)  # 重试前等待
                    else:
                        raise
            
            # 停止任务监控
            task_instance.stop_monitor()
            
            # 更新任务执行结果
            self._update_task_execution_result(task_id, account_id, result)
            
            self.log_info(f"任务 {task_id} 执行完成，结果: {'成功' if result else '失败'}")
            
        except Exception as e:
            self.log_error(f"任务线程执行出错: {str(e)}")
            
            # 确保停止监控
            try:
                task_instance.stop_monitor()
            except:
                pass
                
            # 更新任务执行结果
            self._update_task_execution_result(task_id, account_id, False, error=str(e))
            
        finally:
            # 清理
            with self.task_lock:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                if task_id in self.task_threads:
                    del self.task_threads[task_id]
    
    def _get_current_account_id(self, task_id: str) -> Optional[str]:
        """获取当前执行上下文的账号ID
        
        Args:
            task_id: 任务ID
            
        Returns:
            账号ID，如果不可用则返回None
        """
        # 这里应该通过某种方式获取当前上下文中的账号ID
        # 可能需要与AccountService模块集成
        # 临时实现：从数据库中查询最近一次执行该任务的账号
        try:
            row = self.db_manager.fetch_one(
                "SELECT account_id FROM task_status WHERE task_id = ? ORDER BY last_run_time DESC LIMIT 1",
                (task_id,)
            )
            return row['account_id'] if row else None
        except:
            return None
    
    def _update_task_execution_result(self, task_id: str, account_id: Optional[str], result: bool, error: str = None):
        """更新任务执行结果
        
        Args:
            task_id: 任务ID
            account_id: 账号ID
            result: 执行结果
            error: 错误信息
        """
        if not account_id:
            # 没有关联账号，只记录日志
            self.log_info(f"任务 {task_id} 执行结果: {'成功' if result else '失败'}" +
                         (f", 错误: {error}" if error else ""))
            return
            
        # 更新数据库中的任务状态
        now = current_timestamp()
        
        # 检查是否已有状态记录
        existing = self.db_manager.fetch_one(
            "SELECT status_id FROM task_status WHERE account_id = ? AND task_id = ?",
            (account_id, task_id)
        )
        
        if existing:
            # 更新现有记录
            self.db_manager.update(
                'task_status',
                {
                    'completed': 1 if result else 0,
                    'completion_time': now if result else None,
                    'last_run_time': now,
                    'last_error': error,
                    'execution_data': json.dumps(self.tasks[task_id]['instance'].get_status() if result else {})
                },
                'account_id = ? AND task_id = ?',
                (account_id, task_id)
            )
        else:
            # 创建新记录
            self.db_manager.insert(
                'task_status',
                {
                    'account_id': account_id,
                    'task_id': task_id,
                    'completed': 1 if result else 0,
                    'completion_time': now if result else None,
                    'last_run_time': now,
                    'retry_count': 0,
                    'last_error': error,
                    'execution_data': json.dumps(self.tasks[task_id]['instance'].get_status() if result else {})
                }
            )
        
        # 记录活动
        self.db_manager.log_activity(
            'task_execution',
            'success' if result else 'failure',
            self.tasks[task_id]['info']['app_id'],
            account_id,
            task_id,
            error
        )
    
    def stop_task(self, task_id: str) -> bool:
        """停止一个正在运行的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            成功返回True，否则返回False
        """
        with self.task_lock:
            if task_id not in self.active_tasks:
                self.log_warning(f"任务 {task_id} 未在执行中")
                return False
                
            try:
                # 获取任务实例
                task_instance = self.active_tasks[task_id]
                
                # 停止任务监控
                task_instance.stop_monitor()
                
                # 记录停止操作
                self.log_info(f"已停止任务: {task_id}")
                
                # 清理
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                    
                # 线程会自行结束
                
                return True
                
            except Exception as e:
                self.log_error(f"停止任务时出错: {str(e)}")
                return False
    
    def get_task_status(self, task_id: str, account_id: str = None) -> Dict[str, Any]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            account_id: 可选账号ID
            
        Returns:
            任务状态字典
        """
        try:
            # 获取任务基本信息
            task_info = None
            if task_id in self.tasks:
                task_info = self.tasks[task_id]['info']
            else:
                task_row = self.db_manager.fetch_one(
                    "SELECT * FROM tasks WHERE task_id = ?",
                    (task_id,)
                )
                if not task_row:
                    return {"status": "not_found", "message": f"任务 {task_id} 不存在"}
                task_info = task_row
            
            # 检查是否在执行中
            is_running = task_id in self.active_tasks
            
            result = {
                "task_id": task_id,
                "name": task_info['name'],
                "app_id": task_info['app_id'],
                "type": task_info['type'],
                "status": "running" if is_running else "idle",
                "parent_id": task_info['parent_id']
            }
            
            # 如果指定了账号，获取特定账号的任务状态
            if account_id:
                status_row = self.db_manager.fetch_one(
                    "SELECT * FROM task_status WHERE account_id = ? AND task_id = ?",
                    (account_id, task_id)
                )
                
                if status_row:
                    result.update({
                        "account_id": account_id,
                        "completed": bool(status_row['completed']),
                        "completion_time": status_row['completion_time'],
                        "last_run_time": status_row['last_run_time'],
                        "retry_count": status_row['retry_count'],
                        "last_error": status_row['last_error']
                    })
                    
                    # 解析执行数据
                    if status_row['execution_data']:
                        try:
                            result["execution_data"] = json.loads(status_row['execution_data'])
                        except:
                            result["execution_data"] = {}
            
            return result
            
        except Exception as e:
            self.log_error(f"获取任务状态时出错: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def update_task_status(self, task_id: str, account_id: str, status: Dict[str, Any]) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            account_id: 账号ID
            status: 状态字典
            
        Returns:
            成功返回True，否则返回False
        """
        try:
            # 检查任务是否存在
            if not self.db_manager.exists(
                "tasks", 
                "task_id = ?", 
                (task_id,)
            ):
                self.log_error(f"任务 {task_id} 不存在")
                return False
                
            # 检查账号是否存在
            if not self.db_manager.exists(
                "accounts", 
                "account_id = ?", 
                (account_id,)
            ):
                self.log_error(f"账号 {account_id} 不存在")
                return False
            
            # 检查是否已有状态记录
            existing = self.db_manager.fetch_one(
                "SELECT status_id FROM task_status WHERE account_id = ? AND task_id = ?",
                (account_id, task_id)
            )
            
            # 准备更新数据
            now = current_timestamp()
            update_data = {
                'last_run_time': now
            }
            
            # 添加状态数据
            if 'completed' in status:
                update_data['completed'] = 1 if status['completed'] else 0
                if status['completed']:
                    update_data['completion_time'] = now
            
            if 'retry_count' in status:
                update_data['retry_count'] = status['retry_count']
                
            if 'error' in status:
                update_data['last_error'] = status['error']
                
            if 'execution_data' in status:
                update_data['execution_data'] = json.dumps(status['execution_data'])
            
            if existing:
                # 更新现有记录
                self.db_manager.update(
                    'task_status',
                    update_data,
                    'account_id = ? AND task_id = ?',
                    (account_id, task_id)
                )
            else:
                # 创建新记录
                update_data['account_id'] = account_id
                update_data['task_id'] = task_id
                self.db_manager.insert('task_status', update_data)
            
            # 记录活动
            self.db_manager.log_activity(
                'task_status_update',
                'success',
                None,
                account_id,
                task_id,
                f"状态更新为: {status.get('completed', False)}"
            )
            
            return True
            
        except Exception as e:
            self.log_error(f"更新任务状态时出错: {str(e)}")
            return False
    
    def get_next_task(self, app_id: str, account_id: str) -> Optional[str]:
        """获取下一个要执行的任务
        
        Args:
            app_id: 应用ID
            account_id: 账号ID
            
        Returns:
            任务ID，如果没有待执行任务则返回None
        """
        try:
            # 获取应用的所有任务
            tasks = self.db_manager.fetch_all(
                """
                SELECT t.* 
                FROM tasks t
                WHERE t.app_id = ? AND t.enabled = 1
                ORDER BY t.priority DESC
                """,
                (app_id,)
            )
            
            if not tasks:
                return None
                
            # 获取账号的任务状态
            task_status = self.db_manager.fetch_all(
                """
                SELECT ts.task_id, ts.completed
                FROM task_status ts
                WHERE ts.account_id = ?
                """,
                (account_id,)
            )
            
            # 创建已完成任务集合
            completed_tasks = {ts['task_id'] for ts in task_status if ts['completed']}
            
            # 找出所有未完成的顶级任务
            top_level_tasks = [t for t in tasks if t['parent_id'] is None and t['task_id'] not in completed_tasks]
            
            if not top_level_tasks:
                return None  # 所有顶级任务已完成
                
            # 选择优先级最高的未完成顶级任务
            next_task = max(top_level_tasks, key=lambda t: t['priority'])
            
            # 如果是父任务，查找其未完成的子任务
            if self._has_children(next_task['task_id']):
                child_task_id = self._get_next_child_task(next_task['task_id'], completed_tasks)
                if child_task_id:
                    return child_task_id
            
            return next_task['task_id']
            
        except Exception as e:
            self.log_error(f"获取下一个任务时出错: {str(e)}")
            return None
    
    def _has_children(self, task_id: str) -> bool:
        """检查任务是否有子任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            如果有子任务返回True，否则返回False
        """
        count = self.db_manager.count(
            "tasks",
            "parent_id = ?",
            (task_id,)
        )
        return count > 0
    
    def _get_next_child_task(self, parent_id: str, completed_tasks: set) -> Optional[str]:
        """获取下一个未完成的子任务
        
        Args:
            parent_id: 父任务ID
            completed_tasks: 已完成任务ID集合
            
        Returns:
            子任务ID，如果所有子任务已完成则返回None
        """
        try:
            # 获取所有子任务
            child_tasks = self.db_manager.fetch_all(
                """
                SELECT * 
                FROM tasks
                WHERE parent_id = ? AND enabled = 1
                ORDER BY priority DESC
                """,
                (parent_id,)
            )
            
            # 找出未完成的子任务
            uncompleted_tasks = [t for t in child_tasks if t['task_id'] not in completed_tasks]
            
            if not uncompleted_tasks:
                return None  # 所有子任务已完成
                
            # 选择优先级最高的未完成子任务
            next_task = max(uncompleted_tasks, key=lambda t: t['priority'])
            return next_task['task_id']
            
        except Exception as e:
            self.log_error(f"获取下一个子任务时出错: {str(e)}")
            return None
    
    def get_task_list(self, app_id: str = None, parent_id: str = None) -> List[Dict[str, Any]]:
        """获取任务列表
        
        Args:
            app_id: 可选应用ID过滤
            parent_id: 可选父任务ID过滤
            
        Returns:
            任务字典列表
        """
        try:
            query = "SELECT * FROM tasks WHERE enabled = 1"
            params = []
            
            if app_id:
                query += " AND app_id = ?"
                params.append(app_id)
                
            if parent_id is not None:  # 允许parent_id为None
                query += " AND parent_id " + ("IS NULL" if parent_id is None else "= ?")
                if parent_id is not None:
                    params.append(parent_id)
            
            query += " ORDER BY priority DESC"
            
            tasks = self.db_manager.fetch_all(query, tuple(params))
            
            # 解析配置数据
            for task in tasks:
                if task['config']:
                    try:
                        task['config'] = json.loads(task['config'])
                    except:
                        task['config'] = {}
            
            return tasks
            
        except Exception as e:
            self.log_error(f"获取任务列表时出错: {str(e)}")
            return []
    
    def reset_daily_tasks(self, app_id: str = None) -> bool:
        """重置每日任务状态
        
        Args:
            app_id: 可选应用ID过滤
            
        Returns:
            成功返回True，否则返回False
        """
        try:
            query = """
            UPDATE task_status
            SET completed = 0, completion_time = NULL
            WHERE task_id IN (
                SELECT task_id FROM tasks 
                WHERE type = 'daily'
            """
            
            params = []
            if app_id:
                query += " AND app_id = ?"
                params.append(app_id)
                
            query += ")"
            
            self.db_manager.execute(query, tuple(params))
            
            self.log_info(f"已重置每日任务状态" + (f" (应用: {app_id})" if app_id else ""))
            return True
            
        except Exception as e:
            self.log_error(f"重置每日任务状态时出错: {str(e)}")
            return False
    
    def reset_weekly_tasks(self, app_id: str = None) -> bool:
        """重置每周任务状态
        
        Args:
            app_id: 可选应用ID过滤
            
        Returns:
            成功返回True，否则返回False
        """
        try:
            query = """
            UPDATE task_status
            SET completed = 0, completion_time = NULL
            WHERE task_id IN (
                SELECT task_id FROM tasks 
                WHERE type = 'weekly'
            """
            
            params = []
            if app_id:
                query += " AND app_id = ?"
                params.append(app_id)
                
            query += ")"
            
            self.db_manager.execute(query, tuple(params))
            
            self.log_info(f"已重置每周任务状态" + (f" (应用: {app_id})" if app_id else ""))
            return True
            
        except Exception as e:
            self.log_error(f"重置每周任务状态时出错: {str(e)}")
            return False
    
    def is_task_completed(self, task_id: str, account_id: str) -> bool:
        """检查任务是否已完成
        
        Args:
            task_id: 任务ID
            account_id: 账号ID
            
        Returns:
            如果任务已完成返回True，否则返回False
        """
        try:
            row = self.db_manager.fetch_one(
                "SELECT completed FROM task_status WHERE account_id = ? AND task_id = ?",
                (account_id, task_id)
            )
            
            return bool(row and row['completed'])
            
        except Exception as e:
            self.log_error(f"检查任务完成状态时出错: {str(e)}")
            return False

            # 在TaskManager类中添加以下方法

def get_current_task(self) -> Optional[str]:
    """获取当前正在执行的任务名称"""
    return self.current_task_name

def import_task_class(self, module_path):
    """从模块路径导入任务类"""
    try:
        self.log_info(f"尝试导入模块路径: {module_path}")
        module_parts = module_path.split('.')
        self.log_info(f"拆分后的模块部分: {module_parts}")
        module_name = '.'.join(module_parts[:-1])
        class_name = module_parts[-1]
        self.log_info(f"模块名: {module_name}, 类名: {class_name}")
        
        module = importlib.import_module(module_name)
        self.log_info(f"成功导入模块: {module}")
        
        task_class = getattr(module, class_name)
        self.log_info(f"成功获取类: {task_class}")
        
        return task_class
    except Exception as e:
        self.log_error(f"导入任务类失败: {str(e)}")
        import traceback
        self.log_error(f"详细错误: {traceback.format_exc()}")
        return None
            
    def register_task_from_module(self, module_path, task_config):
        """从模块路径注册任务
        Args:
            module_path: 模块路径
            task_config: 任务配置
        Returns:
            任务ID
        """
        task_class = self.import_task_class(module_path)
        if task_class:
            return self.register_task(task_class, task_config)
        return None
    
    def are_all_tasks_completed(self, app_id: str, account_id: str) -> bool:
        """检查应用的所有任务是否已完成
        
        Args:
            app_id: 应用ID
            account_id: 账号ID
            
        Returns:
            如果所有任务已完成返回True，否则返回False
        """
        try:
            # 获取应用的所有任务
            total_tasks = self.db_manager.count(
                "tasks",
                "app_id = ? AND enabled = 1",
                (app_id,)
            )
            
            if total_tasks == 0:
                return True  # 没有任务
                
            # 获取已完成的任务数量
            completed_tasks = self.db_manager.count(
                """
                SELECT COUNT(*) as count
                FROM task_status ts
                JOIN tasks t ON ts.task_id = t.task_id
                WHERE t.app_id = ? AND ts.account_id = ? AND ts.completed = 1
                """,
                (app_id, account_id)
            )
            
            return completed_tasks >= total_tasks
            
        except Exception as e:
            self.log_error(f"检查所有任务完成状态时出错: {str(e)}")
            return False
    
    def shutdown(self) -> bool:
        """关闭任务管理系统"""
        # 停止所有正在运行的任务
        running_tasks = list(self.active_tasks.keys())
        for task_id in running_tasks:
            self.stop_task(task_id)
        
        # 等待所有任务线程结束
        for thread in self.task_threads.values():
            thread.join(timeout=5)
        
        self.log_info("任务管理系统已关闭")
        return super().shutdown()
