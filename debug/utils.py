"""
调试工具包的辅助函数
"""
import os
import time
import logging
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import json

# 设置日志
def setup_logger(name, log_file='debug.log', level=logging.INFO):
    """设置并返回一个日志记录器"""
    # 创建日志目录
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    handler = logging.FileHandler(log_file)
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)
    
    return logger

# 图像处理函数
def pil_to_tk(pil_image, size=None):
    """将PIL图像转换为Tkinter兼容的PhotoImage"""
    if size:
        pil_image = pil_image.resize(size, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(pil_image)

def crop_image(image, roi):
    """裁剪图像指定区域
    
    Args:
        image: PIL图像对象
        roi: 区域 (x1, y1, x2, y2)
        
    Returns:
        裁剪后的PIL图像
    """
    return image.crop(roi)

def draw_roi(image, roi, color="red", width=2):
    """在图像上绘制ROI矩形
    
    Args:
        image: PIL图像对象
        roi: 区域 (x1, y1, x2, y2)
        color: 线条颜色
        width: 线条宽度
        
    Returns:
        标记后的图像
    """
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    draw.rectangle(roi, outline=color, width=width)
    return img_copy

def draw_match_result(image, result, color="green", width=2, text=None):
    """在图像上标记匹配结果
    
    Args:
        image: PIL图像对象
        result: 匹配结果，格式 (x, y, w, h) 或 (x, y)
        color: 线条颜色
        width: 线条宽度
        text: 可选文本标签
        
    Returns:
        标记后的图像
    """
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    
    if len(result) == 4:
        x, y, w, h = result
        rect = (x-w//2, y-h//2, x+w//2, y+h//2)
        draw.rectangle(rect, outline=color, width=width)
        
        # 添加中心点标记
        dot_size = 3
        draw.ellipse((x-dot_size, y-dot_size, x+dot_size, y+dot_size), fill=color)
        
        # 添加文本
        if text:
            draw.text((x+w//2+5, y-h//2), text, fill=color)
    else:
        # 只有中心点的情况
        x, y = result
        dot_size = 5
        draw.ellipse((x-dot_size, y-dot_size, x+dot_size, y+dot_size), fill=color)
        
        # 添加文本
        if text:
            draw.text((x+10, y-10), text, fill=color)
    
    return img_copy

def save_config(data, file_path):
    """保存配置到JSON文件"""
    # 确保目录存在
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_config(file_path):
    """从JSON文件加载配置"""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_timestamp_filename(prefix, extension):
    """生成带时间戳的文件名"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"
