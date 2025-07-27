import threading
import os
import time
import logging
from typing import Any, Dict, List, Optional, Callable, Tuple
import sqlite3  # 如果还没有导入的话
import json     # 如果还没有导入的话
from core.interfaces import IStateManager, IScreenRecognizer, ISystemModule, IDatabaseManager
from core.base_classes import SystemModule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("state_manager.log"), logging.StreamHandler()]
)
logger = logging.getLogger('state_manager')

class StateManager(SystemModule, IStateManager):
    """状态管理器，负责识别和管理屏幕状态，提供状态变化回调"""
    
    def __init__(self, db_manager: IDatabaseManager, screen_recognizer: IScreenRecognizer):
        """初始化状态管理器
        
        Args:
            db_manager: 数据库管理器实例
            screen_recognizer: 屏幕识别器实例
        """
        super().__init__("StateManager", "1.0.0")
        self.db = db_manager
        self.recognizer = screen_recognizer
        self.current_state = None
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 2.0
        self.state_callbacks = {}
        self.lock = threading.Lock()
    
    def initialize(self) -> bool:
        """初始化状态管理器
        
        Returns:
            初始化是否成功
        """
        if self.is_initialized:
            return True
            
        self.log_info("初始化状态管理器...")
        
        # 确保数据库和屏幕识别器已初始化
        if not self.recognizer.is_initialized:
            self.log_error("屏幕识别器未初始化")
            return False
        
        # 从数据库加载已注册的状态
        try:
            states = self.db.fetch_all("SELECT * FROM recognition_states")
            for state in states:
                state_id = state['state_id']
                self.state_callbacks[state_id] = None
                self.log_info(f"已加载状态: {state_id}")
        except Exception as e:
            self.log_error(f"加载状态失败: {str(e)}")
            return False
        
        return super().initialize()
    
    def shutdown(self) -> bool:
        """关闭状态管理器
        
        Returns:
            关闭是否成功
        """
        self.stop_monitoring()
        self.log_info("状态管理器已关闭")
        return super().shutdown()
    
    def register_state(self, state_id: str, app_id: str, recognition_config: Dict[str, Any], callback=None) -> bool:
        """注册状态
        
        Args:
            state_id: 状态ID
            app_id: 应用ID
            recognition_config: 状态识别配置
            callback: 可选的状态变化回调函数
            
        Returns:
            注册是否成功
        """
        with self.lock:
            try:
                # 检查状态是否已存在
                if self.db.exists("recognition_states", "state_id = ?", (state_id,)):
                    # 更新状态配置
                    self.db.update(
                        "recognition_states",
                        {
                            "app_id": app_id,
                            "name": recognition_config.get('name', state_id),
                            "type": recognition_config.get('type', 'text'),
                            "config": json.dumps(recognition_config)
                        },
                        "state_id = ?",
                        (state_id,)
                    )
                    self.log_info(f"更新状态: {state_id}")
                else:
                    # 插入新状态
                    self.db.insert(
                        "recognition_states",
                        {
                            "state_id": state_id,
                            "app_id": app_id,
                            "name": recognition_config.get('name', state_id),
                            "type": recognition_config.get('type', 'text'),
                            "config": json.dumps(recognition_config)
                        }
                    )
                    self.log_info(f"注册状态: {state_id}")
                
                # 保存回调函数
                self.state_callbacks[state_id] = callback
                return True
                
            except Exception as e:
                self.log_error(f"注册状态失败: {str(e)}")
                return False
    
    def unregister_state(self, state_id: str) -> bool:
        """注销状态
        
        Args:
            state_id: 状态ID
            
        Returns:
            注销是否成功
        """
        with self.lock:
            try:
                # 删除状态记录
                if self.db.exists("recognition_states", "state_id = ?", (state_id,)):
                    self.db.delete("recognition_states", "state_id = ?", (state_id,))
                    
                    # 删除相关的动作
                    self.db.delete("actions", "from_state = ? OR to_state = ?", (state_id, state_id))
                    
                    # 删除回调函数
                    if state_id in self.state_callbacks:
                        del self.state_callbacks[state_id]
                        
                    self.log_info(f"注销状态: {state_id}")
                    return True
                else:
                    self.log_warning(f"状态不存在: {state_id}")
                    return False
                    
            except Exception as e:
                self.log_error(f"注销状态失败: {str(e)}")
                return False
    
    def start_monitoring(self, interval: float = 2.0) -> bool:
        """开始状态监控
        
        Args:
            interval: 监控间隔（秒）
            
        Returns:
            是否成功启动监控
        """
        if self.monitoring:
            return True
        
        self.monitor_interval = interval
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.log_info(f"状态监控已启动，间隔: {interval}秒")
        return True
    
    def stop_monitoring(self) -> bool:
        """停止状态监控
        
        Returns:
            是否成功停止监控
        """
        if not self.monitoring:
            return True
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=3)
            self.monitor_thread = None
        self.log_info("状态监控已停止")
        return True
    
    def get_current_state(self) -> Optional[str]:
        """获取当前状态
        
        Returns:
            当前状态ID，如果未知则返回None
        """
        return self.current_state

    def _recognize_from_db(self, db_connection, app_id=None, task_name=None):
        """从指定数据库连接识别场景

        Args:
            db_connection: 数据库连接
            app_id: 应用ID
            task_name: 任务名称，用于处理相对路径

        Returns:
            状态ID或None
        """
        cursor = db_connection.cursor()

        # 确定表名 - 优先使用states表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='states'")
        if cursor.fetchone():
            table_name = "states"
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recognition_states'")
            if cursor.fetchone():
                table_name = "recognition_states"
            else:
                return None

        # 构建查询条件
        condition = "1=1"
        params = ()

        if app_id:
            condition += " AND app_id = ?"
            params = (app_id,)

        # 获取所有状态配置
        cursor.execute(f"SELECT * FROM {table_name} WHERE {condition}", params)
        states = cursor.fetchall()

        # 项目根目录，用于处理相对路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        for state in states:
            state_id = state['state_id']
            state_type = state['type']

            try:
                config = json.loads(state['config'])
            except:
                self.log_warning(f"解析状态配置失败: {state_id}")
                continue

            # 基于状态类型执行不同的识别逻辑
            if state_type == 'text':
                result = self.recognizer.find_text(
                    config.get('target_text'),
                    config.get('lang'),
                    config.get('config'),
                    config.get('roi'),
                    config.get('threshold', 0.6)
                )

                if result:
                    self.log_info(f"识别到文本状态: {state_id}")
                    return state_id

            elif state_type == 'image':
                # 处理模板路径
                template_path = config.get('template_path')

                if template_path:
                    # 如果是相对路径且提供了任务名称，转换为绝对路径
                    if not os.path.isabs(template_path) and task_name:
                        task_dir = os.path.join(project_root, "tasks", task_name)
                        template_path = os.path.join(task_dir, template_path)

                    result = self.recognizer.find_image(
                        template_path,
                        config.get('threshold', 0.8),
                        config.get('roi')
                    )

                    if result:
                        self.log_info(f"识别到图像状态: {state_id}")
                        return state_id

        return None

    def recognize_current_scene(self, app_id: str = None, task_name: str = None) -> Optional[str]:
        """识别当前场景

        Args:
            app_id: 应用ID
            task_name: 当前任务名称，如果提供，则也会查询任务数据库

        Returns:
            场景状态ID，如果无法识别则返回None
        """
        try:
            # 首先尝试从主数据库识别
            scene = self._recognize_from_db(self.db, app_id)
            if scene:
                return scene

            # 如果提供了任务名称，也尝试从任务数据库识别
            if task_name:
                # 构建任务数据库路径
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(project_root, "tasks", task_name, "db", f"{task_name}.db")

                if os.path.exists(db_path):
                    try:
                        # 连接任务数据库
                        task_conn = sqlite3.connect(db_path)
                        task_conn.row_factory = sqlite3.Row

                        # 从任务数据库识别
                        scene = self._recognize_from_db(task_conn, app_id, task_name)

                        task_conn.close()

                        if scene:
                            return scene

                    except Exception as e:
                        self.log_error(f"从任务数据库识别失败: {str(e)}")

            self.log_debug("无法识别当前场景")
            return None

        except Exception as e:
            self.log_error(f"识别场景出错: {str(e)}")
            return None
    
    def register_state_transition(self, from_state: str, to_state: str, 
                                  action_name: str, function_name: str, 
                                  params: Dict[str, Any] = None) -> bool:
        """注册状态转换动作
        
        Args:
            from_state: 起始状态ID
            to_state: 目标状态ID
            action_name: 动作名称
            function_name: 函数名称
            params: 函数参数
            
        Returns:
            注册是否成功
        """
        try:
            # 检查状态是否存在
            if not self.db.exists("recognition_states", "state_id = ?", (from_state,)):
                self.log_error(f"起始状态不存在: {from_state}")
                return False
                
            if not self.db.exists("recognition_states", "state_id = ?", (to_state,)):
                self.log_error(f"目标状态不存在: {to_state}")
                return False
            
            # 插入或更新动作
            action_data = {
                "from_state": from_state,
                "to_state": to_state,
                "name": action_name,
                "function_name": function_name,
                "params": json.dumps(params or {})
            }
            
            # 检查是否已存在相同的转换
            existing = self.db.fetch_one(
                "SELECT action_id FROM actions WHERE from_state = ? AND to_state = ?",
                (from_state, to_state)
            )
            
            if existing:
                # 更新现有动作
                self.db.update(
                    "actions",
                    action_data,
                    "action_id = ?",
                    (existing['action_id'],)
                )
                self.log_info(f"更新状态转换: {from_state} -> {to_state}")
            else:
                # 插入新动作
                self.db.insert("actions", action_data)
                self.log_info(f"注册状态转换: {from_state} -> {to_state}")
                
            return True
            
        except Exception as e:
            self.log_error(f"注册状态转换失败: {str(e)}")
            return False
    
    def find_path(self, current_state: str, target_state: str) -> List[Dict[str, Any]]:
        """查找从当前状态到目标状态的路径
        
        Args:
            current_state: 当前状态ID
            target_state: 目标状态ID
            
        Returns:
            状态转换动作列表
        """
        try:
            # BFS搜索状态转换路径
            visited = set()
            queue = [(current_state, [])]
            
            while queue:
                state, path = queue.pop(0)
                
                if state == target_state:
                    return path
                
                if state in visited:
                    continue
                    
                visited.add(state)
                
                # 获取所有可能的转换
                transitions = self.db.fetch_all(
                    "SELECT * FROM actions WHERE from_state = ?",
                    (state,)
                )
                
                for transition in transitions:
                    next_state = transition['to_state']
                    if next_state not in visited:
                        # 构建动作信息
                        action = {
                            'from_state': state,
                            'to_state': next_state,
                            'name': transition['name'],
                            'function_name': transition['function_name'],
                            'params': json.loads(transition['params'])
                        }
                        
                        queue.append((next_state, path + [action]))
            
            self.log_warning(f"找不到从 {current_state} 到 {target_state} 的路径")
            return []
            
        except Exception as e:
            self.log_error(f"查找路径失败: {str(e)}")
            return []
    
    def navigate_to_state(self, target_state: str, device_controller, max_attempts: int = 3) -> bool:
        """导航到指定状态
        
        Args:
            target_state: 目标状态ID
            device_controller: 设备控制器实例
            max_attempts: 最大尝试次数
            
        Returns:
            导航是否成功
        """
        for attempt in range(max_attempts):
            # 识别当前状态
            current_state = self.recognize_current_scene()
            if not current_state:
                self.log_warning(f"导航失败: 无法识别当前状态 (尝试 {attempt+1}/{max_attempts})")
                device_controller.wait(2)
                continue
                
            # 如果已经在目标状态，直接返回成功
            if current_state == target_state:
                return True
                
            # 查找路径
            path = self.find_path(current_state, target_state)
            if not path:
                self.log_warning(f"导航失败: 找不到从 {current_state} 到 {target_state} 的路径")
                return False
                
            # 执行路径中的每个动作
            self.log_info(f"开始导航: {current_state} -> {target_state}")
            
            for action in path:
                function_name = action['function_name']
                params = action['params']
                
                self.log_info(f"执行动作: {action['name']}")
                
                # 调用设备控制器的方法
                if hasattr(device_controller, function_name):
                    method = getattr(device_controller, function_name)
                    try:
                        method(**params)
                        device_controller.wait(2)  # 等待动作响应
                    except Exception as e:
                        self.log_error(f"执行动作失败: {str(e)}")
                        break
                else:
                    self.log_error(f"未知函数: {function_name}")
                    break
                    
                # 验证是否达到预期状态
                new_state = self.recognize_current_scene()
                if new_state != action['to_state']:
                    self.log_warning(f"动作未达到预期状态: 期望 {action['to_state']}, 实际 {new_state or '未知'}")
                    break
            
            # 最终检查是否达到目标状态
            if self.recognize_current_scene() == target_state:
                self.log_info(f"成功导航到状态: {target_state}")
                return True
        
        self.log_error(f"导航失败: 多次尝试后仍未到达目标状态 {target_state}")
        return False

        # 在StateManager类中添加以下方法
    def load_states_from_task(self, task_name, app_id):
        """从任务加载状态配置
        Args:
            task_name: 任务名称
            app_id: 应用ID
        Returns:
            是否成功
        """
        try:
            # 构建任务数据库路径
            db_path = f"tasks/{task_name}/db/{task_name}.db"
            if not os.path.exists(db_path):
                self.log_warning(f"任务数据库不存在: {db_path}")
                return False
                
            # 连接任务数据库
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # 加载状态配置
            cursor = conn.execute("SELECT state_id, type, name, config FROM states")
            states = cursor.fetchall()
            
            # 注册状态
            for state in states:
                config = json.loads(state['config'])
                self.register_state(
                    state['state_id'],
                    app_id,
                    {
                        "type": state['type'],
                        "name": state['name'],
                        "config": config
                    }
                )
                
            # 加载状态转换
            cursor = conn.execute(
                "SELECT from_state, to_state, action, function_name, params FROM state_transitions"
            )
            transitions = cursor.fetchall()
            
            # 注册状态转换
            for transition in transitions:
                params = json.loads(transition['params'])
                self.register_state_transition(
                    transition['from_state'],
                    transition['to_state'],
                    transition['action'],
                    transition['function_name'],
                    params
                )
                
            conn.close()
            return True
            
        except Exception as e:
            self.log_error(f"加载任务状态失败: {str(e)}")
            return False
    
    def _monitor_loop(self):
        """状态监控循环"""
        while self.monitoring:
            try:
                # 识别当前状态
                new_state = self.recognize_current_scene()
                
                # 状态变化检测
                if new_state != self.current_state:
                    old_state = self.current_state
                    self.current_state = new_state
                    
                    self.log_info(f"状态变化: {old_state or '未知'} -> {new_state or '未知'}")
                    
                    # 调用状态回调
                    if new_state and new_state in self.state_callbacks and self.state_callbacks[new_state]:
                        try:
                            self.state_callbacks[new_state](new_state, old_state)
                        except Exception as e:
                            self.log_error(f"状态回调执行失败: {str(e)}")
                
            except Exception as e:
                self.log_error(f"状态监控循环出错: {str(e)}")
                
            # 等待下一次检查
            time.sleep(self.monitor_interval)

# 确保导入json
import json
