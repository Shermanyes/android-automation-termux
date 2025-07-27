import os
import sys
import logging
import json
import sqlite3
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 使用相对导入
from tasks.three_kingdoms.task_base import GameTask

class ThreeKingdomsTask(GameTask):
    """三国杀主任务"""
    
    def __init__(self, task_id, name, app_id, parent_id=None):
        super().__init__(task_id, name, app_id, parent_id, "three_kingdoms")
        self.sub_tasks = []
        self.package_name = "com.bf.sgs.hdexp.bd"
        
    def initialize(self):
        """初始化任务"""
        self.log("开始初始化三国杀主任务...")
        
        # 获取系统组件
        self.device = self._get_device_controller()
        if not self.device:
            self.log_error("无法获取设备控制器")
            return False
            
        self.recognizer = self._get_screen_recognizer()
        if not self.recognizer:
            self.log_error("无法获取屏幕识别器")
            return False
        
        # 初始化自定义状态管理器
        db_manager = self._get_database_manager()
        self.state_manager = ThreeKingdomsStateManager(db_manager, self.recognizer)
        if not self.state_manager.initialize():
            self.log_error("状态管理器初始化失败")
            return False
            
        # 加载坐标配置
        if not self._load_coordinates():
            self.log_error("加载坐标失败")
            return False
            
        # 初始化子任务
        self._init_sub_tasks()
        
        self.log("三国杀主任务初始化完成")
        return True
        
    def execute(self):
        """执行主任务"""
        self.log("开始执行三国杀日常任务")
        
        # 启动应用
        if not self._start_app():
            self.log_error("启动应用失败")
            return False
            
        # 执行登录
        if not self._perform_login():
            self.log_error("登录失败，任务终止")
            return False
            
        # 执行子任务
        success = self._execute_sub_tasks()
        
        # 关闭应用
        self._close_app()
        
        self.log(f"三国杀日常任务{'完成' if success else '失败'}")
        return success
        
    def _init_sub_tasks(self):
        """初始化子任务列表"""
        # 导入子任务
        from sub_tasks.signin_task import SignInTask
        from sub_tasks.yuanbao_tree_task import YuanbaoTreeTask
        from sub_tasks.campaign_task import CampaignTask
        from sub_tasks.battle_task import BattleTask
        
        # 按优先级添加子任务
        self.sub_tasks = [
            SignInTask(f"{self.task_id}_signin", "每日签到", self.app_id, self.task_id),
            YuanbaoTreeTask(f"{self.task_id}_yuanbao", "元宝树", self.app_id, self.task_id),
            CampaignTask(f"{self.task_id}_campaign", "征战天下", self.app_id, self.task_id),
            BattleTask(f"{self.task_id}_battle", "军争演练", self.app_id, self.task_id)
        ]
        
        self.log(f"已初始化 {len(self.sub_tasks)} 个子任务")
        
    def _execute_sub_tasks(self):
        """执行所有子任务"""
        results = []
        
        for task in self.sub_tasks:
            try:
                self.log(f"开始执行子任务: {task.name}")
                
                # 初始化子任务
                if not task.initialize():
                    self.log_error(f"子任务 {task.name} 初始化失败")
                    results.append(False)
                    continue
                
                # 执行子任务
                result = task.execute()
                results.append(result)
                
                self.log(f"子任务 [{task.name}] {'完成' if result else '失败'}")
                
                # 如果子任务失败但不是关键任务，继续执行下一个
                if not result and task.name in ["每日签到", "元宝树"]:
                    continue
                    
                # 如果关键任务失败，终止执行
                if not result and task.name in ["征战天下", "军争演练"]:
                    self.log_error(f"关键子任务 [{task.name}] 失败，终止执行")
                    return False
                    
            except Exception as e:
                self.log_error(f"子任务 [{task.name}] 执行异常: {str(e)}")
                results.append(False)
                
        # 至少完成一个主要任务就算成功
        return any(results)
        
    def _start_app(self):
        """启动三国杀应用"""
        try:
            self.log(f"启动应用: {self.package_name}")
            result = self.device.start_app(self.package_name)
            
            # 等待应用启动
            self.wait(5)
            
            return result
            
        except Exception as e:
            self.log_error(f"启动应用失败: {str(e)}")
            return False
        
    def _close_app(self):
        """关闭三国杀应用"""
        try:
            self.log(f"关闭应用: {self.package_name}")
            result = self.device.stop_app(self.package_name)
            
            # 等待应用关闭
            self.wait(2)
            
            return result
            
        except Exception as e:
            self.log_error(f"关闭应用失败: {str(e)}")
            return False
        
    def _perform_login(self):
        """执行登录流程"""
        try:
            # 最多尝试3次登录
            for attempt in range(3):
                # 识别当前状态
                current_state = self.state_manager.recognize_current_state()
                
                # 如果已经在主页，直接返回成功
                if current_state == "main_page":
                    self.log("已在游戏主页，无需登录")
                    return True
                    
                # 处理登录过程中的各种状态
                if current_state == "login":
                    # 点击登录按钮
                    self.tap_coordinate("登录", "登录按钮")
                    self.wait(5)
                    
                elif current_state == "login_announcement":
                    # 关闭公告
                    self.tap_coordinate("登录", "关闭公告")
                    self.wait(2)
                    
                elif current_state == "login_kicked":
                    # 重新登录
                    self.tap_coordinate("登录", "重新登录")
                    self.wait(5)
                    
                elif current_state == "loading":
                    # 等待加载完成
                    self.log("正在加载游戏...")
                    self.wait(5)
                    
                elif current_state == "main_page_ad":
                    # 关闭广告
                    self.tap_coordinate("主页", "返回")
                    self.wait(2)
                    
                elif current_state == "main_page":
                    # 登录成功
                    self.log("登录成功，已进入游戏主页")
                    return True
                    
                else:
                    # 未知状态，可能是广告或其他弹窗
                    self.log(f"登录过程中遇到未知状态: {current_state}")
                    
                    # 尝试点击返回按钮
                    self.device.tap(671, 1242)  # 大多数情况下的返回按钮位置
                    self.wait(2)
                
                # 最大等待时间
                if attempt == 2:
                    # 最后一次尝试，强制重启应用
                    self.log("登录失败，尝试重启应用")
                    self._close_app()
                    self.wait(2)
                    self._start_app()
                    self.wait(5)
            
            # 多次尝试后仍未登录成功
            current_state = self.state_manager.recognize_current_state()
            return current_state == "main_page"
            
        except Exception as e:
            self.log_error(f"登录过程出错: {str(e)}")
            return False

