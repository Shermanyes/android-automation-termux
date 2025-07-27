"""
独立的运行脚本，不依赖于包导入
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

# 将项目路径添加到系统路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入所需的依赖模块
# 这里假设您的组件模块已经存在
try:
    from components.device_controller import AndroidDeviceController
    from components.screen_recognizer import ScreenRecognizer  
    from components.state_manager import StateManager
    from data.database_manager import DatabaseManager
except ImportError as e:
    print(f"无法导入必要的组件：{e}")
    print("请确保项目结构正确，并且所有必要的模块都存在")
    sys.exit(1)

# 直接实现一个简单的调试窗口类，不依赖于debug包
class SimpleDebugWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("简易调试窗口")
        self.root.geometry("400x300")
        
        ttk.Label(self.root, text="这是一个简化版的调试窗口").pack(pady=20)
        ttk.Button(self.root, text="退出", command=self.root.destroy).pack()
    
    def run(self):
        self.root.mainloop()

def main():
    print("启动简易调试窗口...")
    
    try:
        # 初始化数据库
        db_path = "automation.db"
        db_manager = DatabaseManager(db_path=db_path)
        print(f"数据库已连接: {db_path}")
        
        # 初始化设备控制器
        device = AndroidDeviceController(instance_index=0)
        print(f"设备控制器已创建")
        
        # 初始化屏幕识别器
        recognizer = ScreenRecognizer(device)
        print("屏幕识别器已创建")
        
        # 初始化状态管理器
        state_manager = StateManager(db_manager, recognizer)
        print("状态管理器已创建")
        
        # 启动简易调试窗口
        window = SimpleDebugWindow()
        window.run()
        
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
