import os
import time
import json
import sys
import sqlite3

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tasks.three_kingdoms.task_base import GameTask

class BattleTask(GameTask):
    """军争演练任务"""
    
    def __init__(self, task_id, name, app_id, parent_id=None):
        super().__init__(task_id, name, app_id, parent_id, "three_kingdoms")
        self.battle_count = 5  # 默认对战次数
        self.battle_type = "military"  # 默认战斗类型：军争模式
        self.total_battles = 0  # 已完成对战次数
        
    def initialize(self):
        """初始化任务"""
        super().initialize()
        
        # 获取任务配置
        task_config = self._get_task_config()
        if task_config:
            if "battle_count" in task_config:
                self.battle_count = task_config["battle_count"]
            if "battle_type" in task_config:
                self.battle_type = task_config["battle_type"]
                
        return True
        
    def execute(self):
        """执行军争演练任务"""
        self.log(f"开始执行军争演练任务 (目标: {self.battle_count}次, 类型: {self.battle_type})")
        
        # 导航到主页
        if not self.navigate_to_state("main_page"):
            self.log_error("无法导航到主页")
            return False
            
        # 进入经典场
        if not self.navigate_to_state("classic_mode"):
            self.log_error("无法导航到经典场")
            return False
            
        # 根据战斗类型选择模式
        if self.battle_type == "military":
            # 选择军争模式
            self.tap_coordinate("经典场", "军争模式")
            mode_name = "军争模式"
        else:
            # 默认选择标准模式
            self.tap_coordinate("经典场", "标准模式")
            mode_name = "标准模式"
            
        self.wait(2)
            
        # 执行多次对战
        self.total_battles = 0
        
        while self.total_battles < self.battle_count:
            self.log(f"准备第 {self.total_battles + 1}/{self.battle_count} 场对战")
            
            # 开始匹配
            if not self._start_match():
                self.log_error("开始匹配失败")
                break
                
            # 等待匹配完成
            if not self._wait_for_match():
                self.log_error("等待匹配超时")
                break
                
            # 选择武将
            if not self._select_general():
                self.log_error("选择武将失败")
                break
                
            # 执行战斗
            battle_result = self._battle()
            
            # 处理战斗结果
            if battle_result:
                self.total_battles += 1
                self.log(f"成功完成第 {self.total_battles}/{self.battle_count} 场对战")
            else:
                self.log_error("战斗失败")
            
            # 检查是否继续
            if not self._continue_battle():
                self.log_warning("无法继续对战")
                break
        
        # 返回主页
        if not self.navigate_to_state("main_page"):
            self.log_error("无法返回主页")
            # 但不影响任务结果
            
        self.log(f"军争演练任务完成，共完成 {self.total_battles}/{self.battle_count} 场对战")
        return self.total_battles >= 1  # 至少完成一场视为成功
        
    def _start_match(self):
        """开始匹配"""
        try:
            # 检查当前状态
            current_state = self.state_manager.recognize_current_state()
            
            if current_state != "classic_mode":
                self.log_warning(f"当前状态不是经典场: {current_state}")
                return False
                
            # 点击开始匹配
            self.tap_coordinate("经典场", "开始匹配")
            self.wait(2)
            
            # 验证是否进入匹配状态
            current_state = self.state_manager.recognize_current_state()
            return current_state == "battle_matching"
            
        except Exception as e:
            self.log_error(f"开始匹配失败: {str(e)}")
            return False
        
    def _wait_for_match(self, timeout=60):
        """等待匹配完成"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # 检查当前状态
                current_state = self.state_manager.recognize_current_state()
                
                if current_state == "select_general":
                    # 匹配成功，进入选将界面
                    self.log("匹配成功，进入选将界面")
                    return True
                    
                elif current_state != "battle_matching":
                    # 意外状态
                    self.log_warning(f"匹配过程中出现意外状态: {current_state}")
                    return False
                
                # 等待一段时间再检查
                self.wait(2)
            
            # 超时
            self.log_warning("匹配超时")
            return False
            
        except Exception as e:
            self.log_error(f"等待匹配失败: {str(e)}")
            return False
        
    def _select_general(self, timeout=30):
        """选择武将"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # 检查当前状态
                current_state = self.state_manager.recognize_current_state()
                
                if current_state == "select_general_2":
                    # 二选一
                    self.tap_coordinate("选将", "二将选择")
                    self.wait(1)
                    
                elif current_state == "select_general_3":
                    # 三选一
                    self.tap_coordinate("选将", "三将选择")
                    self.wait(1)
                    
                elif current_state == "select_general_4":
                    # 四选一
                    self.tap_coordinate("选将", "四将选择")
                    self.wait(1)
                    
                elif current_state == "select_general_intro":
                    # 确认选择
                    self.device.tap(400, 600)  # 屏幕中央，确认选择
                    self.wait(1)
                    
                elif current_state == "select_general_waiting":
                    # 等待其他玩家选择
                    self.wait(2)
                    
                elif current_state == "battle_fighting":
                    # 选将完成，进入战斗
                    self.log("选将完成，进入战斗")
                    return True
                    
                else:
                    # 其他状态，等待
                    self.wait(1)
            
            # 超时
            self.log_warning("选将超时")
            return False
            
        except Exception as e:
            self.log_error(f"选择武将失败: {str(e)}")
            return False
        
    def _battle(self, max_duration=1200):
        """执行战斗"""
        try:
            start_time = time.time()
            auto_play_enabled = False
            
            # 调整识别间隔为战斗模式
            original_interval = self.state_manager.recognition_interval
            self.state_manager.recognition_interval = self.state_manager.battle_recognition_interval
            
            try:
                while time.time() - start_time < max_duration:
                    # 检查当前状态
                    current_state = self.state_manager.recognize_current_state()
                    
                    if current_state in ["battle_wugufeijian", "battle_play_response", 
                                         "battle_play_phase", "battle_simayi", "battle_zhugeliang"]:
                        # 需要操作的状态，开启托管
                        if not auto_play_enabled:
                            self.log(f"检测到需要操作的状态: {current_state}，开启托管")
                            self.state_manager._handle_auto_play(self.device, {})
                            auto_play_enabled = True
                            self.wait(1)
                            
                    elif current_state == "battle_auto_playing":
                        # 已经在托管中
                        auto_play_enabled = True
                        self.wait(1)
                        
                    elif current_state == "battle_dead":
                        # 已死亡，退出战斗
                        self.log("检测到已死亡状态，退出战斗")
                        self.state_manager._handle_battle_menu(self.device, {"dead": True})
                        self.wait(2)
                        
                        # 确认退出
                        self.device.tap(305, 772)  # 确认退出战斗
                        self.wait(2)
                        
                        # 直接返回结果
                        return True
                        
                    elif current_state == "battle_mvp":
                        # MVP界面
                        self.log("检测到MVP界面")
                        self.tap_coordinate("结算", "继续")
                        self.wait(2)
                        
                    elif current_state == "battle_result":
                        # 结算界面
                        self.log("检测到结算界面")
                        self.tap_coordinate("结算", "退出")
                        self.wait(2)
                        return True
                        
                    elif current_state == "battle_reconnect_fail" or current_state == "battle_reconnecting":
                        # 重连失败或重连中
                        self.log(f"检测到重连状态: {current_state}")
                        if current_state == "battle_reconnect_fail":
                            # 重连失败，返回登录
                            self.device.tap(320, 552)  # 重新登录
                            return False
                        else:
                            # 等待重连
                            self.wait(5)
                            
                    elif current_state == "classic_mode":
                        # 已经返回经典场，战斗结束
                        self.log("已返回经典场，战斗结束")
                        return True
                        
                    elif current_state not in ["battle_fighting", None]:
                        # 其他意外状态
                        self.log_warning(f"战斗中出现意外状态: {current_state}")
                        
                        # 尝试点击返回
                        self.device.tap(671, 1242)  # 返回按钮
                        self.wait(2)
                    
                    # 等待一段时间再检查
                    self.wait(0.5)
                
                # 超时，强制退出战斗
                self.log_warning("战斗超时，强制退出")
                
                # 点击菜单
                self.device.tap(674, 1245)
                self.wait(1)
                
                # 点击退出
                self.device.tap(663, 620)  # 未死亡退出
                self.wait(1)
                
                # 确认退出
                self.device.tap(305, 772)
                
                return False
                
            finally:
                # 恢复原始识别间隔
                self.state_manager.recognition_interval = original_interval
                
        except Exception as e:
            self.log_error(f"战斗过程出错: {str(e)}")
            return False
        
    def _continue_battle(self):
        """检查是否可以继续对战"""
        try:
            # 等待一段时间，确保回到经典场
            self.wait(3)
            
            # 检查当前状态
            current_state = self.state_manager.recognize_current_state()
            
            if current_state == "classic_mode":
                # 已经回到经典场，可以继续
                return True
                
            elif current_state == "battle_result":
                # 还在结算界面，点击退出
                self.tap_coordinate("结算", "退出")
                self.wait(3)
                return self._continue_battle()  # 递归检查
                
            elif current_state == "main_page":
                # 回到了主页，需要重新进入经典场
                return self.navigate_to_state("classic_mode")
                
            else:
                # 其他状态，尝试返回
                self.device.tap(671, 1242)  # 返回按钮
                self.wait(2)
                return self._continue_battle()  # 递归检查
                
        except Exception as e:
            self.log_error(f"检查是否可以继续对战失败: {str(e)}")
            return False
        
    def _get_task_config(self):
        """获取任务配置"""
        try:
            if not os.path.exists(self.db_path):
                return None
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT config FROM tasks WHERE task_id = 'task_battle'")
            row = cursor.fetchone()
            
            if row and row['config']:
                config = json.loads(row['config'])
                return config
                
            return None
            
        except Exception as e:
            self.log_error(f"获取任务配置失败: {str(e)}")
            return None