class ThreeKingdomsStateManager:
    """三国杀游戏状态管理器"""
    
    def __init__(self, db_manager=None, screen_recognizer=None, db_path="db/three_kingdoms.db"):
        
        self.db_manager = db_manager
        self.recognizer = screen_recognizer
        self.db_path = db_path
        self.states = {}
        self.actions = {}
        self.current_state = None
        self.recognition_interval = 1  # 默认屏幕识别间隔(秒)
        self.battle_recognition_interval = 0.3  # 战斗中屏幕识别间隔(秒)
        self._logger = logging.getLogger("three_kingdoms.state_manager")
        
    def initialize(self) -> bool:
        """初始化状态管理器"""
        self.log_info("初始化状态管理器...")
        
        # 从数据库加载状态和动作
        if not self._load_states():
            self.log_error("加载状态失败")
            return False
            
        if not self._load_actions():
            self.log_error("加载动作失败")
            return False
            
        # 加载设置
        self._load_settings()
        
        self.log_info("状态管理器初始化完成")
        return True
        
    def recognize_current_state(self, app_id: str = "three_kingdoms") -> Optional[str]:
        """识别当前游戏状态"""
        try:
            # 获取所有状态配置
            states = []
            for state_id, state in self.states.items():
                if state.get('app_id') == app_id:
                    states.append((state_id, state))
            
            # 按照状态名称对状态进行排序（子状态排在前面，如battle_fighting在battle前面）
            states.sort(key=lambda x: len(x[0]), reverse=True)
            
            # 记录识别到的状态和相似度
            recognized_states = []
            
            for state_id, state in states:
                # 基于状态类型执行不同的识别逻辑
                recognition_type = state.get('type', 'screen')
                config = state.get('config', {})
                
                if recognition_type == 'screen':
                    # 屏幕状态识别
                    recognition_area = config.get('recognition_area')
                    recognition_text = config.get('recognition_text')
                    threshold = config.get('threshold', 0.8)
                    
                    # 如果有多个识别区域和文本，需要全部匹配
                    if isinstance(recognition_area, list) and isinstance(recognition_text, list):
                        match_all = True
                        for i, area in enumerate(recognition_area):
                            text = recognition_text[i] if i < len(recognition_text) else recognition_text[0]
                            match = self._recognize_text_in_area(area, text, threshold)
                            if not match:
                                match_all = False
                                break
                        
                        if match_all:
                            recognized_states.append((state_id, 1.0))
                            
                    else:
                        # 单一区域和文本识别
                        match = self._recognize_text_in_area(recognition_area, recognition_text, threshold)
                        if match:
                            recognized_states.append((state_id, match[1] if isinstance(match, tuple) else 1.0))
                            
                elif recognition_type == 'image':
                    # 图像状态识别
                    template_path = config.get('template_path')
                    threshold = config.get('threshold', 0.8)
                    roi = config.get('roi')
                    
                    result = self.recognizer.find_image(template_path, threshold, roi)
                    if result:
                        recognized_states.append((state_id, 1.0))
                        
                elif recognition_type == 'color':
                    # 颜色状态识别
                    # 这部分需要实现颜色识别逻辑
                    pass
            
            # 如果识别到多个状态，取相似度最高的
            if recognized_states:
                recognized_states.sort(key=lambda x: x[1], reverse=True)
                best_state = recognized_states[0][0]
                self.current_state = best_state
                return best_state
                
            self.current_state = None
            return None
            
        except Exception as e:
            self.log_error(f"识别状态出错: {str(e)}")
            return None
    
    def _recognize_text_in_area(self, area, target_text, threshold):
        """在指定区域识别文本"""
        if not area or not target_text:
            return False
            
        # 解析区域参数
        x = area.get('x', 0)
        y = area.get('y', 0)
        width = area.get('width', 100)
        height = area.get('height', 100)
        
        # 构建ROI
        roi = (x, y, x + width, y + height)
        
        # 调用recognizer的find_text方法
        result = self.recognizer.find_text(target_text, roi=roi, threshold=threshold)
        return result
        
    def navigate_to_state(self, target_state: str, device_controller, max_attempts: int = 3) -> bool:
        """导航到指定状态
        
        Args:
            target_state: 目标状态ID
            device_controller: 设备控制器实例
            max_attempts: 最大尝试次数
            
        Returns:
            是否成功导航到目标状态
        """
        if not self.recognizer or not device_controller:
            self.log_error("屏幕识别器或设备控制器未初始化")
            return False
            
        for attempt in range(max_attempts):
            # 识别当前状态
            current_state = self.recognize_current_state()
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
                
                # 执行动作
                if function_name == 'click':
                    x = params.get('x', 0)
                    y = params.get('y', 0)
                    device_controller.tap(x, y)
                    
                elif function_name == 'swipe':
                    x1 = params.get('x1', 0)
                    y1 = params.get('y1', 0)
                    x2 = params.get('x2', 0)
                    y2 = params.get('y2', 0)
                    duration = params.get('duration', 300)
                    device_controller.swipe(x1, y1, x2, y2, duration)
                    
                elif function_name == 'wait':
                    seconds = params.get('seconds', 1)
                    device_controller.wait(seconds)
                    
                elif function_name == 'back':
                    device_controller.back()
                    
                elif function_name == 'auto_play':
                    self._handle_auto_play(device_controller, params)
                    
                elif function_name == 'battle_menu':
                    self._handle_battle_menu(device_controller, params)
                    
                else:
                    self.log_error(f"未知动作: {function_name}")
                    continue
                    
                # 等待动作响应
                device_controller.wait(2)
                    
                # 验证是否达到预期状态
                new_state = self.recognize_current_state()
                if new_state != action['to_state']:
                    self.log_warning(f"动作未达到预期状态: 期望 {action['to_state']}, 实际 {new_state or '未知'}")
                    break
            
            # 最终检查是否达到目标状态
            if self.recognize_current_state() == target_state:
                self.log_info(f"成功导航到状态: {target_state}")
                return True
        
        self.log_error(f"导航失败: 多次尝试后仍未到达目标状态 {target_state}")
        return False
        
    def _handle_auto_play(self, device_controller, params):
        """处理托管逻辑"""
        try:
            # 点击菜单
            device_controller.tap(674, 1245)
            device_controller.wait(1)
            
            # 点击托管
            device_controller.tap(655, 1138)
            
            self.log_info("已开启托管")
            
        except Exception as e:
            self.log_error(f"托管操作失败: {str(e)}")
            
    def _handle_battle_menu(self, device_controller, params):
        """处理战斗菜单逻辑"""
        try:
            is_dead = params.get('dead', False)
            
            # 点击菜单
            device_controller.tap(674, 1245)
            device_controller.wait(1)
            
            if is_dead:
                # 已死亡，点击退出
                device_controller.tap(649, 792)
            else:
                # 未死亡，点击退出
                device_controller.tap(663, 620)
                
            self.log_info(f"已点击{'死亡' if is_dead else '未死亡'}退出菜单")
            
        except Exception as e:
            self.log_error(f"战斗菜单操作失败: {str(e)}")
            
    def find_path(self, current_state: str, target_state: str) -> List[Dict]:
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
            queue = deque([(current_state, [])])
            
            while queue:
                state, path = queue.popleft()
                
                if state == target_state:
                    return path
                
                if state in visited:
                    continue
                    
                visited.add(state)
                
                # 获取所有可能的转换
                for action_id, action in self.actions.items():
                    if action['from_state'] == state:
                        next_state = action['to_state']
                        if next_state not in visited:
                            # 构建动作信息
                            action_info = {
                                'from_state': state,
                                'to_state': next_state,
                                'name': action['name'],
                                'function_name': action['function_name'],
                                'params': action['params']
                            }
                            
                            queue.append((next_state, path + [action_info]))
            
            self.log_warning(f"找不到从 {current_state} 到 {target_state} 的路径")
            return []
            
        except Exception as e:
            self.log_error(f"查找路径失败: {str(e)}")
            return []
            
    def _load_states(self) -> bool:
        """从数据库加载状态配置"""
        try:
            if not os.path.exists(self.db_path):
                self.log_error(f"数据库不存在: {self.db_path}")
                return False
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM recognition_states")
            rows = cursor.fetchall()
            
            for row in rows:
                state_id = row['state_id']
                config = json.loads(row['config']) if row['config'] else {}
                
                self.states[state_id] = {
                    'app_id': row['app_id'],
                    'name': row['name'],
                    'type': row['type'],
                    'config': config
                }
                
            conn.close()
            self.log_info(f"已加载 {len(rows)} 个状态配置")
            return True
            
        except Exception as e:
            self.log_error(f"加载状态失败: {str(e)}")
            return False
            
    def _load_actions(self) -> bool:
        """从数据库加载状态转换动作"""
        try:
            if not os.path.exists(self.db_path):
                self.log_error(f"数据库不存在: {self.db_path}")
                return False
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM actions")
            rows = cursor.fetchall()
            
            for row in rows:
                action_id = row['action_id']
                params = json.loads(row['params']) if row['params'] else {}
                
                self.actions[action_id] = {
                    'from_state': row['from_state'],
                    'to_state': row['to_state'],
                    'name': row['name'],
                    'function_name': row['function_name'],
                    'params': params
                }
                
            conn.close()
            self.log_info(f"已加载 {len(rows)} 个动作配置")
            return True
            
        except Exception as e:
            self.log_error(f"加载动作失败: {str(e)}")
            return False
            
    def _load_settings(self) -> bool:
        """加载系统设置"""
        try:
            if not os.path.exists(self.db_path):
                return False
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 加载屏幕识别间隔设置
            cursor.execute("SELECT value FROM settings WHERE key = 'screen_recognition_interval'")
            row = cursor.fetchone()
            if row:
                self.recognition_interval = float(row['value'])
                
            # 加载战斗识别间隔设置
            cursor.execute("SELECT value FROM settings WHERE key = 'battle_recognition_interval'")
            row = cursor.fetchone()
            if row:
                self.battle_recognition_interval = float(row['value'])
                
            conn.close()
            return True
            
        except Exception as e:
            self.log_error(f"加载设置失败: {str(e)}")
            return False
            
    def log_info(self, message: str):
        """记录信息日志"""
        self._logger.info(message)
        
    def log_warning(self, message: str):
        """记录警告日志"""
        self._logger.warning(message)
        
    def log_error(self, message: str):
        """记录错误日志"""
        self._logger.error(message)
