"""
调试系统启动器
提供各种调试模块的启动入口
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging
import time

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 配置日志
logs_dir = os.path.join(project_root, 'debug', 'logs')
os.makedirs(logs_dir, exist_ok=True)

log_filename = os.path.join(logs_dir, f'launcher_{time.strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=log_filename,
    filemode='w'
)
logger = logging.getLogger('DebugLauncher')

# 输出日志到控制台
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

logger.info(f"调试启动器日志文件: {log_filename}")
logger.info(f"项目根目录: {project_root}")

# 全局变量，用于存储已初始化的模块实例
initialized_modules = {}


class DebugLauncher:
    def __init__(self):
        """初始化调试启动器"""
        logger.info("开始初始化调试启动器")

        # 初始化状态
        self.initialized = False

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("调试系统启动器")
        self.root.geometry("800x600")

        # 添加窗口图标
        try:
            icon_path = os.path.join(project_root, "debug", "resources", "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"设置窗口图标失败: {e}")

        # 创建状态变量
        self.status_var = tk.StringVar(value="准备就绪")

        # 创建初始化提示
        self.init_frame = ttk.Frame(self.root)
        self.init_frame.pack(fill=tk.BOTH, expand=True)

        init_label = ttk.Label(
            self.init_frame,
            text="欢迎使用调试系统\n请选择初始化模式",
            font=("Arial", 18),
            anchor=tk.CENTER
        )
        init_label.pack(pady=50)

        # 初始化选项按钮
        btn_frame = ttk.Frame(self.init_frame)
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text="完整初始化",
            command=self.full_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        ttk.Button(
            btn_frame,
            text="仅设备调试",
            command=self.device_only_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        ttk.Button(
            btn_frame,
            text="仅数据库调试",
            command=self.database_only_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        # 显示状态栏
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        logger.info("调试启动器界面初始化完成")

    def update_status(self, message):
        """更新状态栏信息"""
        self.status_var.set(message)
        self.root.update_idletasks()
        logger.info(message)

    def full_initialize(self):
        """完整初始化所有系统模块"""
        self.update_status("正在完整初始化系统...")

        # 导入所需模块
        try:
            from data.database_manager import DatabaseManager
            from data.config import Config
            from components.device_controller import AndroidDeviceController
            from components.screen_recognizer import ScreenRecognizer
            from components.state_manager import StateManager
            from schedulers.task_manager import TaskManager
            from schedulers.account_service import AccountService

            # 1. 初始化配置
            self.update_status("初始化配置...")
            self.config = Config()
            initialized_modules['Config'] = self.config

            # 2. 初始化数据库管理器
            self.update_status("初始化数据库管理器...")
            db_path = self.config.get('database.path', 'automation.db')
            self.db_manager = DatabaseManager(db_path=db_path)
            initialized_modules['DatabaseManager'] = self.db_manager

            # 3. 初始化设备控制器
            self.update_status("初始化设备控制器...")
            self.device_controller = AndroidDeviceController()

            # 显式调用初始化方法
            if hasattr(self.device_controller, 'initialize'):
                self.device_controller.initialize()
                logger.info("已显式调用设备控制器初始化方法")

            # 检查初始化状态
            if hasattr(self.device_controller, 'is_initialized') and self.device_controller.is_initialized:
                logger.info("设备控制器初始化成功")
            else:
                logger.warning("设备控制器初始化失败")
                # 提示用户使用诊断工具
                messagebox.showwarning("警告", "设备控制器初始化失败，请使用设备诊断工具检查问题")

            initialized_modules['AndroidDeviceController'] = self.device_controller

            # 4. 初始化屏幕识别器
            self.update_status("初始化屏幕识别器...")
            self.screen_recognizer = ScreenRecognizer(self.device_controller)
            initialized_modules['ScreenRecognizer'] = self.screen_recognizer

            # 5. 初始化任务管理器
            self.update_status("初始化任务管理器...")
            self.task_manager = TaskManager(self.db_manager)
            initialized_modules['TaskManager'] = self.task_manager

            # 6. 初始化账号服务
            self.update_status("初始化账号服务...")
            self.account_service = AccountService(self.db_manager)
            initialized_modules['AccountService'] = self.account_service

            # 7. 初始化状态管理器
            self.update_status("初始化状态管理器...")
            self.state_manager = StateManager(self.db_manager, self.screen_recognizer)
            initialized_modules['StateManager'] = self.state_manager

            # 标记初始化成功
            self.initialized = True
            self.update_status("系统模块初始化完成")

            # 创建主界面
            self.init_frame.destroy()
            self.create_main_frame()

        except Exception as e:
            logger.error(f"完整初始化系统模块时发生错误: {e}", exc_info=True)
            self.update_status(f"初始化失败: {e}")
            # 提示用户
            messagebox.showerror("错误", f"初始化系统模块失败: {str(e)}")

    def device_only_initialize(self):
        """仅初始化设备调试相关模块"""
        self.update_status("正在初始化设备调试模块...")

        try:
            from components.device_controller import AndroidDeviceController

            # 初始化设备控制器
            self.update_status("初始化设备控制器...")
            self.device_controller = AndroidDeviceController()

            # 显式调用初始化方法
            if hasattr(self.device_controller, 'initialize'):
                self.device_controller.initialize()
                logger.info("已显式调用设备控制器初始化方法")

            # 检查初始化状态
            if hasattr(self.device_controller, 'is_initialized') and self.device_controller.is_initialized:
                logger.info("设备控制器初始化成功")
                initialized_modules['AndroidDeviceController'] = self.device_controller

                # 尝试初始化屏幕识别器
                try:
                    from components.screen_recognizer import ScreenRecognizer
                    self.update_status("初始化屏幕识别器...")
                    self.screen_recognizer = ScreenRecognizer(self.device_controller)
                    initialized_modules['ScreenRecognizer'] = self.screen_recognizer
                except Exception as e:
                    logger.error(f"初始化屏幕识别器失败: {e}")

                # 标记初始化成功
                self.initialized = True
                self.update_status("设备调试模块初始化完成")

                # 创建设备调试界面
                self.init_frame.destroy()
                self.create_device_debug_frame()
            else:
                logger.warning("设备控制器初始化失败")
                self.update_status("设备控制器初始化失败")
                # 提示用户
                messagebox.showwarning("警告", "设备控制器初始化失败，请检查连接或使用设备诊断工具")

                # 显示诊断选项
                diag_btn = ttk.Button(
                    self.init_frame,
                    text="打开设备诊断工具",
                    command=self.open_device_diagnostic_tool
                )
                diag_btn.pack(pady=20)

        except Exception as e:
            logger.error(f"初始化设备调试模块时发生错误: {e}", exc_info=True)
            self.update_status(f"初始化失败: {e}")
            # 提示用户
            messagebox.showerror("错误", f"初始化设备调试模块失败: {str(e)}")

    def database_only_initialize(self):
        """仅初始化数据库调试相关模块"""
        self.update_status("正在初始化数据库调试模块...")

        try:
            from data.database_manager import DatabaseManager
            from data.config import Config

            # 初始化配置
            self.update_status("初始化配置...")
            self.config = Config()
            initialized_modules['Config'] = self.config

            # 初始化数据库管理器
            self.update_status("初始化数据库管理器...")
            db_path = self.config.get('database.path', 'automation.db')
            self.db_manager = DatabaseManager(db_path=db_path)
            initialized_modules['DatabaseManager'] = self.db_manager

            # 标记初始化成功
            self.initialized = True
            self.update_status("数据库调试模块初始化完成")

            # 创建数据库调试界面
            self.init_frame.destroy()
            self.create_database_debug_frame()

        except Exception as e:
            logger.error(f"初始化数据库调试模块时发生错误: {e}", exc_info=True)
            self.update_status(f"初始化失败: {e}")
            # 提示用户
            messagebox.showerror("错误", f"初始化数据库调试模块失败: {str(e)}")

    def create_main_frame(self):
        """创建主调试面板"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建分类选项卡
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 设备和屏幕识别选项卡
        device_frame = ttk.Frame(notebook)
        notebook.add(device_frame, text="设备与识别")

        # 数据库选项卡
        db_frame = ttk.Frame(notebook)
        notebook.add(db_frame, text="数据库")

        # 任务与状态选项卡
        task_frame = ttk.Frame(notebook)
        notebook.add(task_frame, text="任务与状态")

        # 诊断工具选项卡
        diag_frame = ttk.Frame(notebook)
        notebook.add(diag_frame, text="诊断工具")

        # 设备与识别选项卡内容
        ttk.Button(device_frame, text="屏幕识别调试",
                   command=self.open_screen_recognition_panel).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(device_frame, text="设备控制调试",
                   command=self.open_device_control_panel).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(device_frame, text="OCR文本识别调试",
                   command=self.open_ocr_debug_panel).pack(pady=10, padx=50, fill=tk.X)

        ttk.Button(device_frame, text="设备诊断工具",
                   command=self.open_device_diagnostic_tool).pack(pady=10, padx=20, fill=tk.X)

        # 数据库选项卡内容
        ttk.Button(db_frame, text="数据库查询",
                   command=self.open_database_panel).pack(pady=10, padx=20, fill=tk.X)

        # 任务与状态选项卡内容
        ttk.Button(task_frame, text="状态管理调试",
                   command=self.open_state_management_panel).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(task_frame, text="任务管理调试",
                   command=self.open_task_management_panel).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(task_frame, text="账号服务调试",
                   command=self.open_account_service_panel).pack(pady=10, padx=20, fill=tk.X)

        # 诊断工具选项卡内容
        ttk.Label(diag_frame, text="系统诊断工具").pack(pady=5)

        ttk.Button(diag_frame, text="检查系统状态",
                   command=self.check_system_status).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(diag_frame, text="重新初始化系统",
                   command=self.reinitialize_system).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(diag_frame, text="查看系统日志",
                   command=self.view_system_logs).pack(pady=10, padx=20, fill=tk.X)

    def open_ocr_debug_panel(self):
        """打开OCR调试面板"""
        self.update_status("正在打开OCR调试面板...")

        if 'AndroidDeviceController' not in initialized_modules:
            messagebox.showerror("错误", "设备控制器未初始化，无法打开OCR调试面板")
            return

        try:
            # 导入OCR调试面板
            from debug.ocr_debug_tool import OCRDebugPanel

            # 创建OCR调试窗口
            ocr_window = tk.Toplevel(self.root)
            ocr_window.title("OCR文本识别调试")
            ocr_window.geometry("1200x800")

            # 创建屏幕面板
            from debug.screen_panel import ScreenPanel
            screen_panel = ScreenPanel(ocr_window, initialized_modules['AndroidDeviceController'])
            screen_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 创建OCR调试面板
            ocr_debug_panel = OCRDebugPanel(
                ocr_window,
                initialized_modules['ScreenRecognizer'],
                screen_panel
            )
            ocr_debug_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

            self.update_status("OCR调试面板已打开")

        except ModuleNotFoundError:
            logger.error("OCR调试面板模块不存在")
            self.update_status("OCR调试面板模块不存在")
            messagebox.showerror("错误", "OCR调试面板模块不存在")
        except Exception as e:
            logger.error(f"打开OCR调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开OCR调试面板失败: {e}")
            messagebox.showerror("错误", f"打开OCR调试面板失败: {str(e)}")

    def create_device_debug_frame(self):
        """创建设备调试专用面板"""
        device_frame = ttk.Frame(self.root)
        device_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 标题
        ttk.Label(device_frame, text="设备调试面板", font=("Arial", 16)).pack(pady=10)

        # 功能按钮
        ttk.Button(device_frame, text="屏幕识别调试",
                   command=self.open_screen_recognition_panel).pack(pady=10, padx=50, fill=tk.X)

        ttk.Button(device_frame, text="设备控制调试",
                   command=self.open_device_control_panel).pack(pady=10, padx=50, fill=tk.X)

        ttk.Button(device_frame, text="OCR文本识别调试",
                   command=self.open_ocr_debug_panel).pack(pady=10, padx=20, fill=tk.X)

        ttk.Button(device_frame, text="设备诊断工具",
                   command=self.open_device_diagnostic_tool).pack(pady=10, padx=50, fill=tk.X)

        # 分隔线
        ttk.Separator(device_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=50, pady=20)

        # 返回按钮
        ttk.Button(device_frame, text="返回初始化选择",
                   command=self.back_to_init).pack(pady=10, padx=50)

    def create_database_debug_frame(self):
        """创建数据库调试专用面板"""
        db_frame = ttk.Frame(self.root)
        db_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 标题
        ttk.Label(db_frame, text="数据库调试面板", font=("Arial", 16)).pack(pady=10)

        # 功能按钮
        ttk.Button(db_frame, text="数据库查询",
                   command=self.open_database_panel).pack(pady=10, padx=50, fill=tk.X)

        # 分隔线
        ttk.Separator(db_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=50, pady=20)

        # 返回按钮
        ttk.Button(db_frame, text="返回初始化选择",
                   command=self.back_to_init).pack(pady=10, padx=50)

    def back_to_init(self):
        """返回初始化选择界面"""
        # 清除当前界面
        for widget in self.root.winfo_children():
            widget.destroy()

        # 重新创建初始化界面
        self.init_frame = ttk.Frame(self.root)
        self.init_frame.pack(fill=tk.BOTH, expand=True)

        init_label = ttk.Label(
            self.init_frame,
            text="欢迎使用调试系统\n请选择初始化模式",
            font=("Arial", 18),
            anchor=tk.CENTER
        )
        init_label.pack(pady=50)

        # 初始化选项按钮
        btn_frame = ttk.Frame(self.init_frame)
        btn_frame.pack(pady=20)

        ttk.Button(
            btn_frame,
            text="完整初始化",
            command=self.full_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        ttk.Button(
            btn_frame,
            text="仅设备调试",
            command=self.device_only_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        ttk.Button(
            btn_frame,
            text="仅数据库调试",
            command=self.database_only_initialize
        ).pack(side=tk.LEFT, padx=10, ipadx=10, ipady=5)

        # 显示状态栏
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 更新状态
        self.update_status("已返回初始化选择界面")

    def open_screen_recognition_panel(self):
        """打开屏幕识别调试面板"""
        self.update_status("正在打开屏幕识别调试面板...")

        if 'AndroidDeviceController' not in initialized_modules:
            messagebox.showerror("错误", "设备控制器未初始化，无法打开屏幕识别调试面板")
            return

        try:
            from debug.screen_panel import ScreenPanel
            from debug.recognition_panel import RecognitionPanel

            # 创建调试窗口
            recognition_window = tk.Toplevel(self.root)
            recognition_window.title("屏幕识别调试")
            recognition_window.geometry("1200x800")

            # 创建屏幕面板和识别面板
            screen_panel = ScreenPanel(recognition_window, initialized_modules['AndroidDeviceController'])
            screen_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 如果有屏幕识别器，则创建识别面板
            if 'ScreenRecognizer' in initialized_modules:
                recognition_panel = RecognitionPanel(
                    recognition_window,
                    initialized_modules['ScreenRecognizer'],
                    screen_panel
                )
                recognition_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

            self.update_status("屏幕识别调试面板已打开")

        except Exception as e:
            logger.error(f"打开屏幕识别调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开屏幕识别调试面板失败: {e}")
            messagebox.showerror("错误", f"打开屏幕识别调试面板失败: {str(e)}")

    def open_device_control_panel(self):
        """打开设备控制调试面板"""
        self.update_status("正在打开设备控制调试面板...")

        if 'AndroidDeviceController' not in initialized_modules:
            messagebox.showerror("错误", "设备控制器未初始化，无法打开设备控制调试面板")
            return

        try:
            # 导入设备控制面板模块
            # 注意：这个模块需要先创建
            from debug.device_panel import DeviceControlPanel

            device_window = tk.Toplevel(self.root)
            device_window.title("设备控制调试")
            device_window.geometry("800x600")

            device_panel = DeviceControlPanel(
                device_window,
                initialized_modules['AndroidDeviceController']
            )
            device_panel.pack(fill=tk.BOTH, expand=True)

            self.update_status("设备控制调试面板已打开")

        except ModuleNotFoundError:
            logger.error("设备控制面板模块不存在")
            self.update_status("设备控制面板模块不存在")
            messagebox.showerror("错误", "设备控制面板模块不存在，请先创建该模块")
        except Exception as e:
            logger.error(f"打开设备控制调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开设备控制调试面板失败: {e}")
            messagebox.showerror("错误", f"打开设备控制调试面板失败: {str(e)}")

    def open_device_diagnostic_tool(self):
        """打开设备诊断工具"""
        self.update_status("正在打开设备诊断工具...")

        try:
            # 导入诊断工具模块
            from debug.device_diagnostic import DeviceDiagnosticTool

            # 直接运行诊断工具
            tool = DeviceDiagnosticTool()
            tool.run()

            self.update_status("设备诊断工具已启动")

        except ModuleNotFoundError:
            logger.error("设备诊断工具模块不存在")
            self.update_status("设备诊断工具模块不存在")
            messagebox.showerror("错误", "设备诊断工具模块不存在，请先创建该模块")
        except Exception as e:
            logger.error(f"打开设备诊断工具时发生错误: {e}", exc_info=True)
            self.update_status(f"打开设备诊断工具失败: {e}")
            messagebox.showerror("错误", f"打开设备诊断工具失败: {str(e)}")

    def open_database_panel(self):
        """打开数据库查询面板"""
        self.update_status("正在打开数据库查询面板...")

        if 'DatabaseManager' not in initialized_modules:
            messagebox.showerror("错误", "数据库管理器未初始化，无法打开数据库查询面板")
            return

        try:
            from debug.database_panel import DatabaseQueryPanel

            # 只传递一个参数 - 父窗口
            db_panel = DatabaseQueryPanel(self.root)

            # DatabaseQueryPanel类会自己初始化DatabaseManager，不需要我们传递

            self.update_status("数据库查询面板已打开")

        except Exception as e:
            logger.error(f"打开数据库查询面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开数据库查询面板失败: {e}")
            messagebox.showerror("错误", f"打开数据库查询面板失败: {str(e)}")
    def open_state_management_panel(self):
        """打开状态管理调试面板"""
        self.update_status("正在打开状态管理调试面板...")

        if 'StateManager' not in initialized_modules:
            messagebox.showerror("错误", "状态管理器未初始化，无法打开状态管理调试面板")
            return

        try:
            from debug.state_panel import StateManagementPanel

            state_window = tk.Toplevel(self.root)
            state_window.title("状态管理调试")
            state_window.geometry("1000x700")

            state_panel = StateManagementPanel(
                state_window,
                initialized_modules['StateManager'],
                initialized_modules.get('ScreenRecognizer')
            )
            state_panel.pack(fill=tk.BOTH, expand=True)

            self.update_status("状态管理调试面板已打开")

        except Exception as e:
            logger.error(f"打开状态管理调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开状态管理调试面板失败: {e}")
            messagebox.showerror("错误", f"打开状态管理调试面板失败: {str(e)}")

    def open_task_management_panel(self):
        """打开任务管理调试面板"""
        self.update_status("正在打开任务管理调试面板...")

        if 'TaskManager' not in initialized_modules:
            messagebox.showerror("错误", "任务管理器未初始化，无法打开任务管理调试面板")
            return

        try:
            # 导入任务管理面板模块
            # 注意：这个模块可能需要先创建
            from debug.task_panel import TaskManagementPanel

            task_window = tk.Toplevel(self.root)
            task_window.title("任务管理调试")
            task_window.geometry("1000x700")

            task_panel = TaskManagementPanel(
                task_window,
                initialized_modules['TaskManager']
            )
            task_panel.pack(fill=tk.BOTH, expand=True)

            self.update_status("任务管理调试面板已打开")

        except ModuleNotFoundError:
            logger.error("任务管理面板模块不存在")
            self.update_status("任务管理面板模块不存在")
            messagebox.showerror("错误", "任务管理面板模块不存在，请先创建该模块")
        except Exception as e:
            logger.error(f"打开任务管理调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开任务管理调试面板失败: {e}")
            messagebox.showerror("错误", f"打开任务管理调试面板失败: {str(e)}")

    def open_account_service_panel(self):
        """打开账号服务调试面板"""
        self.update_status("正在打开账号服务调试面板...")

        if 'AccountService' not in initialized_modules:
            messagebox.showerror("错误", "账号服务未初始化，无法打开账号服务调试面板")
            return

        try:
            # 导入账号服务面板模块
            # 注意：这个模块可能需要先创建
            from debug.account_panel import AccountServicePanel

            account_window = tk.Toplevel(self.root)
            account_window.title("账号服务调试")
            account_window.geometry("1000x700")

            account_panel = AccountServicePanel(
                account_window,
                initialized_modules['AccountService']
            )
            account_panel.pack(fill=tk.BOTH, expand=True)

            self.update_status("账号服务调试面板已打开")

        except ModuleNotFoundError:
            logger.error("账号服务面板模块不存在")
            self.update_status("账号服务面板模块不存在")
            messagebox.showerror("错误", "账号服务面板模块不存在，请先创建该模块")
        except Exception as e:
            logger.error(f"打开账号服务调试面板时发生错误: {e}", exc_info=True)
            self.update_status(f"打开账号服务调试面板失败: {e}")
            messagebox.showerror("错误", f"打开账号服务调试面板失败: {str(e)}")

    def check_system_status(self):
        """检查系统状态"""
        self.update_status("正在检查系统状态...")

        status_window = tk.Toplevel(self.root)
        status_window.title("系统状态检查")
        status_window.geometry("600x400")

        # 创建状态显示文本区域
        text_frame = ttk.Frame(status_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 文本区域和滚动条
        scroll = ttk.Scrollbar(text_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        status_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scroll.set)
        status_text.pack(fill=tk.BOTH, expand=True)

        scroll.config(command=status_text.yview)

        # 显示系统状态
        status_text.insert(tk.END, "=== 系统状态检查 ===\n\n")

        # 检查已初始化的模块
        status_text.insert(tk.END, "已初始化的模块:\n")
        for module_name, module in initialized_modules.items():
            status = "正常" if hasattr(module, 'is_initialized') and module.is_initialized else "异常"
            status_text.insert(tk.END, f"- {module_name}: {status}\n")

        # 检查Python版本
        status_text.insert(tk.END, f"\nPython版本: {sys.version}\n")

        # 检查系统平台
        status_text.insert(tk.END, f"系统平台: {sys.platform}\n")

        # 检查项目目录
        status_text.insert(tk.END, f"项目根目录: {project_root}\n")

        # 检查日志目录
        status_text.insert(tk.END, f"日志目录: {logs_dir}\n")

        # 检查数据库
        if 'DatabaseManager' in initialized_modules:
            db_manager = initialized_modules['DatabaseManager']
            if hasattr(db_manager, 'db_path'):
                status_text.insert(tk.END, f"数据库路径: {db_manager.db_path}\n")

                # 尝试获取表信息
                try:
                    query = "SELECT name FROM sqlite_master WHERE type='table'"
                    tables = db_manager.fetch_all(query)
                    status_text.insert(tk.END, f"数据库表数量: {len(tables)}\n")
                    status_text.insert(tk.END, "表列表:\n")
                    for table in tables:
                        status_text.insert(tk.END, f"- {table['name']}\n")
                except Exception as e:
                    status_text.insert(tk.END, f"获取表信息失败: {e}\n")

        # 检查设备信息
        if 'AndroidDeviceController' in initialized_modules:
            device = initialized_modules['AndroidDeviceController']
            status_text.insert(tk.END, "\n设备信息:\n")
            if hasattr(device, 'is_initialized') and device.is_initialized:
                status_text.insert(tk.END, "设备已初始化\n")

                # 尝试获取设备信息
                try:
                    import subprocess
                    result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=False)
                    status_text.insert(tk.END, f"ADB设备列表:\n{result.stdout}\n")
                except Exception as e:
                    status_text.insert(tk.END, f"获取ADB设备信息失败: {e}\n")
            else:
                status_text.insert(tk.END, "设备未初始化\n")

        # 检查任务信息
        if 'TaskManager' in initialized_modules:
            task_manager = initialized_modules['TaskManager']
            status_text.insert(tk.END, "\n任务管理信息:\n")

            # 尝试获取任务列表
            try:
                if hasattr(task_manager, 'get_task_list'):
                    tasks = task_manager.get_task_list()
                    status_text.insert(tk.END, f"任务数量: {len(tasks)}\n")
                    status_text.insert(tk.END, "任务列表:\n")
                    for task in tasks:
                        task_id = task.get('task_id', 'unknown')
                        task_name = task.get('name', 'unknown')
                        status_text.insert(tk.END, f"- {task_name} (ID: {task_id})\n")
            except Exception as e:
                status_text.insert(tk.END, f"获取任务信息失败: {e}\n")

        self.update_status("系统状态检查完成")

    def reinitialize_system(self):
        """重新初始化系统"""
        if messagebox.askyesno("确认", "确定要重新初始化系统吗？这将关闭所有打开的调试面板。"):
            self.update_status("正在重新初始化系统...")

            # 清空已初始化的模块
            initialized_modules.clear()

            # 返回初始化选择界面
            self.back_to_init()

            self.update_status("系统已重置，请重新初始化")

    def view_system_logs(self):
        """查看系统日志"""
        self.update_status("正在打开系统日志查看器...")

        log_viewer = tk.Toplevel(self.root)
        log_viewer.title("系统日志查看器")
        log_viewer.geometry("1000x700")

        # 创建日志文件选择区域
        select_frame = ttk.Frame(log_viewer)
        select_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(select_frame, text="选择日志文件:").pack(side=tk.LEFT, padx=5)

        # 获取所有日志文件
        log_files = []
        try:
            for file in os.listdir(logs_dir):
                if file.endswith(".log"):
                    log_files.append(file)
        except:
            log_files = []

        # 添加系统默认日志
        system_logs = ['system.log', 'database.log', 'screen_recognizer.log', 'state_manager.log']
        for log in system_logs:
            log_path = os.path.join(project_root, log)
            if os.path.exists(log_path):
                log_files.append(log_path)

        # 创建下拉选择框
        self.log_file_var = tk.StringVar()
        log_combo = ttk.Combobox(select_frame, textvariable=self.log_file_var, width=50)
        log_combo['values'] = log_files
        if log_files:
            log_combo.current(0)
        log_combo.pack(side=tk.LEFT, padx=5)

        # 加载按钮
        ttk.Button(select_frame, text="加载",
                   command=lambda: self.load_log_file(self.log_file_var.get(), log_text)).pack(side=tk.LEFT, padx=5)

        # 刷新按钮
        ttk.Button(select_frame, text="刷新",
                   command=lambda: self.refresh_log_file(self.log_file_var.get(), log_text)).pack(side=tk.LEFT, padx=5)

        # 日志显示区域
        log_frame = ttk.Frame(log_viewer)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 文本区域和滚动条
        y_scroll = ttk.Scrollbar(log_frame)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        x_scroll = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        log_text = tk.Text(log_frame, wrap=tk.NONE, xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        log_text.pack(fill=tk.BOTH, expand=True)

        y_scroll.config(command=log_text.yview)
        x_scroll.config(command=log_text.xview)

        # 如果有选中的日志文件，自动加载
        if log_files:
            self.load_log_file(self.log_file_var.get(), log_text)

        self.update_status("系统日志查看器已打开")

    def install_dependencies(self):
        """安装必要的依赖"""
        self.update_status("正在检查并安装依赖...")

        try:
            import subprocess
            import sys

            # 检查和安装EasyOCR
            try:
                import easyocr
                self.update_status("EasyOCR已安装")
            except ImportError:
                self.update_status("正在安装EasyOCR...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "easyocr"])
                self.update_status("EasyOCR安装成功")

            # 检查其他依赖
            dependencies = ["numpy", "opencv-python", "pytesseract", "pillow"]
            for dep in dependencies:
                try:
                    __import__(dep.replace("-", "_"))
                except ImportError:
                    self.update_status(f"正在安装{dep}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                    self.update_status(f"{dep}安装成功")

            messagebox.showinfo("成功", "所有依赖已成功安装")

        except Exception as e:
            self.update_status(f"安装依赖失败: {e}")
            messagebox.showerror("错误", f"安装依赖失败: {str(e)}")

    def load_log_file(self, log_file, text_widget):
        """加载日志文件内容"""
        if not log_file:
            messagebox.showinfo("提示", "请选择要查看的日志文件")
            return

        # 确定日志文件路径
        log_path = log_file
        if not os.path.isabs(log_path):
            log_path = os.path.join(logs_dir, log_file)

        if not os.path.exists(log_path):
            # 尝试在项目根目录查找
            log_path = os.path.join(project_root, log_file)
            if not os.path.exists(log_path):
                messagebox.showerror("错误", f"日志文件不存在: {log_file}")
                return

        try:
            # 清除当前内容
            text_widget.delete(1.0, tk.END)

            # 加载日志文件
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                text_widget.insert(tk.END, content)

            # 滚动到底部
            text_widget.see(tk.END)

        except Exception as e:
            logger.error(f"加载日志文件时发生错误: {e}")
            messagebox.showerror("错误", f"加载日志文件失败: {str(e)}")

    def refresh_log_file(self, log_file, text_widget):
        """刷新日志文件内容"""
        self.load_log_file(log_file, text_widget)

    def run(self):
        """运行调试启动器"""
        self.root.mainloop()




if __name__ == "__main__":
    try:
        debug_launcher = DebugLauncher()
        debug_launcher.run()
    except Exception as e:
        logger.critical(f"启动调试系统时发生错误: {e}", exc_info=True)
        print(f"启动调试系统时发生错误: {e}")

        # 如果GUI启动失败，尝试输出更多诊断信息
        print("\n===== 系统诊断信息 =====")
        print(f"Python版本: {sys.version}")
        print(f"系统平台: {sys.platform}")
        print(f"项目根目录: {project_root}")

        # 检查必要的目录和文件
        components_dir = os.path.join(project_root, "components")
        if os.path.exists(components_dir):
            print(f"components 目录存在")
        else:
            print(f"components 目录不存在")

        device_controller_path = os.path.join(components_dir, "device_controller.py")
        if os.path.exists(device_controller_path):
            print(f"device_controller.py 文件存在")
        else:
            print(f"device_controller.py 文件不存在")

