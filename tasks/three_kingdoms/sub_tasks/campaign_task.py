import os
import time
import sqlite3
import sys
import json

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tasks.three_kingdoms.task_base import GameTask

class CampaignTask(GameTask):
    """征战天下任务"""
    
    def __init__(self, task_id, name, app_id, parent_id=None):
        super().__init__(task_id, name, app_id, parent_id, "three_kingdoms")
        self.chapters = []
        self.stages = {}
        self.stamina_threshold = 40  # 体力阈值
        
    def initialize(self):
        """初始化任务"""
        super().initialize()
        
        # 加载章节和关卡配置
        self._load_campaign_config()
        
        # 获取任务配置
        task_config = self._get_task_config()
        if task_config and "stamina_threshold" in task_config:
            self.stamina_threshold = task_config["stamina_threshold"]
            
        return True
        
    def execute(self):
        """执行征战天下任务"""
        self.log("开始执行征战天下任务")
        
        # 导航到征战天下界面
        if not self.navigate_to_state("campaign"):
            self.log_error("无法导航到征战天下界面")
            return False
            
        # 检查并领取俸禄
        self._check_and_collect_salary()
        
        # 检查并完成任务
        self._check_and_complete_tasks()
        
        # 执行扫荡
        success = self._perform_sweep()
        
        # 返回主页
        if not self.navigate_to_state("main_page"):
            self.log_error("无法返回主页")
            # 但不影响任务结果
            
        self.log(f"征战天下任务{'完成' if success else '失败'}")
        return success
        
    def _load_campaign_config(self):
        """加载征战天下配置"""
        try:
            if not os.path.exists(self.db_path):
                self.log_error(f"数据库不存在: {self.db_path}")
                return False
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 加载章节
            cursor.execute("SELECT * FROM sweep_chapters ORDER BY priority")
            chapters = cursor.fetchall()
            
            for chapter in chapters:
                chapter_id = chapter['chapter_id']
                self.chapters.append({
                    'id': chapter_id,
                    'name': chapter['name'],
                    'priority': chapter['priority']
                })
                
                # 加载章节对应的关卡
                cursor.execute("SELECT * FROM sweep_stages WHERE chapter_id = ? ORDER BY priority", (chapter_id,))
                stages = cursor.fetchall()
                
                self.stages[chapter_id] = []
                for stage in stages:
                    self.stages[chapter_id].append({
                        'chapter_id': chapter_id,
                        'stage_number': stage['stage_number'],
                        'priority': stage['priority']
                    })
            
            conn.close()
            self.log(f"已加载 {len(self.chapters)} 个章节配置")
            return True
            
        except Exception as e:
            self.log_error(f"加载征战天下配置失败: {str(e)}")
            return False
        
    def _check_and_collect_salary(self):
        """检查并领取俸禄"""
        try:
            # 检查当前状态
            current_state = self.state_manager.recognize_current_state()
            
            if current_state == "campaign_salary":
                # 有俸禄可领取
                self.log("检测到俸禄可领取")
                
                # 点击领取俸禄按钮
                self.tap_coordinate("征战天下", "领取俸禄")
                self.wait(2)
                
                # 确认领取
                if self.state_manager.recognize_current_state() == "campaign_collect_salary":
                    self.tap_coordinate("征战天下俸禄", "确认")
                    self.wait(2)
                    
                self.log("已领取俸禄")
                
            return True
            
        except Exception as e:
            self.log_error(f"检查并领取俸禄失败: {str(e)}")
            return False
        
    def _check_and_complete_tasks(self):
        """检查并完成任务"""
        try:
            # 进入任务界面
            self.tap_coordinate("征战天下", "任务")
            self.wait(2)
            
            # 检查当前状态
            current_state = self.state_manager.recognize_current_state()
            if current_state != "campaign_task":
                self.log_warning("无法进入征战天下任务界面")
                return False
                
            # 领取奖励（最多尝试4次，对应4个宝箱）
            for _ in range(4):
                if self.state_manager.recognize_current_state() == "campaign_task":
                    # 点击领取按钮
                    self.tap_coordinate("征战天下任务", "领取")
                    self.wait(2)
                else:
                    break
            
            # 检查宝箱
            for box_id in ["宝箱1", "宝箱2", "宝箱3", "宝箱4"]:
                self.tap_coordinate("征战天下任务", box_id)
                self.wait(1)
            
            # 返回征战天下主界面
            self.tap_coordinate("征战天下任务", "返回")
            self.wait(2)
            
            return True
            
        except Exception as e:
            self.log_error(f"检查并完成任务失败: {str(e)}")
            return False
        
    def _perform_sweep(self):
        """执行扫荡"""
        try:
            if not self.chapters or not self.stages:
                self.log_warning("没有找到章节配置")
                return False
                
            # 遍历章节
            for chapter in self.chapters:
                chapter_id = chapter['id']
                chapter_name = chapter['name']
                
                if chapter_id not in self.stages or not self.stages[chapter_id]:
                    continue
                    
                self.log(f"开始扫荡章节: {chapter_name}")
                
                # 选择章节（TODO: 实现选择章节逻辑）
                # 由于没有具体的章节选择界面状态，这里需要根据实际情况补充
                
                # 遍历关卡
                for stage in self.stages[chapter_id]:
                    stage_number = stage['stage_number']
                    
                    self.log(f"扫荡关卡: {chapter_name} - {stage_number}")
                    
                    # 选择关卡（TODO: 实现选择关卡逻辑）
                    # 由于没有具体的关卡选择界面状态，这里需要根据实际情况补充
                    
                    # 检查当前状态
                    current_state = self.state_manager.recognize_current_state()
                    if current_state == "campaign_sweep":
                        # 点击扫荡按钮
                        self.device.tap(573, 591)  # 扫荡按钮
                        self.wait(2)
                        
                        # 确认扫荡（如果有确认界面）
                        self.device.tap(400, 700)  # 确认按钮估计位置
                        self.wait(2)
                        
                        # 关闭结算界面（如果有）
                        self.device.tap(400, 700)  # 关闭按钮估计位置
                        self.wait(2)
                    
                    # 检查体力是否不足
                    # TODO: 实现体力检查逻辑
                    # 这里需要根据实际界面添加体力检查代码
                    
                    # 简单模拟：按照设定的体力阈值，每次扫荡消耗10点体力
                    simulated_stamina = 100 - (10 * (stage_number - 1))
                    if simulated_stamina < self.stamina_threshold:
                        self.log(f"体力不足，停止扫荡（模拟值: {simulated_stamina}）")
                        break
            
            return True
            
        except Exception as e:
            self.log_error(f"执行扫荡失败: {str(e)}")
            return False
        
    def _get_task_config(self):
        """获取任务配置"""
        try:
            if not os.path.exists(self.db_path):
                return None
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT config FROM tasks WHERE task_id = 'task_campaign'")
            row = cursor.fetchone()
            
            if row and row['config']:
                config = json.loads(row['config'])
                return config
                
            return None
            
        except Exception as e:
            self.log_error(f"获取任务配置失败: {str(e)}")
            return None
