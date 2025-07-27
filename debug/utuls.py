import os
import time
from PIL import ImageDraw


def generate_timestamp_filename(prefix, ext):
    """生成带时间戳的文件名"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{ext}"


def draw_match_result(image, result, color='green', thickness=2, label=None):
    """在图像上绘制匹配结果"""
    x, y, w, h = result
    draw = ImageDraw.Draw(image)

    # 绘制矩形框
    draw.rectangle([x, y, x + w, y + h], outline=color, width=thickness)

    # 如果有标签，绘制标签
    if label:
        draw.text((x, y - 10), label, fill=color)

    return image