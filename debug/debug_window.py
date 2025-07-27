"""
主调试窗口
整合屏幕、识别和状态调试面板
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import time

from .screen_panel import ScreenPanel
from .recognition_panel import RecognitionPanel
from .state_panel import StatePanel
from .utils import setup_logger

class DebugWindow:
    """屏幕识别和状态识别调试窗口"""
    
    def __init__(self, device_controller=None, screen_recognizer=None, state_manager=None):
        """初始化调试窗口
        
        Args:
            device_controller: 设备控制器实例
            screen_recognizer: 屏幕识别器实例
            state_manager: 状态管理器实例
        """
        self.device = device_controller
        self.recognizer = screen_recognizer
        self.state_manager = state_manager
        
        # 创建调试目录
        os.makedirs("debug_data", exist_ok=True)
        
        # 初始化日志
        self.logger = setup_logger("debug_window", "debug_data/debug.log")
        
        # 创建窗口
        self.root = tk.Tk()
        self.root.title("屏幕识别和状态识别调试工具")
        self.root.geometry("1280x800")
        
        # 设置样式
        self.style = ttk.Style()
        self.style.configure("TNotebook", tabposition='n')
        
        # 创建UI
        self._setup_ui()
        
        # 状态标志
        self.running = False
        self.monitor_thread = None
    
    def _setup_ui(self):
        """设置UI组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # 设备状态标签
        ttk.Label(toolbar, text="设备状态:").pack(side=tk.LEFT, padx=(0, 5))
        self.device_status_label = ttk.Label(toolbar, text="未连接", foreground="red")
        self.device_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 设备控制按钮
        ttk.Button(toolbar, text="连接设备", command=self.connect_device).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="断开设备", command=self.disconnect_device).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # 状态监控开关
        self.monitor_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="状态监控", variable=self.monitor_var, 
                        command=self.toggle_monitoring).pack(side=tk.LEFT, padx=5)
        
        # 主内容区 - 选项卡
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 创建选项卡页面
        self.screen_panel = ScreenPanel(self.notebook, self.device)
        self.notebook.add(self.screen_panel, text="屏幕")
        
        self.recognition_panel = RecognitionPanel(self.notebook, self.recognizer, self.screen_panel)
        self.notebook.add(self.recognition_panel, text="识别")
        
        self.state_panel = StatePanel(self.notebook, self.state_manager, self.recognizer, 
                                      self.screen_panel, self.device)
        self.notebook.add(self.state_panel, text="状态")
        
        # 底部日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志")
        log_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 日志滚动条
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 日志文本区域
        self.log_text = tk.Text(log_frame, height=8, yscrollcommand=log_scroll.set)
        self.log_text.pack(fill=tk.X, expand=True, padx=5, pady=5)
        
        log_scroll.config(command=self.log_text.yview)
        
        # 自定义日志处理器，将日志输出到文本框
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record)
                
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.configure(state='disabled')
                    self.text_widget.see(tk.END)
                    
                # 主线程中执行UI更新
                self.text_widget.after(0, append)
        
        # 添加文本处理器到logger
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(text_handler)
        
        # 底部状态栏
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(status_bar, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 更新设备状态
        self.update_device_status()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def run(self):
        """运行调试窗口"""
        self.logger.info("调试窗口已启动")
        self.root.mainloop()
    
    def connect_device(self):
        """连接设备"""
        if self.device is None:
            messagebox.showerror("错误", "设备控制器未初始化")
            return
            
        try:
            # 初始化设备
            if not self.device.is_initialized:
                self.device.initialize()
                
            self.update_device_status()
            self.logger.info("设备已连接")
            
        except Exception as e:
            self.logger.error(f"连接设备失败: {str(e)}")
            messagebox.showerror("错误", f"连接设备失败: {str(e)}")
    
    def disconnect_device(self):
        """断开设备连接"""
        if self.device is None:
            return
            
        try:
            # 停止监控
            if self.monitor_var.get():
                self.monitor_var.set(False)
                self.toggle_monitoring()
            
            # 关闭设备
            if self.device.is_initialized:
                self.device.shutdown()
                
            self.update_device_status()
            self.logger.info("设备已断开")
            
        except Exception as e:
            self.logger.error(f"断开设备失败: {str(e)}")
            messagebox.showerror("错误", f"断开设备失败: {str(e)}")
    
    def update_device_status(self):
        """更新设备状态显示"""
        if self.device is None:
            self.device_status_label.config(text="未初始化", foreground="red")
        elif self.device.is_initialized:
            self.device_status_label.config(text="已连接", foreground="green")
        else:
            self.device_status_label.config(text="未连接", foreground="red")
    
    def toggle_monitoring(self):
        """切换状态监控"""
        if self.state_manager is None:
            messagebox.showerror("错误", "状态管理器未初始化")
            self.monitor_var.set(False)
            return
            
        if self.monitor_var.get():
            # 启动监控
            self.start_monitoring()
        else:
            # 停止监控
            self.stop_monitoring()
    
    def start_monitoring(self):
        """启动状态监控"""
        if self.running:
            return
            
        try:
            # 确保设备已连接
            if not self.device.is_initialized:
                messagebox.showinfo("提示", "请先连接设备")
                self.monitor_var.set(False)
                return
                
            # 启动状态管理器的监控
            self.state_manager.start_monitoring()
            
            # 启动本地监控线程
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitoring_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.logger.info("状态监控已启动")
            self.status_label.config(text="监控中...")
            
        except Exception as e:
            self.logger.error(f"启动监控失败: {str(e)}")
            messagebox.showerror("错误", f"启动监控失败: {str(e)}")
            self.monitor_var.set(False)
    
    def stop_monitoring(self):
        """停止状态监控"""
        if not self.running:
            return
            
        try:
            # 停止状态管理器的监控
            if self.state_manager.is_initialized:
                self.state_manager.stop_monitoring()
                
            # 停止本地监控线程
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1)
                self.monitor_thread = None
                
            self.logger.info("状态监控已停止")
            self.status_label.config(text="就绪")
            
        except Exception as e:
            self.logger.error(f"停止监控失败: {str(e)}")
            messagebox.showerror("错误", f"停止监控失败: {str(e)}")
    
    def monitoring_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 获取当前状态
                current_state = self.state_manager.get_current_state()
                
                # 在界面上更新状态
                if current_state:
                    self.root.after(0, lambda: self.status_label.config(
                        text=f"当前状态: {current_state}"
                    ))
                    
                    # 如果在状态面板，自动选中当前状态
                    if self.notebook.index(self.notebook.select()) == 2:  # 状态面板索引
                        self.root.after(0, lambda s=current_state: self.state_panel.select_state_in_list(s))
                
            except Exception as e:
                self.logger.error(f"监控循环出错: {str(e)}")
            
            # 每2秒检查一次
            time.sleep(2)
    
    def on_close(self):
        """窗口关闭处理"""
        try:
            # 停止监控
            if self.monitor_var.get():
                self.monitor_var.set(False)
                self.stop_monitoring()
                
            # 关闭设备
            if self.device and self.device.is_initialized:
                self.device.shutdown()
                
            # 关闭状态管理器
            if self.state_manager and self.state_manager.is_initialized:
                self.state_manager.shutdown()
                
            self.logger.info("调试窗口已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭窗口出错: {str(e)}")
            
        finally:
            # 销毁窗口
            self.root.destroy()


def main():
    """主函数"""
    import argparse
    from components.device_controller import AndroidDeviceController
    from components.screen_recognizer import ScreenRecognizer
    from components.state_manager import StateManager
    from data.database_manager import DatabaseManager
    
    # 命令行参数
    parser = argparse.ArgumentParser(description="屏幕识别和状态识别调试工具")
    parser.add_argument("--device-index", type=int, default=0, help="设备索引")
    parser.add_argument("--db-path", type=str, default="automation.db", help="数据库路径")
    args = parser.parse_args()
    
    try:
        # 初始化组件
        db_manager = DatabaseManager(db_path=args.db_path)
        device = AndroidDeviceController(instance_index=args.device_index)
        recognizer = ScreenRecognizer(device)
        state_manager = StateManager(db_manager, recognizer)
        
        # 启动调试窗口
        debugger = DebugWindow(device, recognizer, state_manager)
        debugger.run()
        
    except Exception as e:
        print(f"启动调试工具失败: {str(e)}")


if __name__ == "__main__":
    main()
