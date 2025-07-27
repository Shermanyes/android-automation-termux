"""
状态识别调试工具 - 用于检测系统状态识别功能是否正常工作
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import logging
from PIL import Image, ImageTk

# 将项目路径添加到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "state_recognition_debug.log")), logging.StreamHandler()]
)
logger = logging.getLogger('state_recognition_debug')

# 导入所需的依赖模块
try:
    from components.device_controller import AndroidDeviceController
    from components.screen_recognizer import ScreenRecognizer  
    from components.state_manager import StateManager
    from data.database_manager import DatabaseManager
except ImportError as e:
    logger.error(f"无法导入必要的组件：{e}")
    logger.error("请确保项目结构正确，并且所有必要的模块都存在")
    sys.exit(1)

class StateRecognitionDebugWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("状态识别调试工具")
        self.root.geometry("1200x800")
        
        # 初始化组件
        self.db_manager = None
        self.device = None
        self.recognizer = None
        self.state_manager = None
        
        # 组件状态标志
        self.is_initialized = False
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # 创建UI
        self.setup_ui()
        
    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding="10")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        # 设备控制
        device_frame = ttk.LabelFrame(control_frame, text="设备控制", padding="5")
        device_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(device_frame, text="雷电模拟器索引:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.instance_index_var = tk.StringVar(value="0")
        ttk.Entry(device_frame, textvariable=self.instance_index_var, width=5).grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(device_frame, text="雷电路径:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
        self.ld_path_var = tk.StringVar(value="D:\\计算机辅助\\leidian\\LDPlayer9\\ld.exe")
        ttk.Entry(device_frame, textvariable=self.ld_path_var, width=40).grid(column=1, row=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(device_frame, text="控制台路径:").grid(column=0, row=2, sticky=tk.W, padx=5, pady=2)
        self.ldconsole_path_var = tk.StringVar(value="D:\\计算机辅助\\leidian\\LDPlayer9\\ldconsole.exe")
        ttk.Entry(device_frame, textvariable=self.ldconsole_path_var, width=40).grid(column=1, row=2, sticky=tk.W, padx=5, pady=2)
        
        # 数据库控制
        db_frame = ttk.LabelFrame(control_frame, text="数据库", padding="5")
        db_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(db_frame, text="数据库路径:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.db_path_var = tk.StringVar(value="automation.db")
        ttk.Entry(db_frame, textvariable=self.db_path_var, width=30).grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        ttk.Button(db_frame, text="浏览", command=self.browse_db).grid(column=2, row=0, padx=5, pady=2)
        
        # 任务控制
        task_frame = ttk.LabelFrame(control_frame, text="任务加载", padding="5")
        task_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(task_frame, text="任务名称:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.task_name_var = tk.StringVar(value="three_kingdoms")
        ttk.Entry(task_frame, textvariable=self.task_name_var, width=20).grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(task_frame, text="应用ID:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
        self.app_id_var = tk.StringVar(value="com.game.three_kingdoms")
        ttk.Entry(task_frame, textvariable=self.app_id_var, width=30).grid(column=1, row=1, sticky=tk.W, padx=5, pady=2)
        
        # 按钮控制区
        btn_frame = ttk.Frame(control_frame, padding="5")
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.init_btn = ttk.Button(btn_frame, text="初始化系统", command=self.initialize_system)
        self.init_btn.pack(fill=tk.X, pady=2)
        
        self.load_states_btn = ttk.Button(btn_frame, text="加载任务状态", command=self.load_task_states, state=tk.DISABLED)
        self.load_states_btn.pack(fill=tk.X, pady=2)
        
        self.screenshot_btn = ttk.Button(btn_frame, text="截图", command=self.take_screenshot, state=tk.DISABLED)
        self.screenshot_btn.pack(fill=tk.X, pady=2)
        
        self.recognize_btn = ttk.Button(btn_frame, text="识别当前状态", command=self.recognize_state, state=tk.DISABLED)
        self.recognize_btn.pack(fill=tk.X, pady=2)
        
        self.monitor_btn = ttk.Button(btn_frame, text="开始状态监控", command=self.toggle_monitoring, state=tk.DISABLED)
        self.monitor_btn.pack(fill=tk.X, pady=2)
        
        # 创建右侧显示面板
        display_frame = ttk.Frame(main_frame)
        display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建顶部屏幕显示区域
        screen_frame = ttk.LabelFrame(display_frame, text="当前屏幕", padding="5")
        screen_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.screen_canvas = tk.Canvas(screen_frame, bg="black", width=600, height=400)
        self.screen_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 创建底部状态列表
        state_frame = ttk.LabelFrame(display_frame, text="状态列表", padding="5")
        state_frame.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # 创建状态列表
        columns = ("state_id", "app_id", "type", "name")
        self.state_tree = ttk.Treeview(state_frame, columns=columns, show="headings", height=10)
        
        self.state_tree.heading("state_id", text="状态ID")
        self.state_tree.heading("app_id", text="应用ID")
        self.state_tree.heading("type", text="类型")
        self.state_tree.heading("name", text="名称")
        
        self.state_tree.column("state_id", width=150)
        self.state_tree.column("app_id", width=150)
        self.state_tree.column("type", width=80)
        self.state_tree.column("name", width=200)
        
        self.state_tree.pack(fill=tk.BOTH, expand=True)
        
        # 添加终端命令区域
        terminal_frame = ttk.LabelFrame(display_frame, text="终端命令", padding="5")
        terminal_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(terminal_frame, text="命令:").grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(terminal_frame, textvariable=self.command_var, width=50)
        self.command_entry.grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        ttk.Button(terminal_frame, text="执行", command=self.execute_command).grid(column=2, row=0, padx=5, pady=2)
        
        # 常用命令下拉菜单
        ttk.Label(terminal_frame, text="常用命令:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
        self.common_commands = [
            "screencap /sdcard/screenshot.png",
            "tap 360 640",
            "swipe 360 800 360 400 500",
            "input text 测试文本",
            "input keyevent 4",  # 返回键
            "adb shell dumpsys window windows | findstr mCurrentFocus"  # 查看当前焦点窗口
        ]
        self.common_cmd_var = tk.StringVar()
        common_cmd_dropdown = ttk.Combobox(terminal_frame, textvariable=self.common_cmd_var, values=self.common_commands, width=50)
        common_cmd_dropdown.grid(column=1, row=1, sticky=tk.W, padx=5, pady=2)
        ttk.Button(terminal_frame, text="插入", command=lambda: self.command_var.set(self.common_cmd_var.get())).grid(column=2, row=1, padx=5, pady=2)
        
        # 创建底部状态栏
        self.status_var = tk.StringVar(value="状态: 未初始化")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建日志区域
        log_frame = ttk.LabelFrame(display_frame, text="日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 添加日志滚动条
        log_scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
    def log(self, message):
        """添加日志到日志区域"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        logger.info(message)
        
    def browse_db(self):
        """浏览数据库文件"""
        db_path = filedialog.askopenfilename(
            title="选择数据库文件",
            filetypes=[("SQLite数据库", "*.db"), ("所有文件", "*.*")]
        )
        if db_path:
            self.db_path_var.set(db_path)
            
    def initialize_system(self):
        """初始化系统组件"""
        try:
            self.log("开始初始化系统组件...")
            
            # 初始化数据库
            db_path = self.db_path_var.get()
            self.db_manager = DatabaseManager(db_path=db_path)
            self.log(f"数据库已连接: {db_path}")
            
            # 初始化设备控制器
            instance_index = int(self.instance_index_var.get())
            ld_path = self.ld_path_var.get()
            ldconsole_path = self.ldconsole_path_var.get()
            
            self.device = AndroidDeviceController(
                instance_index=instance_index,
                ld_path=ld_path,
                ldconsole_path=ldconsole_path
            )
            
            if not self.device.initialize():
                raise Exception("设备控制器初始化失败")
                
            self.log(f"设备控制器已初始化，屏幕尺寸: {self.device.screen_width}x{self.device.screen_height}")
            
            # 初始化屏幕识别器
            self.recognizer = ScreenRecognizer(self.device)
            if not self.recognizer.initialize():
                raise Exception("屏幕识别器初始化失败")
                
            self.log("屏幕识别器已初始化")
            
            # 初始化状态管理器
            self.state_manager = StateManager(self.db_manager, self.recognizer)
            if not self.state_manager.initialize():
                raise Exception("状态管理器初始化失败")
                
            self.log("状态管理器已初始化")
            
            # 更新UI状态
            self.is_initialized = True
            self.status_var.set("状态: 已初始化")
            self.load_states_btn.config(state=tk.NORMAL)
            self.screenshot_btn.config(state=tk.NORMAL)
            self.recognize_btn.config(state=tk.NORMAL)
            self.monitor_btn.config(state=tk.NORMAL)
            self.init_btn.config(state=tk.DISABLED)
            
            # 立即截图
            self.take_screenshot()
            
            # 加载状态列表
            self.load_states()
            
        except Exception as e:
            self.log(f"初始化失败: {str(e)}")
            messagebox.showerror("初始化失败", str(e))
    
    def load_task_states(self):
        """从任务加载状态配置"""
        try:
            task_name = self.task_name_var.get()
            app_id = self.app_id_var.get()
            
            if not task_name or not app_id:
                messagebox.showwarning("警告", "请输入任务名称和应用ID")
                return
                
            self.log(f"正在加载任务 {task_name} 的状态配置...")
            
            # 检查任务数据库路径
            task_db_path = f"tasks/{task_name}/db/{task_name}.db"
            if not os.path.exists(task_db_path):
                self.log(f"警告: 任务数据库不存在: {task_db_path}")
                self.log(f"尝试检查备选路径...")
                
                # 尝试检查其他可能的路径
                alt_paths = [
                    f"tasks/{task_name}/{task_name}.db",
                    f"tasks/{task_name}/db/task.db",
                    f"tasks/{task_name}/automation.db"
                ]
                
                found = False
                for path in alt_paths:
                    if os.path.exists(path):
                        task_db_path = path
                        self.log(f"找到任务数据库: {path}")
                        found = True
                        break
                
                if not found:
                    messagebox.showerror("错误", f"找不到任务 {task_name} 的数据库")
                    return
            
            if hasattr(self.state_manager, "load_states_from_task"):
                success = self.state_manager.load_states_from_task(task_name, app_id)
                if success:
                    self.log(f"成功加载任务 {task_name} 的状态配置")
                    # 重新加载状态列表
                    self.load_states()
                else:
                    # 尝试手动加载
                    self.log("尝试手动加载任务状态...")
                    success = self.manual_load_task_states(task_name, app_id, task_db_path)
                    if success:
                        self.log(f"成功手动加载任务 {task_name} 的状态配置")
                        self.load_states()
                    else:
                        self.log(f"手动加载任务状态失败")
            else:
                self.log("状态管理器没有实现 load_states_from_task 方法，尝试手动加载...")
                success = self.manual_load_task_states(task_name, app_id, task_db_path)
                if success:
                    self.log(f"成功手动加载任务 {task_name} 的状态配置")
                    self.load_states()
                else:
                    self.log(f"手动加载任务状态失败")
                
        except Exception as e:
            self.log(f"加载任务状态失败: {str(e)}")
            messagebox.showerror("加载任务状态失败", str(e))
            
    def manual_load_task_states(self, task_name, app_id, task_db_path):
        """手动从任务数据库加载状态配置
        
        Args:
            task_name: 任务名称
            app_id: 应用ID
            task_db_path: 任务数据库路径
            
        Returns:
            是否成功
        """
        try:
            import sqlite3
            import json
            
            self.log(f"连接任务数据库: {task_db_path}")
            conn = sqlite3.connect(task_db_path)
            conn.row_factory = sqlite3.Row
            
            # 检查states表是否存在
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [table['name'] for table in tables]
            
            self.log(f"数据库中的表: {', '.join(table_names)}")
            
            states_table = None
            transitions_table = None
            
            # 查找可能的状态表名
            potential_state_tables = ['states', 'recognition_states', f'{task_name}_states']
            for table in potential_state_tables:
                if table in table_names:
                    states_table = table
                    self.log(f"使用状态表: {states_table}")
                    break
                    
            # 查找可能的转换表名
            potential_transition_tables = ['transitions', 'state_transitions', 'actions', f'{task_name}_transitions']
            for table in potential_transition_tables:
                if table in table_names:
                    transitions_table = table
                    self.log(f"使用转换表: {transitions_table}")
                    break
            
            if not states_table:
                self.log("无法找到状态表")
                conn.close()
                return False
                
            # 获取状态表结构
            cursor = conn.execute(f"PRAGMA table_info({states_table})")
            columns = [col['name'] for col in cursor.fetchall()]
            self.log(f"状态表列: {', '.join(columns)}")
            
            # 确定列映射
            state_id_col = 'state_id' if 'state_id' in columns else 'id'
            type_col = 'type' if 'type' in columns else 'recognition_type'
            name_col = 'name' if 'name' in columns else 'description'
            config_col = 'config' if 'config' in columns else 'recognition_config'
            
            # 加载状态
            query = f"SELECT {state_id_col}, {type_col}, {name_col}, {config_col} FROM {states_table}"
            cursor = conn.execute(query)
            states = cursor.fetchall()
            
            for state in states:
                state_id = state[state_id_col]
                state_type = state[type_col]
                state_name = state[name_col]
                config = state[config_col]
                
                # 确保config是JSON字符串
                if isinstance(config, dict):
                    config_str = json.dumps(config)
                else:
                    config_str = config
                
                # 注册状态
                recognition_config = {
                    "name": state_name,
                    "type": state_type,
                    "config": json.loads(config_str) if isinstance(config_str, str) else {}
                }
                
                self.db_manager.execute(
                    "INSERT OR REPLACE INTO recognition_states (state_id, app_id, name, type, config) VALUES (?, ?, ?, ?, ?)",
                    (state_id, app_id, state_name, state_type, config_str)
                )
                
                self.log(f"导入状态: {state_id}")
            
            # 如果找到了转换表，加载转换
            if transitions_table:
                # 获取转换表结构
                cursor = conn.execute(f"PRAGMA table_info({transitions_table})")
                columns = [col['name'] for col in cursor.fetchall()]
                self.log(f"转换表列: {', '.join(columns)}")
                
                # 确定列映射
                from_state_col = 'from_state' if 'from_state' in columns else 'source_state'
                to_state_col = 'to_state' if 'to_state' in columns else 'target_state'
                action_col = 'action' if 'action' in columns else 'name'
                function_col = 'function_name' if 'function_name' in columns else 'action_function'
                params_col = 'params' if 'params' in columns else 'action_params'
                
                # 加载转换
                query = f"SELECT {from_state_col}, {to_state_col}, {action_col}, {function_col}, {params_col} FROM {transitions_table}"
                cursor = conn.execute(query)
                transitions = cursor.fetchall()
                
                for transition in transitions:
                    from_state = transition[from_state_col]
                    to_state = transition[to_state_col]
                    action = transition[action_col]
                    function_name = transition[function_col]
                    params = transition[params_col]
                    
                    # 确保params是JSON字符串
                    if isinstance(params, dict):
                        params_str = json.dumps(params)
                    else:
                        params_str = params
                    
                    # 注册转换
                    self.db_manager.execute(
                        "INSERT OR REPLACE INTO actions (from_state, to_state, name, function_name, params) VALUES (?, ?, ?, ?, ?)",
                        (from_state, to_state, action, function_name, params_str)
                    )
                    
                    self.log(f"导入转换: {from_state} -> {to_state}")
            
            conn.close()
            return True
            
        except Exception as e:
            self.log(f"手动加载任务状态失败: {str(e)}")
            return False
    
    def load_states(self):
        """加载状态列表"""
        try:
            # 清空现有状态
            for item in self.state_tree.get_children():
                self.state_tree.delete(item)
                
            # 检查数据库表是否存在
            table_exists = self.db_manager.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='recognition_states'"
            )
            
            if not table_exists:
                self.log("警告: recognition_states 表不存在，将创建表")
                # 创建表
                self.db_manager.execute("""
                CREATE TABLE IF NOT EXISTS recognition_states (
                    state_id TEXT PRIMARY KEY,
                    app_id TEXT,
                    name TEXT,
                    type TEXT,
                    config TEXT
                )
                """)
                self.log("创建了 recognition_states 表")
                
                # 创建动作表
                self.db_manager.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_state TEXT,
                    to_state TEXT,
                    name TEXT,
                    function_name TEXT,
                    params TEXT,
                    FOREIGN KEY (from_state) REFERENCES recognition_states (state_id),
                    FOREIGN KEY (to_state) REFERENCES recognition_states (state_id)
                )
                """)
                self.log("创建了 actions 表")
                
            # 从数据库加载状态
            states = self.db_manager.fetch_all("SELECT * FROM recognition_states")
            
            for state in states:
                self.state_tree.insert("", tk.END, values=(
                    state['state_id'],
                    state['app_id'],
                    state['type'],
                    state['name']
                ))
                
            self.log(f"已加载 {len(states)} 个状态")
            
        except Exception as e:
            self.log(f"加载状态列表失败: {str(e)}")
    
    def take_screenshot(self):
        """截取屏幕并显示"""
        try:
            self.log("正在截取屏幕...")
            screenshot = self.device.take_screenshot()
            
            if screenshot:
                # 调整图像大小以适应画布
                canvas_width = self.screen_canvas.winfo_width()
                canvas_height = self.screen_canvas.winfo_height()
                
                if canvas_width > 50 and canvas_height > 50:  # 确保画布已经正确调整大小
                    aspect_ratio = screenshot.width / screenshot.height
                    
                    if canvas_width / canvas_height > aspect_ratio:
                        # 按高度缩放
                        new_height = canvas_height
                        new_width = int(aspect_ratio * new_height)
                    else:
                        # 按宽度缩放
                        new_width = canvas_width
                        new_height = int(new_width / aspect_ratio)
                    
                    resized_img = screenshot.resize((new_width, new_height), Image.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(resized_img)
                    
                    # 清除画布并显示新图像
                    self.screen_canvas.delete("all")
                    self.screen_canvas.create_image(
                        canvas_width // 2, canvas_height // 2, 
                        image=self.photo_image, anchor=tk.CENTER
                    )
                    
                    self.log(f"屏幕截图已更新，尺寸: {screenshot.width}x{screenshot.height}")
                else:
                    self.log("画布尺寸不足，无法显示截图")
            else:
                self.log("截图失败")
                
        except Exception as e:
            self.log(f"截图失败: {str(e)}")
    
    def recognize_state(self):
        """识别当前状态"""
        try:
            self.log("正在识别当前状态...")
            
            # 先更新截图
            self.take_screenshot()
            
            # 识别状态
            app_id = self.app_id_var.get() if self.app_id_var.get() else None
            state_id = self.state_manager.recognize_current_scene(app_id)
            
            if state_id:
                self.log(f"识别到状态: {state_id}")
                self.status_var.set(f"当前状态: {state_id}")
                
                # 在状态列表中高亮显示当前状态
                for item in self.state_tree.get_children():
                    values = self.state_tree.item(item, "values")
                    if values and values[0] == state_id:
                        self.state_tree.selection_set(item)
                        self.state_tree.see(item)
                        break
            else:
                self.log("无法识别当前状态")
                self.status_var.set("当前状态: 未知")
                
        except Exception as e:
            self.log(f"识别状态失败: {str(e)}")
    
    def toggle_monitoring(self):
        """切换状态监控"""
        if not self.is_monitoring:
            try:
                self.log("开始状态监控...")
                
                # 设置监控间隔
                interval = 2.0  # 默认2秒
                
                # 启动状态管理器的监控
                if self.state_manager.start_monitoring(interval):
                    self.is_monitoring = True
                    self.monitor_btn.config(text="停止状态监控")
                    
                    # 启动UI更新线程
                    self.monitoring_thread = threading.Thread(target=self.update_monitoring_ui)
                    self.monitoring_thread.daemon = True
                    self.monitoring_thread.start()
                    
                    self.log(f"状态监控已启动，间隔: {interval}秒")
                else:
                    self.log("启动状态监控失败")
                    
            except Exception as e:
                self.log(f"启动状态监控失败: {str(e)}")
        else:
            try:
                self.log("停止状态监控...")
                
                # 停止状态管理器的监控
                if self.state_manager.stop_monitoring():
                    self.is_monitoring = False
                    self.monitor_btn.config(text="开始状态监控")
                    self.log("状态监控已停止")
                else:
                    self.log("停止状态监控失败")
                    
            except Exception as e:
                self.log(f"停止状态监控失败: {str(e)}")
    
    def update_monitoring_ui(self):
        """更新监控UI的线程函数"""
        while self.is_monitoring:
            try:
                # 获取当前状态
                current_state = self.state_manager.get_current_state()
                
                # 更新UI
                self.root.after(0, lambda: self.status_var.set(f"当前状态: {current_state or '未知'}"))
                
                # 每隔一段时间更新截图
                self.root.after(0, self.take_screenshot)
                
                # 高亮当前状态
                if current_state:
                    def highlight_state():
                        for item in self.state_tree.get_children():
                            values = self.state_tree.item(item, "values")
                            if values and values[0] == current_state:
                                self.state_tree.selection_set(item)
                                self.state_tree.see(item)
                                break
                    
                    self.root.after(0, highlight_state)
                
                # 暂停一下，避免过于频繁地更新UI
                time.sleep(1.5)
                
            except Exception as e:
                logger.error(f"更新监控UI失败: {str(e)}")
                time.sleep(2)
    
    def execute_command(self):
        """执行终端命令"""
        command = self.command_var.get().strip()
        if not command:
            return
            
        try:
            self.log(f"执行命令: {command}")
            
            if not self.device or not self.device.is_initialized:
                messagebox.showerror("错误", "设备未初始化")
                return
                
            # 解析命令
            cmd_parts = command.split()
            if not cmd_parts:
                return
                
            base_cmd = cmd_parts[0].lower()
            
            # 执行不同类型的命令
            if base_cmd == "tap" and len(cmd_parts) >= 3:
                x, y = int(cmd_parts[1]), int(cmd_parts[2])
                result = self.device.tap(x, y)
                self.log(f"点击坐标 ({x}, {y}): {'成功' if result else '失败'}")
                
            elif base_cmd == "swipe" and len(cmd_parts) >= 5:
                x1, y1, x2, y2 = int(cmd_parts[1]), int(cmd_parts[2]), int(cmd_parts[3]), int(cmd_parts[4])
                duration = int(cmd_parts[5]) if len(cmd_parts) >= 6 else 300
                result = self.device.swipe(x1, y1, x2, y2, duration)
                self.log(f"滑动 ({x1}, {y1}) -> ({x2}, {y2}), 持续{duration}ms: {'成功' if result else '失败'}")
                
            elif base_cmd == "input" and len(cmd_parts) >= 2:
                input_type = cmd_parts[1].lower()
                if input_type == "text" and len(cmd_parts) >= 3:
                    text = ' '.join(cmd_parts[2:])
                    result = self.device.input_text(text)
                    self.log(f"输入文本 '{text}': {'成功' if result else '失败'}")
                    
                elif input_type == "keyevent" and len(cmd_parts) >= 3:
                    keycode = int(cmd_parts[2])
                    result = self.device.press_key(keycode)
                    self.log(f"按键 {keycode}: {'成功' if result else '失败'}")
                    
            elif base_cmd == "screencap":
                if len(cmd_parts) >= 2:
                    filename = cmd_parts[1]
                    result = self.device.take_screenshot(filename)
                    self.log(f"截图到 {filename}: {'成功' if result else '失败'}")
                else:
                    # 直接更新UI上的截图
                    self.take_screenshot()
                    
            elif base_cmd == "back":
                result = self.device.back()
                self.log(f"返回按键: {'成功' if result else '失败'}")
                
            elif base_cmd == "home":
                result = self.device.home()
                self.log(f"Home按键: {'成功' if result else '失败'}")
                
            elif base_cmd == "sleep" and len(cmd_parts) >= 2:
                seconds = float(cmd_parts[1])
                self.log(f"等待 {seconds} 秒...")
                self.device.wait(seconds)
                self.log("等待完成")
                
            else:
                # 对于其他命令，尝试直接执行
                import subprocess
                
                # 构建命令字符串，使用设备的索引
                if cmd_parts[0].lower() in ["adb", "shell"]:
                    # 用户输入的是adb命令，转换为雷电命令
                    cmd = f'"{self.device.ld_path}" -s {self.device.instance_index} {" ".join(cmd_parts[1:])}'
                else:
                    # 直接使用用户输入的命令
                    cmd = f'"{self.device.ld_path}" -s {self.device.instance_index} {command}'
                
                result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
                self.log(f"命令输出:\n{result}")
                
            # 延时执行截图，显示命令执行后的结果
            self.root.after(1000, self.take_screenshot)
                
        except Exception as e:
            self.log(f"执行命令失败: {str(e)}")
    
    def run(self):
        """运行调试窗口"""
        # 绑定回车键执行命令
        self.command_entry.bind("<Return>", lambda event: self.execute_command())
        
        self.root.mainloop()
        
        # 退出前清理
        if self.is_monitoring:
            try:
                self.state_manager.stop_monitoring()
            except:
                pass
            
        # 关闭所有组件
        components = [self.state_manager, self.recognizer, self.device, self.db_manager]
        for component in components:
            if component:
                try:
                    component.shutdown()
                except:
                    pass

def main():
    """主函数"""
    print("启动状态识别调试工具...")
    
    try:
        # 创建并运行调试窗口
        window = StateRecognitionDebugWindow()
        window.run()
        
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
