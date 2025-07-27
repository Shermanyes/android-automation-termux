# tasks/three_kingdoms/test_run.py
import os
import sys

# 添加主项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# 将
from helpers.state_manager import ThreeKingdomsStateManager
# 改为
from tasks.three_kingdoms.helpers.state_manager import ThreeKingdomsStateManager
# 或者
from .helpers.state_manager import ThreeKingdomsStateManager

def test_initialization():
    task = ThreeKingdomsTask("test_task", "测试任务", "three_kingdoms")
    if task.initialize():
        print("初始化成功")
        print(f"加载了 {len(task.coordinates)} 个屏幕配置")
        print(f"状态管理器加载了 {len(task.state_manager.states)} 个状态")
        print(f"状态管理器加载了 {len(task.state_manager.actions)} 个动作")
        return True
    return False

if __name__ == "__main__":
    test_initialization()
