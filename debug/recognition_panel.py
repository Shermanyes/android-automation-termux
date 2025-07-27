"""
识别测试面板
提供图像和文本识别的测试功能
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import cv2
import time


from .utils import pil_to_tk, draw_match_result, generate_timestamp_filename

class RecognitionPanel(ttk.Frame):
    """识别功能测试面板"""
    
    def __init__(self, parent, screen_recognizer, screen_panel, **kwargs):
        """初始化识别面板
        
        Args:
            parent: 父窗口
            screen_recognizer: 屏幕识别器实例
            screen_panel: 屏幕面板实例，用于获取图像和ROI
        """
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.recognizer = screen_recognizer
        self.screen_panel = screen_panel
        
        self.test_image = None  # 测试用图像
        self.result_image = None  # 结果图像
        
        self._setup_ui()

    def _setup_ui(self):
        """设置UI组件"""
        # 主分区
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧控制面板
        control_frame = ttk.Frame(main_paned)
        main_paned.add(control_frame, weight=1)

        # 图像识别控制区
        image_recognition_frame = ttk.LabelFrame(control_frame, text="图像识别")
        image_recognition_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(image_recognition_frame, text="模板图像:").pack(anchor=tk.W, padx=5, pady=2)

        template_frame = ttk.Frame(image_recognition_frame)
        template_frame.pack(fill=tk.X, padx=5, pady=2)

        self.template_path_var = tk.StringVar()
        ttk.Entry(template_frame, textvariable=self.template_path_var, width=30).pack(side=tk.LEFT, fill=tk.X,
                                                                                      expand=True)

        ttk.Button(template_frame, text="浏览", command=self.browse_template).pack(side=tk.LEFT, padx=2)

        ttk.Label(image_recognition_frame, text="匹配阈值:").pack(anchor=tk.W, padx=5, pady=2)

        threshold_frame = ttk.Frame(image_recognition_frame)
        threshold_frame.pack(fill=tk.X, padx=5, pady=2)

        self.threshold_var = tk.DoubleVar(value=0.8)
        ttk.Scale(threshold_frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL,
                  variable=self.threshold_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        threshold_label = ttk.Label(threshold_frame, text="0.80")
        threshold_label.pack(side=tk.LEFT, padx=5)

        # 更新阈值标签
        def update_threshold_label(*args):
            threshold_label.config(text=f"{self.threshold_var.get():.2f}")

        self.threshold_var.trace_add("write", update_threshold_label)

        # ROI设置
        roi_frame = ttk.Frame(image_recognition_frame)
        roi_frame.pack(fill=tk.X, padx=5, pady=2)

        self.use_roi_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(roi_frame, text="使用选定区域", variable=self.use_roi_var).pack(side=tk.LEFT)

        ttk.Button(image_recognition_frame, text="执行图像匹配",
                   command=self.run_image_recognition).pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(image_recognition_frame, text="图像识别调试",
                   command=self.debug_image_recognition).pack(fill=tk.X, padx=5, pady=5)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)

        # 文本识别控制区
        text_recognition_frame = ttk.LabelFrame(control_frame, text="文本识别")
        text_recognition_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(text_recognition_frame, text="查找文本:").pack(anchor=tk.W, padx=5, pady=2)

        self.target_text_var = tk.StringVar()
        ttk.Entry(text_recognition_frame, textvariable=self.target_text_var).pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(text_recognition_frame, text="OCR语言:").pack(anchor=tk.W, padx=5, pady=2)

        self.lang_var = tk.StringVar(value="chi_sim+eng")
        ttk.Combobox(text_recognition_frame, textvariable=self.lang_var,
                     values=["chi_sim", "eng", "chi_sim+eng"]).pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(text_recognition_frame, text="匹配阈值:").pack(anchor=tk.W, padx=5, pady=2)

        text_threshold_frame = ttk.Frame(text_recognition_frame)
        text_threshold_frame.pack(fill=tk.X, padx=5, pady=2)

        self.text_threshold_var = tk.DoubleVar(value=0.6)
        ttk.Scale(text_threshold_frame, from_=0.1, to=1.0, orient=tk.HORIZONTAL,
                  variable=self.text_threshold_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        text_threshold_label = ttk.Label(text_threshold_frame, text="0.60")
        text_threshold_label.pack(side=tk.LEFT, padx=5)

        # 更新文本阈值标签
        def update_text_threshold_label(*args):
            text_threshold_label.config(text=f"{self.text_threshold_var.get():.2f}")

        self.text_threshold_var.trace_add("write", update_text_threshold_label)

        # 文本识别按钮
        ttk.Button(text_recognition_frame, text="查找文本",
                   command=self.run_text_recognition).pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(text_recognition_frame, text="获取全部文本",
                   command=self.get_all_text).pack(fill=tk.X, padx=5, pady=5)

        # 添加直接EasyOCR调试按钮
        ttk.Button(text_recognition_frame, text="直接EasyOCR调试",
                   command=self.debug_text_recognition).pack(fill=tk.X, padx=5, pady=5)

        ttk.Separator(control_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)

        # 结果保存
        result_frame = ttk.Frame(control_frame)
        result_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(result_frame, text="保存结果图像",
                   command=self.save_result_image).pack(fill=tk.X, pady=2)

        ttk.Button(result_frame, text="保存识别配置",
                   command=self.save_recognition_config).pack(fill=tk.X, pady=2)

        # 右侧结果显示区域
        result_frame = ttk.Frame(main_paned)
        main_paned.add(result_frame, weight=3)

        # 上方图像显示
        image_frame = ttk.LabelFrame(result_frame, text="识别结果")
        image_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.result_canvas = tk.Canvas(image_frame, bg="black")
        self.result_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 下方文本结果
        text_result_frame = ttk.LabelFrame(result_frame, text="文本结果")
        text_result_frame.pack(fill=tk.X, padx=5, pady=5)

        # 文本滚动区域
        text_scroll = ttk.Scrollbar(text_result_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.result_text = tk.Text(text_result_frame, height=10, wrap=tk.WORD,
                                   yscrollcommand=text_scroll.set)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        text_scroll.config(command=self.result_text.yview)

        # 显示初始信息
        self.show_info("请从屏幕面板获取截图，然后进行识别测试")
    
    def browse_template(self):
        """浏览选择模板图像"""
        filepath = filedialog.askopenfilename(
            title="选择模板图像",
            filetypes=[("图像文件", "*.png *.jpg *.jpeg *.bmp")]
        )
        
        if filepath:
            self.template_path_var.set(filepath)
    
    def show_info(self, message):
        """在结果区域显示信息"""
        # 清除画布
        self.result_canvas.delete("all")
        self.result_canvas.create_text(
            self.result_canvas.winfo_width() // 2 or 200,
            self.result_canvas.winfo_height() // 2 or 150,
            text=message,
            fill="white",
            font=("Arial", 12)
        )
        
        # 清除文本
        self.result_text.delete(1.0, tk.END)

    def run_text_recognition(self):
        """执行文本识别"""
        try:
            # 添加详细日志
            print("=== 开始文本识别 ===")

            # 显示加载消息
            self.show_info("正在获取最新截图...")
            self.update()  # 强制更新UI

            # 直接从设备获取新鲜截图
            if hasattr(self.screen_panel, 'device_controller'):
                print("使用设备控制器获取截图")
                screenshot = self.screen_panel.device_controller.take_screenshot()
                if screenshot:
                    print(f"获取到截图，尺寸：{screenshot.size}")
                    self.screen_panel._display_image(screenshot)
                    self.update()
                else:
                    print("设备控制器未返回截图")

            # 获取当前图像
            image = self.screen_panel.get_current_image()
            if image is None:
                print("当前图像为空")
                messagebox.showinfo("提示", "请先在屏幕面板获取截图")
                return

            print(f"当前图像尺寸：{image.size}")

            # 获取查找文本和参数
            target_text = self.target_text_var.get()
            if not target_text:
                messagebox.showinfo("提示", "请输入要查找的文本")
                return
            print(f"目标文本：'{target_text}'")

            # 获取ROI
            roi = None
            if self.use_roi_var.get():
                roi = self.screen_panel.get_selected_roi()
                if not roi:
                    messagebox.showinfo("提示", "请在屏幕面板选择区域")
                    return

            # 获取阈值
            threshold = self.text_threshold_var.get()
            print(f"使用阈值：{threshold}")

            # 显示加载消息
            self.show_info("正在识别文本...")
            self.update()  # 强制更新UI

            # 创建调试目录
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            os.makedirs(debug_dir, exist_ok=True)

            # 保存当前图像用于调试
            image_path = os.path.join(debug_dir, 'panel_image.png')
            image.save(image_path)

            # 执行识别
            lang = self.lang_var.get()
            threshold = self.text_threshold_var.get()

            # 添加直接调用EasyOCR的代码
            try:
                import easyocr
                import numpy as np
                import cv2

                # 初始化EasyOCR
                reader = easyocr.Reader(['ch_sim', 'en'])

                # 转换图像
                image_np = np.array(image)
                if roi:
                    x1, y1, x2, y2 = roi
                    image_np = image_np[y1:y2, x1:x2]

                # BGR转换
                if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                    image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
                else:
                    image_bgr = image_np

                # 执行识别
                self.result_text.delete(1.0, tk.END)
                self.result_text.insert(tk.END, "使用EasyOCR直接识别中...\n\n")
                self.update()

                results = reader.readtext(image_bgr)

                # 显示结果
                self.result_text.insert(tk.END, f"识别到 {len(results)} 个文本区域:\n\n")

                # 创建可视化图像
                visual_img = image_bgr.copy()
                found = False
                result = None

                for i, (bbox, detected_text, confidence) in enumerate(results):
                    self.result_text.insert(tk.END, f"{i + 1}. '{detected_text}' (置信度: {confidence:.2f})\n")

                    # 绘制边界框
                    pts = np.array(bbox, np.int32).reshape((-1, 1, 2))
                    color = (0, 255, 0)  # 默认绿色

                    # 检查是否匹配目标文本
                    if target_text.lower() in detected_text.lower():
                        self.result_text.insert(tk.END, f"  ✓ 包含目标文本 '{target_text}'\n")
                        color = (0, 0, 255)  # 红色表示匹配
                        found = True

                        # 找到匹配结果
                        x_min = min(point[0] for point in bbox)
                        y_min = min(point[1] for point in bbox)
                        x_max = max(point[0] for point in bbox)
                        y_max = max(point[1] for point in bbox)

                        width = x_max - x_min
                        height = y_max - y_min

                        # 调整坐标
                        if roi:
                            x_min += roi[0]
                            y_min += roi[1]

                        result = (int(x_min), int(y_min), int(width), int(height))

                    cv2.polylines(visual_img, [pts], True, color, 2)

                    # 添加文本
                    x_min = min(point[0] for point in bbox)
                    y_min = min(point[1] for point in bbox)
                    cv2.putText(
                        visual_img,
                        f"{detected_text[:10]}.. ({confidence:.2f})",
                        (int(x_min), int(y_min) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )

                # 保存可视化结果
                visual_path = os.path.join(debug_dir, 'panel_ocr_results.png')
                cv2.imwrite(visual_path, visual_img)

                if found:
                    self.result_text.insert(tk.END, f"\n找到目标文本: '{target_text}'\n")
                    self.result_text.insert(tk.END, f"结果坐标: {result}\n")

                    # 在图像上标记结果
                    from PIL import ImageDraw
                    result_image = image.copy()
                    if result:
                        x, y, w, h = result
                        draw = ImageDraw.Draw(result_image)
                        draw.rectangle([(x, y), (x + w, y + h)], outline="blue", width=2)
                        draw.text((x, y - 20), target_text, fill="blue")

                    # 显示结果图像
                    self.display_result(result_image,
                                        f"找到文本: '{target_text}'\n位置=({result[0]}, {result[1]}), 尺寸={result[2]}x{result[3]}")

                    # 保存结果图像
                    self.result_image = result_image
                else:
                    self.result_text.insert(tk.END, f"\n未找到目标文本: '{target_text}'\n")
                    self.result_text.insert(tk.END, f"识别结果图像已保存到: {visual_path}")

                    # 显示原始图像
                    self.display_result(image, f"未找到文本: '{target_text}' (阈值={threshold:.2f})")
                    self.result_image = image

                # 添加查看按钮
                if not hasattr(self, 'view_btn'):
                    self.view_btn = ttk.Button(
                        self.result_text.master,
                        text="查看识别结果图像",
                        command=lambda: os.startfile(visual_path) if os.path.exists(visual_path) else None
                    )
                    self.view_btn.pack(after=self.result_text, pady=5)

            except Exception as e:
                self.result_text.insert(tk.END, f"直接识别失败: {str(e)}")
                import traceback
                self.result_text.insert(tk.END, f"\n\n{traceback.format_exc()}")

            # 正常的识别流程继续
            self.result_text.insert(tk.END, "\n\n通过ScreenRecognizer识别:\n")

            result = self.recognizer.find_text(target_text, lang, None, roi, threshold)

            if result:
                x, y, w, h = result
                self.result_text.insert(tk.END, f"找到匹配: ({x}, {y}, {w}, {h})")
            else:
                self.result_text.insert(tk.END, "未找到匹配")

        except Exception as e:
            messagebox.showerror("错误", f"文本识别过程出错: {str(e)}")
            import traceback
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, traceback.format_exc())

    def run_text_recognition(self):
        """执行文本识别"""
        try:
            # 添加详细日志
            print("=== 开始文本识别 ===")

            # 显示加载消息
            self.show_info("正在获取最新截图...")
            self.update()  # 强制更新UI

            # 直接从设备获取新鲜截图
            if hasattr(self.screen_panel, 'device_controller'):
                print("使用设备控制器获取截图")
                screenshot = self.screen_panel.device_controller.take_screenshot()
                if screenshot:
                    print(f"获取到截图，尺寸：{screenshot.size}")
                    self.screen_panel._display_image(screenshot)
                    self.update()
                else:
                    print("设备控制器未返回截图")

            # 获取当前图像
            image = self.screen_panel.get_current_image()
            if image is None:
                print("当前图像为空")
                messagebox.showinfo("提示", "请先在屏幕面板获取截图")
                return

            print(f"当前图像尺寸：{image.size}")

            # 获取查找文本和参数
            target_text = self.target_text_var.get()
            if not target_text:
                messagebox.showinfo("提示", "请输入要查找的文本")
                return
            print(f"目标文本：'{target_text}'")

            # 获取阈值
            lang = self.lang_var.get()
            threshold = self.text_threshold_var.get()
            print(f"使用阈值：{threshold}")

            # 调用识别器前后记录
            print("开始调用ScreenRecognizer")
            result = self.recognizer.find_text(target_text, lang, None, roi, threshold)
            print(f"ScreenRecognizer返回结果：{result}")

            # 获取ROI
            roi = None
            if self.use_roi_var.get():
                roi = self.screen_panel.get_selected_roi()
                if not roi:
                    messagebox.showinfo("提示", "请在屏幕面板选择区域")
                    return

            # 显示加载消息
            self.show_info("正在识别文本...")
            self.update()  # 强制更新UI

            # 创建调试目录
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            os.makedirs(debug_dir, exist_ok=True)

            # 保存当前图像用于调试
            image_path = os.path.join(debug_dir, 'panel_image.png')
            image.save(image_path)

            # 执行识别
            lang = self.lang_var.get()
            threshold = self.text_threshold_var.get()

            # 添加直接调用EasyOCR的代码
            try:
                import easyocr
                import numpy as np
                import cv2

                # 初始化EasyOCR
                reader = easyocr.Reader(['ch_sim', 'en'])

                # 转换图像
                image_np = np.array(image)
                if roi:
                    x1, y1, x2, y2 = roi
                    image_np = image_np[y1:y2, x1:x2]

                # BGR转换
                if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                    image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
                else:
                    image_bgr = image_np

                # 执行识别
                self.result_text.delete(1.0, tk.END)
                self.result_text.insert(tk.END, "使用EasyOCR直接识别中...\n\n")
                self.update()

                results = reader.readtext(image_bgr)

                # 显示结果
                self.result_text.insert(tk.END, f"识别到 {len(results)} 个文本区域:\n\n")

                # 创建可视化图像
                visual_img = image_bgr.copy()
                found = False
                result = None

                for i, (bbox, detected_text, confidence) in enumerate(results):
                    self.result_text.insert(tk.END, f"{i + 1}. '{detected_text}' (置信度: {confidence:.2f})\n")

                    # 绘制边界框
                    pts = np.array(bbox, np.int32).reshape((-1, 1, 2))
                    color = (0, 255, 0)  # 默认绿色

                    # 检查是否匹配目标文本
                    if target_text.lower() in detected_text.lower():
                        self.result_text.insert(tk.END, f"  ✓ 包含目标文本 '{target_text}'\n")
                        color = (0, 0, 255)  # 红色表示匹配
                        found = True

                        # 找到匹配结果
                        x_min = min(point[0] for point in bbox)
                        y_min = min(point[1] for point in bbox)
                        x_max = max(point[0] for point in bbox)
                        y_max = max(point[1] for point in bbox)

                        width = x_max - x_min
                        height = y_max - y_min

                        # 调整坐标
                        if roi:
                            x_min += roi[0]
                            y_min += roi[1]

                        result = (int(x_min), int(y_min), int(width), int(height))

                    cv2.polylines(visual_img, [pts], True, color, 2)

                    # 添加文本
                    x_min = min(point[0] for point in bbox)
                    y_min = min(point[1] for point in bbox)
                    cv2.putText(
                        visual_img,
                        f"{detected_text[:10]}.. ({confidence:.2f})",
                        (int(x_min), int(y_min) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )

                # 保存可视化结果
                visual_path = os.path.join(debug_dir, 'panel_ocr_results.png')
                cv2.imwrite(visual_path, visual_img)

                if found:
                    self.result_text.insert(tk.END, f"\n找到目标文本: '{target_text}'\n")
                    self.result_text.insert(tk.END, f"结果坐标: {result}\n")

                    # 在图像上标记结果
                    result_image = image.copy()
                    if result:
                        x, y, w, h = result
                        draw = ImageDraw.Draw(result_image)
                        draw.rectangle([(x, y), (x + w, y + h)], outline="blue", width=2)
                        draw.text((x, y - 20), target_text, fill="blue")

                    # 显示结果图像
                    self.display_result(result_image,
                                        f"找到文本: '{target_text}'\n位置=({result[0]}, {result[1]}), 尺寸={result[2]}x{result[3]}")

                    # 保存结果图像
                    self.result_image = result_image
                else:
                    self.result_text.insert(tk.END, f"\n未找到目标文本: '{target_text}'\n")
                    self.result_text.insert(tk.END, f"识别结果图像已保存到: {visual_path}")

                    # 显示原始图像
                    self.display_result(image, f"未找到文本: '{target_text}' (阈值={threshold:.2f})")
                    self.result_image = image

                # 添加查看按钮
                if not hasattr(self, 'view_btn'):
                    self.view_btn = ttk.Button(
                        self.result_text.master,
                        text="查看识别结果图像",
                        command=lambda: os.startfile(visual_path) if os.path.exists(visual_path) else None
                    )
                    self.view_btn.pack(after=self.result_text, pady=5)

            except Exception as e:
                self.result_text.insert(tk.END, f"直接识别失败: {str(e)}")
                import traceback
                self.result_text.insert(tk.END, f"\n\n{traceback.format_exc()}")

            # 正常的识别流程继续
            self.result_text.insert(tk.END, "\n\n通过ScreenRecognizer识别:\n")

            result = self.recognizer.find_text(target_text, lang, None, roi, threshold)

            if result:
                x, y, w, h = result
                self.result_text.insert(tk.END, f"找到匹配: ({x}, {y}, {w}, {h})")
            else:
                self.result_text.insert(tk.END, "未找到匹配")

        except Exception as e:
            messagebox.showerror("错误", f"文本识别过程出错: {str(e)}")
            import traceback
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, traceback.format_exc())

    def show_debug_images(self):
        """显示调试图像"""
        try:
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            if not os.path.exists(debug_dir):
                messagebox.showinfo("提示", "没有可用的调试图像")
                return

            # 创建调试图像查看窗口
            debug_window = tk.Toplevel(self.parent)
            debug_window.title("识别调试图像")
            debug_window.geometry("800x600")

            # 创建选项卡
            notebook = ttk.Notebook(debug_window)
            notebook.pack(fill=tk.BOTH, expand=True)

            # 查找预处理图像
            preprocess_methods = ["原图", "灰度图", "增强对比度", "自适应二值化"]

            for method in preprocess_methods:
                img_path = os.path.join(debug_dir, f"{method}.png")
                if os.path.exists(img_path):
                    # 创建标签页
                    tab = ttk.Frame(notebook)
                    notebook.add(tab, text=method)

                    # 加载图像
                    image = Image.open(img_path)

                    # 调整图像大小
                    canvas_width = 780
                    canvas_height = 550

                    # 计算缩放比例
                    width_ratio = canvas_width / image.width
                    height_ratio = canvas_height / image.height
                    scale_ratio = min(width_ratio, height_ratio)

                    if scale_ratio < 1:
                        new_width = int(image.width * scale_ratio)
                        new_height = int(image.height * scale_ratio)
                        image = image.resize((new_width, new_height), Image.LANCZOS)

                    # 显示图像
                    photo = ImageTk.PhotoImage(image)

                    canvas = tk.Canvas(tab, width=canvas_width, height=canvas_height)
                    canvas.pack(fill=tk.BOTH, expand=True)

                    canvas.create_image(canvas_width // 2, canvas_height // 2, image=photo)
                    canvas.image = photo  # 保持引用

                    # 显示当前识别参数
                    if hasattr(self, 'current_params'):
                        param_text = (f"目标文本: {self.current_params['text']}\n"
                                      f"语言: {self.current_params['lang']}\n"
                                      f"阈值: {self.current_params['threshold']}\n"
                                      f"ROI: {self.current_params['roi']}")

                        ttk.Label(tab, text=param_text).pack(side=tk.BOTTOM, pady=10)

            if notebook.tabs():
                messageLabel = ttk.Label(debug_window, text="点击标签查看不同预处理方法的结果图像")
                messageLabel.pack(side=tk.TOP, pady=5)
            else:
                messageLabel = ttk.Label(debug_window, text="没有可用的预处理图像")
                messageLabel.pack(pady=20)

        except Exception as e:
            messagebox.showerror("错误", f"显示调试图像失败: {str(e)}")

    def show_recognition_log(self):
        """显示识别日志"""
        try:
            log_path = "screen_recognizer.log"

            # 创建日志查看窗口
            log_window = tk.Toplevel(self.parent)
            log_window.title("文本识别日志")
            log_window.geometry("800x600")

            # 创建文本显示区域和滚动条
            y_scroll = ttk.Scrollbar(log_window)
            y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            log_text = tk.Text(log_window, wrap=tk.WORD, yscrollcommand=y_scroll.set)
            log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            y_scroll.config(command=log_text.yview)

            # 读取日志文件
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    log_content = f.read()

                    # 过滤出与当前目标文本相关的日志
                    target_text = self.target_text_var.get()
                    log_sections = log_content.split("======= 开始寻找文本:")

                    relevant_logs = ""
                    for section in log_sections:
                        if f"'{target_text}'" in section:
                            relevant_logs += "======= 开始寻找文本:" + section

                    if relevant_logs:
                        log_text.insert(tk.END, relevant_logs)
                    else:
                        log_text.insert(tk.END, "未找到与当前文本匹配的日志记录")

                    # 滚动到最新内容
                    log_text.see(tk.END)
            else:
                log_text.insert(tk.END, f"找不到日志文件: {log_path}")

        except Exception as e:
            messagebox.showerror("错误", f"显示日志失败: {str(e)}")

    def show_detailed_debug_info(self, debug_results):
        """显示详细的调试信息"""
        # 创建调试信息窗口
        debug_window = tk.Toplevel(self.parent)
        debug_window.title("识别调试详情")
        debug_window.geometry("800x600")

        # 创建选项卡
        notebook = ttk.Notebook(debug_window)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 结果概览选项卡
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="结果概览")

        # 创建结果概览
        overview_text = tk.Text(overview_frame, wrap=tk.WORD)
        overview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加目标信息
        overview_text.insert(tk.END, f"目标文本: {debug_results.get('target_text', '')}\n")
        overview_text.insert(tk.END, f"匹配阈值: {debug_results.get('threshold', 0)}\n\n")

        # 添加详细结果信息
        overview_text.insert(tk.END, "识别结果:\n")

        results = debug_results.get("results", [])
        if results:
            for i, result in enumerate(results):
                overview_text.insert(tk.END, f"\n结果 {i + 1}:\n")
                overview_text.insert(tk.END, f"- 方法: {result.get('method', 'unknown')}\n")
                overview_text.insert(tk.END, f"- 检测文本: {result.get('detected_text', '')}\n")
                overview_text.insert(tk.END, f"- 置信度: {result.get('confidence', 'N/A')}\n")

                if 'bbox' in result:
                    bbox = result['bbox']
                    if isinstance(bbox, list) and len(bbox) == 4:  # EasyOCR格式
                        overview_text.insert(tk.END, f"- 边界框: 多边形 {bbox}\n")
                    elif isinstance(bbox, tuple) and len(bbox) == 4:  # (x,y,w,h) 格式
                        overview_text.insert(tk.END, f"- 边界框: x={bbox[0]}, y={bbox[1]}, w={bbox[2]}, h={bbox[3]}\n")
        else:
            overview_text.insert(tk.END, "未找到匹配结果\n")

        # 可视化选项卡
        if hasattr(self.recognizer, "visualize_results"):
            visual_frame = ttk.Frame(notebook)
            notebook.add(visual_frame, text="可视化")

            # 创建画布
            canvas = tk.Canvas(visual_frame)
            canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # 生成可视化图像
            visualized_image = self.recognizer.visualize_results()
            if visualized_image is not None:
                # 转换为PIL图像
                pil_image = Image.fromarray(visualized_image)

                # 调整大小以适应画布
                canvas_width = 780
                canvas_height = 550

                # 计算缩放比例
                width_ratio = canvas_width / pil_image.width
                height_ratio = canvas_height / pil_image.height
                scale_ratio = min(width_ratio, height_ratio)

                if scale_ratio < 1:
                    new_width = int(pil_image.width * scale_ratio)
                    new_height = int(pil_image.height * scale_ratio)
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

                # 显示图像
                tk_image = ImageTk.PhotoImage(pil_image)
                canvas.create_image(canvas_width // 2, canvas_height // 2, image=tk_image)
                canvas.image = tk_image  # 保持引用

        # 原始数据选项卡
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="原始数据")

        # 创建文本区域和滚动条
        scroll = ttk.Scrollbar(data_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        data_text = tk.Text(data_frame, wrap=tk.WORD, yscrollcommand=scroll.set)
        data_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scroll.config(command=data_text.yview)

        # 添加原始调试数据的JSON表示
        import json
        # 过滤掉图像数据以避免显示过大
        filtered_results = {k: v for k, v in debug_results.items() if k not in ['original_image']}

        try:
            data_text.insert(tk.END, json.dumps(filtered_results, indent=4, default=str))
        except:
            data_text.insert(tk.END, "无法显示完整调试数据")
    
    def get_all_text(self):
        """获取全部文本"""
        # 获取当前图像
        image = self.screen_panel.get_current_image()
        if image is None:
            messagebox.showinfo("提示", "请先在屏幕面板获取截图")
            return
        
        # 获取ROI
        roi = None
        if self.use_roi_var.get():
            roi = self.screen_panel.get_selected_roi()
        
        try:
            # 显示加载消息
            self.show_info("正在识别所有文本...")
            self.update()  # 强制更新UI
            
            # 执行识别
            lang = self.lang_var.get()
            
            # 如果有ROI，先裁剪图像
            if roi:
                image_for_ocr = image.crop(roi)
            else:
                image_for_ocr = image
            
            # 全局文本识别
            all_text = self.recognizer.get_screen_text(lang)
            
            # 显示结果
            self.display_result(image, all_text)
            
        except Exception as e:
            messagebox.showerror("错误", f"文本识别过程出错: {str(e)}")
    
    def display_result(self, image, text):
        """显示识别结果
        
        Args:
            image: 结果图像
            text: 结果文本
        """
        # 调整图像大小适应画布
        canvas_width = self.result_canvas.winfo_width()
        canvas_height = self.result_canvas.winfo_height()
        
        if canvas_width <= 1:  # 窗口还未完全初始化
            canvas_width = 600
            canvas_height = 400
        
        # 计算缩放比例
        width_ratio = canvas_width / image.width
        height_ratio = canvas_height / image.height
        scale_ratio = min(width_ratio, height_ratio)
        
        if scale_ratio < 1:
            new_width = int(image.width * scale_ratio)
            new_height = int(image.height * scale_ratio)
            image_display = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            image_display = image
        
        # 转换为Tkinter格式
        self.result_image_tk = ImageTk.PhotoImage(image_display)
        
        # 清除画布并显示新图像
        self.result_canvas.delete("all")
        self.result_canvas.create_image(
            canvas_width // 2, 
            canvas_height // 2,
            image=self.result_image_tk
        )
        
        # 显示文本结果
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, text)
    
    def save_result_image(self):
        """保存结果图像"""
        if self.result_image is None:
            messagebox.showinfo("提示", "没有可保存的结果图像")
            return
            
        try:
            # 创建保存目录
            save_dir = "recognition_results"
            os.makedirs(save_dir, exist_ok=True)
            
            # 生成文件名
            filename = generate_timestamp_filename("recognition", "png")
            filepath = os.path.join(save_dir, filename)
            
            # 保存图像
            self.result_image.save(filepath)
            messagebox.showinfo("成功", f"结果图像已保存到: {filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"保存结果图像失败: {str(e)}")
    
    def save_recognition_config(self):
        """保存识别配置"""
        # 确定要保存的配置类型
        if self.template_path_var.get():
            config_type = "image"
        elif self.target_text_var.get():
            config_type = "text"
        else:
            messagebox.showinfo("提示", "请先设置识别参数")
            return
        
        try:
            # 创建保存目录
            save_dir = "recognition_configs"
            os.makedirs(save_dir, exist_ok=True)
            
            # 构建配置数据
            config = {
                "type": config_type,
                "name": f"{config_type}_recognition_{int(time.time())}"
            }
            
            if config_type == "image":
                config.update({
                    "template_path": self.template_path_var.get(),
                    "threshold": self.threshold_var.get()
                })
            else:
                config.update({
                    "target_text": self.target_text_var.get(),
                    "lang": self.lang_var.get(),
                    "threshold": self.text_threshold_var.get()
                })
            
            # 添加ROI信息
            if self.use_roi_var.get() and self.screen_panel.get_selected_roi():
                config["roi"] = self.screen_panel.get_selected_roi()
            
            # 生成文件名
            filename = generate_timestamp_filename(f"{config_type}_config", "json")
            filepath = os.path.join(save_dir, filename)
            
            # 保存配置
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
                
            messagebox.showinfo("成功", f"识别配置已保存到: {filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"保存识别配置失败: {str(e)}")

    def debug_image_recognition(self):
        """调试图像识别问题"""
        try:
            # 创建调试目录
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            os.makedirs(debug_dir, exist_ok=True)

            # 获取当前图像
            current_image = self.screen_panel.get_current_image()
            if current_image is None:
                messagebox.showinfo("提示", "请先在屏幕面板获取截图")
                return

            # 获取目标文本
            target_text = self.target_text_var.get() or "斗地主"  # 默认值

            # 创建调试窗口
            debug_window = tk.Toplevel(self.parent)
            debug_window.title("图像识别调试器")
            debug_window.geometry("800x700")

            # 创建文本区域
            debug_text = tk.Text(debug_window, wrap=tk.WORD)
            debug_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # 1. 保存当前图像
            image_path = os.path.join(debug_dir, 'debug_current.png')
            current_image.save(image_path)
            debug_text.insert(tk.END, f"✓ 已保存当前图像到 {image_path}\n\n")

            # 2. 获取新截图并比较
            debug_text.insert(tk.END, "正在获取新截图...\n")
            debug_text.update()

            if hasattr(self.screen_panel, 'device_controller'):
                try:
                    new_screenshot = self.screen_panel.device_controller.take_screenshot()
                    if new_screenshot:
                        new_path = os.path.join(debug_dir, 'debug_new.png')
                        new_screenshot.save(new_path)
                        debug_text.insert(tk.END, f"✓ 已保存新截图到 {new_path}\n")

                        # 比较两个图像
                        current_array = np.array(current_image)
                        new_array = np.array(new_screenshot)

                        if current_array.shape != new_array.shape:
                            debug_text.insert(tk.END, f"⚠️ 图像尺寸不同!\n")
                            debug_text.insert(tk.END, f"当前图像: {current_array.shape}\n")
                            debug_text.insert(tk.END, f"新截图: {new_array.shape}\n\n")
                        else:
                            # 计算差异
                            diff = cv2.absdiff(
                                cv2.cvtColor(current_array, cv2.COLOR_RGB2GRAY),
                                cv2.cvtColor(new_array, cv2.COLOR_RGB2GRAY)
                            )
                            diff_percent = np.count_nonzero(diff) / diff.size * 100
                            debug_text.insert(tk.END, f"图像差异: {diff_percent:.2f}%\n\n")

                            # 保存差异图
                            diff_path = os.path.join(debug_dir, 'debug_diff.png')
                            cv2.imwrite(diff_path, diff)
                    else:
                        debug_text.insert(tk.END, "❌ 获取新截图失败\n\n")
                except Exception as e:
                    debug_text.insert(tk.END, f"❌ 获取新截图出错: {str(e)}\n\n")
            else:
                debug_text.insert(tk.END, "❌ 无法获取设备控制器\n\n")

            # 3. 直接使用EasyOCR处理两个图像
            debug_text.insert(tk.END, "=== 使用EasyOCR分析图像 ===\n\n")

            try:
                import easyocr
                reader = easyocr.Reader(['ch_sim', 'en'])

                # 处理当前图像
                debug_text.insert(tk.END, "分析当前图像...\n")
                debug_text.update()

                current_results = reader.readtext(np.array(current_image))
                debug_text.insert(tk.END, f"识别到 {len(current_results)} 个文本区域:\n")

                found_in_current = False
                for i, (bbox, text, conf) in enumerate(current_results):
                    debug_text.insert(tk.END, f"{i + 1}. '{text}' (置信度: {conf:.2f})\n")
                    if target_text.lower() in text.lower():
                        debug_text.insert(tk.END, f"   ✓ 包含目标文本 '{target_text}'\n")
                        found_in_current = True

                if not found_in_current:
                    debug_text.insert(tk.END, f"❌ 当前图像中未找到 '{target_text}'\n")

                debug_text.insert(tk.END, "\n")

                # 如果有新截图，也处理它
                if 'new_screenshot' in locals():
                    debug_text.insert(tk.END, "分析新截图...\n")
                    debug_text.update()

                    new_results = reader.readtext(np.array(new_screenshot))
                    debug_text.insert(tk.END, f"识别到 {len(new_results)} 个文本区域:\n")

                    found_in_new = False
                    for i, (bbox, text, conf) in enumerate(new_results):
                        debug_text.insert(tk.END, f"{i + 1}. '{text}' (置信度: {conf:.2f})\n")
                        if target_text.lower() in text.lower():
                            debug_text.insert(tk.END, f"   ✓ 包含目标文本 '{target_text}'\n")
                            found_in_new = True

                            # 标记结果并保存
                            marked_img = np.array(new_screenshot).copy()
                            pts = np.array(bbox, np.int32).reshape((-1, 1, 2))
                            cv2.polylines(marked_img, [pts], True, (0, 0, 255), 2)

                            marked_path = os.path.join(debug_dir, 'debug_marked.png')
                            cv2.imwrite(marked_path, cv2.cvtColor(marked_img, cv2.COLOR_RGB2BGR))
                            debug_text.insert(tk.END, f"\n已将匹配标记保存到: {marked_path}\n")

                    if not found_in_new:
                        debug_text.insert(tk.END, f"❌ 新截图中未找到 '{target_text}'\n")

            except Exception as e:
                debug_text.insert(tk.END, f"EasyOCR分析失败: {str(e)}\n")
                import traceback
                debug_text.insert(tk.END, traceback.format_exc())

            # 4. 添加查看按钮
            button_frame = ttk.Frame(debug_window)
            button_frame.pack(fill=tk.X, pady=10)

            if os.path.exists(os.path.join(debug_dir, 'debug_current.png')):
                ttk.Button(
                    button_frame,
                    text="查看当前图像",
                    command=lambda: os.startfile(os.path.join(debug_dir, 'debug_current.png'))
                ).pack(side=tk.LEFT, padx=5)

            if 'new_path' in locals() and os.path.exists(new_path):
                ttk.Button(
                    button_frame,
                    text="查看新截图",
                    command=lambda: os.startfile(new_path)
                ).pack(side=tk.LEFT, padx=5)

            if 'diff_path' in locals() and os.path.exists(diff_path):
                ttk.Button(
                    button_frame,
                    text="查看差异图",
                    command=lambda: os.startfile(diff_path)
                ).pack(side=tk.LEFT, padx=5)

            if 'marked_path' in locals() and os.path.exists(marked_path):
                ttk.Button(
                    button_frame,
                    text="查看标记结果",
                    command=lambda: os.startfile(marked_path)
                ).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("调试错误", str(e))
            import traceback
            print(traceback.format_exc())

    def debug_text_recognition(self):
        import numpy as np
        import cv2
        import time
        """直接使用EasyOCR进行调试识别"""
        try:
            # 创建调试目录
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            os.makedirs(debug_dir, exist_ok=True)

            # 获取截图
            if hasattr(self.screen_panel, 'device_controller'):
                screenshot = self.screen_panel.device_controller.take_screenshot()
                if screenshot:
                    # 保存截图
                    screenshot_path = os.path.join(debug_dir, 'panel_direct_screenshot.png')
                    screenshot.save(screenshot_path)

                    # 创建调试窗口
                    debug_window = tk.Toplevel(self.parent)
                    debug_window.title("直接EasyOCR调试")
                    debug_window.geometry("800x600")

                    # 创建文本区域
                    debug_text = tk.Text(debug_window, wrap=tk.WORD)
                    debug_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                    debug_text.insert(tk.END, f"✓ 已保存截图到 {screenshot_path}\n\n")

                    # 显示截图信息
                    debug_text.insert(tk.END, f"截图尺寸: {screenshot.size}, 格式: {screenshot.mode}\n\n")
                    debug_text.update()

                    # 使用与debug_recognition.py相同的方式
                    import easyocr
                    target_text = self.target_text_var.get() or "斗地主"

                    debug_text.insert(tk.END, f"目标文本: '{target_text}'\n")
                    debug_text.insert(tk.END, "使用EasyOCR直接识别中...\n")
                    debug_text.update()

                    # 初始化读取器
                    reader = easyocr.Reader(['ch_sim', 'en'])

                    # 方法1: 使用OpenCV读取保存的图像（与debug_recognition.py相同）
                    debug_text.insert(tk.END, "方法1: 使用OpenCV读取保存的图像\n")
                    img_for_ocr1 = cv2.imread(screenshot_path)

                    if img_for_ocr1 is None:
                        debug_text.insert(tk.END, "❌ OpenCV无法读取图像，尝试备选方法\n")
                        # 备选：直接从PIL转换为numpy，然后转BGR
                        img_np = np.array(screenshot)
                        img_for_ocr1 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

                    debug_text.insert(tk.END, f"图像形状: {img_for_ocr1.shape}, 类型: {img_for_ocr1.dtype}\n")

                    try:
                        start_time = time.time()
                        results1 = reader.readtext(img_for_ocr1)
                        elapsed_time = time.time() - start_time

                        debug_text.insert(tk.END, f"识别到 {len(results1)} 个文本区域 (耗时: {elapsed_time:.2f}秒):\n")

                        found_target1 = False
                        for i, (bbox, text, confidence) in enumerate(results1):
                            debug_text.insert(tk.END, f"{i + 1}. '{text}' (置信度: {confidence:.2f})\n")
                            if target_text.lower() in text.lower():
                                debug_text.insert(tk.END, f"  ✓ 包含目标文本 '{target_text}'\n")
                                found_target1 = True
                    except Exception as e:
                        debug_text.insert(tk.END, f"❌ 方法1识别出错: {str(e)}\n")

                    # 方法2: 直接使用PIL格式转numpy(与recognition_panel.py类似)
                    debug_text.insert(tk.END, "\n方法2: 直接使用PIL图像转换\n")
                    img_np = np.array(screenshot)
                    debug_text.insert(tk.END, f"NumPy数组形状: {img_np.shape}, 类型: {img_np.dtype}\n")

                    # 检查通道数和处理RGB/RGBA
                    if len(img_np.shape) == 3:
                        if img_np.shape[2] == 4:  # RGBA
                            debug_text.insert(tk.END, "检测到RGBA图像，转换为RGB\n")
                            img_np = img_np[:, :, :3]  # 去除Alpha通道

                        img_for_ocr2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    else:
                        img_for_ocr2 = img_np

                    debug_text.insert(tk.END, f"处理后图像形状: {img_for_ocr2.shape}, 类型: {img_for_ocr2.dtype}\n")

                    try:
                        start_time = time.time()
                        results2 = reader.readtext(img_for_ocr2)
                        elapsed_time = time.time() - start_time

                        debug_text.insert(tk.END, f"识别到 {len(results2)} 个文本区域 (耗时: {elapsed_time:.2f}秒):\n")

                        found_target2 = False
                        for i, (bbox, text, confidence) in enumerate(results2):
                            debug_text.insert(tk.END, f"{i + 1}. '{text}' (置信度: {confidence:.2f})\n")
                            if target_text.lower() in text.lower():
                                debug_text.insert(tk.END, f"  ✓ 包含目标文本 '{target_text}'\n")
                                found_target2 = True
                    except Exception as e:
                        debug_text.insert(tk.END, f"❌ 方法2识别出错: {str(e)}\n")

                    # 方法3: 直接使用保存的图像路径
                    debug_text.insert(tk.END, "\n方法3: 直接使用图像文件路径\n")
                    try:
                        start_time = time.time()
                        results3 = reader.readtext(screenshot_path)
                        elapsed_time = time.time() - start_time

                        debug_text.insert(tk.END, f"识别到 {len(results3)} 个文本区域 (耗时: {elapsed_time:.2f}秒):\n")

                        found_target3 = False
                        for i, (bbox, text, confidence) in enumerate(results3):
                            debug_text.insert(tk.END, f"{i + 1}. '{text}' (置信度: {confidence:.2f})\n")
                            if target_text.lower() in text.lower():
                                debug_text.insert(tk.END, f"  ✓ 包含目标文本 '{target_text}'\n")
                                found_target3 = True
                    except Exception as e:
                        debug_text.insert(tk.END, f"❌ 方法3识别出错: {str(e)}\n")

                    # 添加对比结论
                    debug_text.insert(tk.END, "\n对比结论:\n")
                    if 'found_target1' in locals():
                        debug_text.insert(tk.END,
                                          f"方法1 (OpenCV读取): {'找到' if found_target1 else '未找到'} '{target_text}'\n")
                    if 'found_target2' in locals():
                        debug_text.insert(tk.END,
                                          f"方法2 (PIL转NumPy): {'找到' if found_target2 else '未找到'} '{target_text}'\n")
                    if 'found_target3' in locals():
                        debug_text.insert(tk.END,
                                          f"方法3 (文件路径): {'找到' if found_target3 else '未找到'} '{target_text}'\n")

                    # 保存调试日志
                    log_path = os.path.join(debug_dir, 'easyocr_comparison.log')
                    with open(log_path, 'w', encoding='utf-8') as f:
                        f.write(debug_text.get(1.0, tk.END))

                    debug_text.insert(tk.END, f"\n调试日志已保存到: {log_path}\n")
                else:
                    messagebox.showinfo("提示", "获取截图失败")
            else:
                messagebox.showinfo("提示", "设备控制器不可用")
        except Exception as e:
            messagebox.showerror("调试错误", str(e))
            import traceback
            print(traceback.format_exc())


