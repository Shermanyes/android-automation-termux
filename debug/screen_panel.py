"""
屏幕面板调试模块
提供屏幕截取和区域选择功能
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='screen_panel_debug.log',
    filemode='w'
)
logger = logging.getLogger('ScreenPanel')

class ScreenPanel(ttk.Frame):
    """屏幕面板类，用于截取和显示屏幕"""

    def __init__(self, parent, device_controller, **kwargs):
        """
        初始化屏幕面板

        Args:
            parent: 父窗口
            device_controller: 设备控制器实例
        """
        super().__init__(parent, **kwargs)

        # 初始化变量
        self.device_controller = device_controller
        self.current_image = None
        self.current_tk_image = None
        self.roi_start = None
        self.roi_end = None
        self.roi_rectangle = None

        # 显式初始化设备控制器
        if not hasattr(self.device_controller, 'is_initialized') or not self.device_controller.is_initialized:
            logger.info("设备未初始化，尝试显式初始化")
            if hasattr(self.device_controller, 'initialize'):
                self.device_controller.initialize()
            else:
                logger.error("设备控制器没有initialize方法")

        # 再次检查设备是否初始化
        if hasattr(self.device_controller, 'is_initialized') and self.device_controller.is_initialized:
            logger.info("设备已初始化")
        else:
            logger.error("设备初始化失败")
            messagebox.showwarning("警告", "设备初始化失败，请使用设备诊断工具检查问题")

        # 创建UI
        self._create_ui()

        # 记录初始化日志
        logger.info("屏幕面板初始化完成")

    def _create_ui(self):
        """创建用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 截图按钮
        capture_btn = ttk.Button(main_frame, text="截取屏幕", command=self._capture_screen)
        capture_btn.pack(pady=10)

        # 加载图像按钮
        load_btn = ttk.Button(main_frame, text="加载图像", command=self._load_image)
        load_btn.pack(pady=10)

        # 添加重新初始化设备按钮
        reinit_btn = ttk.Button(main_frame, text="重新初始化设备", command=self._reinitialize_device)
        reinit_btn.pack(pady=10)

        # 画布区域
        self.canvas = tk.Canvas(main_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 绑定鼠标事件用于选择区域
        self.canvas.bind('<ButtonPress-1>', self._on_roi_start)
        self.canvas.bind('<B1-Motion>', self._on_roi_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_roi_end)

        # 显示初始状态信息
        self._show_status()

    def _show_status(self):
        """在画布上显示设备状态信息"""
        self.canvas.delete("all")

        # 检查设备状态
        if hasattr(self.device_controller, 'is_initialized') and self.device_controller.is_initialized:
            status_text = "设备已连接和初始化\n点击「截取屏幕」按钮获取屏幕图像"
            status_color = "green"
        else:
            status_text = "设备未初始化\n请点击「重新初始化设备」按钮"
            status_color = "red"

        # 显示状态文本
        self.canvas.create_text(
            self.canvas.winfo_width() // 2 or 300,
            self.canvas.winfo_height() // 2 or 200,
            text=status_text,
            fill=status_color,
            font=("Arial", 14),
            justify=tk.CENTER
        )

    def _reinitialize_device(self):
        """重新初始化设备控制器"""
        try:
            logger.info("尝试重新初始化设备")

            if hasattr(self.device_controller, 'initialize'):
                success = self.device_controller.initialize()
                if success:
                    logger.info("设备重新初始化成功")
                    messagebox.showinfo("成功", "设备已成功初始化")
                else:
                    logger.error("设备重新初始化失败")
                    messagebox.showerror("错误", "设备初始化失败")
            else:
                logger.error("设备控制器没有initialize方法")
                messagebox.showerror("错误", "设备控制器不支持手动初始化")

            # 更新状态显示
            self._show_status()

        except Exception as e:
            logger.exception(f"重新初始化设备时发生错误: {e}")
            messagebox.showerror("错误", f"初始化设备失败: {e}")

    def _capture_screen(self):
        """截取屏幕"""
        try:
            # 检查设备是否初始化
            if not hasattr(self.device_controller, 'is_initialized') or not self.device_controller.is_initialized:
                logger.error("设备未初始化")

                # 尝试自动初始化设备
                if hasattr(self.device_controller, 'initialize'):
                    logger.info("尝试自动初始化设备")
                    if self.device_controller.initialize():
                        logger.info("设备初始化成功")
                    else:
                        logger.error("设备初始化失败")
                        messagebox.showerror("错误", "设备初始化失败，请检查设备连接")
                        return
                else:
                    messagebox.showerror("错误", "设备未初始化，请检查设备连接")
                    return

            logger.info("开始截取屏幕")

            # 使用设备控制器截图
            screenshot = self.device_controller.take_screenshot()

            if screenshot is None:
                logger.error("截图失败")
                messagebox.showerror("错误", "截图失败")
                return

            # 显示截图
            self._display_image(screenshot)

            logger.info("屏幕截图成功")

        except Exception as e:
            logger.exception(f"截取屏幕时发生错误: {e}")
            messagebox.showerror("错误", f"截取屏幕失败: {e}")

    def _load_image(self):
        """从文件加载图像"""
        try:
            # 打开文件选择对话框
            file_path = filedialog.askopenfilename(
                title="选择图像文件",
                filetypes=[("图像文件", "*.png *.jpg *.jpeg *.bmp")]
            )

            if not file_path:
                return

            # 加载图像
            image = Image.open(file_path)

            # 显示图像
            self._display_image(image)

            logger.info(f"成功加载图像: {file_path}")

        except Exception as e:
            logger.exception(f"加载图像时发生错误: {e}")
            messagebox.showerror("错误", f"加载图像失败: {e}")

    def _display_image(self, image):
        """在画布上显示图像"""
        # 调整图像大小以适应画布
        canvas_width = self.canvas.winfo_width() or 600
        canvas_height = self.canvas.winfo_height() or 400

        # 计算缩放比例
        width_ratio = canvas_width / image.width
        height_ratio = canvas_height / image.height
        scale_ratio = min(width_ratio, height_ratio)

        # 缩放图像
        if scale_ratio < 1:
            new_width = int(image.width * scale_ratio)
            new_height = int(image.height * scale_ratio)
            image = image.resize((new_width, new_height), Image.LANCZOS)

        # 转换为Tkinter图像
        self.current_tk_image = ImageTk.PhotoImage(image)
        self.current_image = image

        # 清除画布并显示图像
        self.canvas.delete("all")
        self.canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image=self.current_tk_image
        )

        # 重置ROI选择
        self.roi_start = None
        self.roi_end = None
        self.roi_rectangle = None

    def _on_roi_start(self, event):
        """开始选择区域"""
        self.roi_start = (event.x, event.y)
        self.roi_end = None

        # 删除之前的选择区域
        if self.roi_rectangle:
            self.canvas.delete(self.roi_rectangle)

    def _on_roi_drag(self, event):
        """拖动选择区域"""
        if self.roi_start:
            # 删除之前的选择区域
            if self.roi_rectangle:
                self.canvas.delete(self.roi_rectangle)

            # 绘制新的选择区域
            self.roi_rectangle = self.canvas.create_rectangle(
                self.roi_start[0], self.roi_start[1],
                event.x, event.y,
                outline='red', width=2
            )

    def _on_roi_end(self, event):
        """结束选择区域"""
        if self.roi_start:
            self.roi_end = (event.x, event.y)

    def get_current_image(self):
        """获取当前图像"""
        if self.current_image is None:
            logger.warning("当前没有图像")
        return self.current_image

    def get_selected_roi(self):
        """获取选择的区域"""
        if not self.roi_start or not self.roi_end:
            logger.warning("没有选择区域")
            return None

        # 确保坐标是左上和右下
        x1 = min(self.roi_start[0], self.roi_end[0])
        y1 = min(self.roi_start[1], self.roi_end[1])
        x2 = max(self.roi_start[0], self.roi_end[0])
        y2 = max(self.roi_start[1], self.roi_end[1])

        return (x1, y1, x2, y2)