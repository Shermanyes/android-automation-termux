import os
import time
import sys

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tasks.three_kingdoms.task_base import GameTask

class YuanbaoTreeTask(GameTask):
    """元宝树任务"""
    
    def __init__(self, task_id, name, app_id, parent_id=None):
        super().__init__(task_id, name, app_id, parent_id, "three_kingdoms")
        
    def execute(self):
        """执行元宝树任务"""
        self.log("开始执行元宝树任务")
        
        # 确保在主页
        if not self.navigate_to_state("main_page"):
            self.log_error("无法导航到主页")
            return False
            
        # 先进入任务界面
        if not self.navigate_to_state("task_page"):
            self.log_error("无法导航到任务界面")
            return False
            
        # 进入元宝树
        if not self.navigate_to_state("yuanbao_tree"):
            self.log_error("无法导航到元宝树")
            return False
            
        # 检查是否需要浇水
        current_state = self.state_manager.recognize_current_state()
        if current_state == "yuanbao_tree_water":
            # 需要浇水
            self.log("元宝树需要浇水")
            self.tap_coordinate("元宝树", "浇水")
            self.wait(3)
            
        # 摘元宝（如果有的话）
        max_attempts = 5
        for i in range(max_attempts):
            current_state = self.state_manager.recognize_current_state()
            
            if current_state == "yuanbao_tree_collect":
                # 有元宝可以摘
                self.log("摘取元宝")
                self.tap_coordinate("元宝树", "摘元宝")
                self.wait(2)
                continue
                
            elif current_state == "yuanbao_tree_completed" or current_state == "yuanbao_tree":
                # 元宝已经全部摘取
                self.log("元宝树已完成")
                break
                
            else:
                # 未知状态，可能是界面刚刚更新
                self.wait(1)
                
            # 超过最大尝试次数
            if i == max_attempts - 1:
                self.log_warning("无法完成元宝树任务，尝试次数过多")
        
        # 返回主页
        if not self.navigate_to_state("main_page"):
            self.log_error("无法返回主页")
            # 但不影响任务结果
            
        self.log("元宝树任务完成")
        return True
