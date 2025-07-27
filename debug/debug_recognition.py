"""
临时调试脚本：直接测试屏幕识别功能
跟踪识别全过程，输出详细调试信息
"""
import os
import sys
import time
import logging
import cv2
import numpy as np
from PIL import Image

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("recognition_debug.log", mode="w"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RecognitionDebug')

def debug_recognition():
    """执行识别调试"""
    logger.info("=== 开始屏幕识别调试 ===")
    
    try:
        # 导入组件
        from components.device_controller import AndroidDeviceController
        from components.screen_recognizer import ScreenRecognizer
        
        # 步骤1: 初始化设备控制器
        logger.info("步骤1: 初始化设备控制器")
        device = AndroidDeviceController()
        if hasattr(device, 'initialize'):
            init_result = device.initialize()
            logger.info(f"设备初始化结果: {init_result}")
        
        # 检查设备状态
        if hasattr(device, 'is_initialized'):
            logger.info(f"设备是否初始化: {device.is_initialized}")
        else:
            logger.warning("设备未实现is_initialized属性")
        
        # 步骤2: 初始化屏幕识别器
        logger.info("步骤2: 初始化屏幕识别器")
        
        # 检查EasyOCR是否可用
        try:
            import easyocr
            logger.info("EasyOCR可用")
            easyocr_available = True
        except ImportError:
            logger.warning("EasyOCR不可用，将只使用pytesseract")
            easyocr_available = False
        
        # 初始化识别器
        recognizer = ScreenRecognizer(device)
        recognizer.initialize()
        
        # 步骤3: 截取屏幕
        logger.info("步骤3: 截取屏幕")
        screenshot = device.take_screenshot()
        if screenshot is None:
            logger.error("截图失败")
            return
        
        # 保存截图用于后续分析
        debug_dir = os.path.join(project_root, 'debug', 'temp')
        os.makedirs(debug_dir, exist_ok=True)
        screenshot_path = os.path.join(debug_dir, 'debug_screenshot.png')
        screenshot.save(screenshot_path)
        logger.info(f"截图已保存到: {screenshot_path}")
        
        # 转换为numpy数组
        screenshot_np = np.array(screenshot)
        
        # 步骤4: 执行文本识别 (多种阈值)
        logger.info("步骤4: 执行文本识别")
        target_texts = ['斗地主', '经典场', '菜单']
        thresholds = [0.1, 0.3, 0.5, 0.7]
        
        for target_text in target_texts:
            logger.info(f"目标文本: '{target_text}'")
            
            for threshold in thresholds:
                logger.info(f"使用阈值: {threshold}")
                result = recognizer.find_text(target_text, threshold=threshold)
                
                if result:
                    logger.info(f"找到匹配: {result}")
                    
                    # 在图像上标记结果
                    marked_img = screenshot_np.copy()
                    x, y, w, h = result
                    cv2.rectangle(marked_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(
                        marked_img, 
                        f"{target_text} ({threshold})", 
                        (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, 
                        (0, 255, 0), 
                        2
                    )
                    
                    # 保存标记后的图像
                    result_path = os.path.join(
                        debug_dir, 
                        f"result_{target_text.replace(' ', '_')}_{threshold}.png"
                    )
                    cv2.imwrite(
                        result_path, 
                        cv2.cvtColor(marked_img, cv2.COLOR_RGB2BGR)
                    )
                    logger.info(f"结果图像已保存到: {result_path}")
                else:
                    logger.info(f"未找到匹配")
        
        # 步骤5: 如果有EasyOCR，尝试直接调用EasyOCR
        if easyocr_available:
            logger.info("步骤5: 直接使用EasyOCR")
            import easyocr
            
            # 初始化读取器
            reader = easyocr.Reader(['ch_sim', 'en'])
            
            # 读取图像
            img_for_ocr = cv2.imread(screenshot_path)
            
            # 进行OCR
            try:
                ocr_start = time.time()
                logger.info("开始OCR识别...")
                results = reader.readtext(img_for_ocr)
                ocr_time = time.time() - ocr_start
                
                logger.info(f"OCR识别完成，耗时: {ocr_time:.2f}秒")
                logger.info(f"识别到 {len(results)} 个文本区域")
                
                # 记录每个识别结果
                for i, (bbox, text, prob) in enumerate(results):
                    logger.info(f"结果 {i+1}: '{text}' (置信度: {prob:.4f})")
                    
                    # 检查是否包含目标文本
                    for target_text in target_texts:
                        if target_text.lower() in text.lower():
                            logger.info(f"  ✓ 包含目标文本 '{target_text}'")
                
                # 在图像上标记所有识别结果
                visual_img = img_for_ocr.copy()
                for bbox, text, prob in results:
                    # 绘制边界框
                    pts = np.array(bbox, np.int32)
                    cv2.polylines(visual_img, [pts.reshape((-1, 1, 2))], True, (0, 255, 0), 2)
                    
                    # 添加文本
                    x_min = min(point[0] for point in bbox)
                    y_min = min(point[1] for point in bbox)
                    cv2.putText(
                        visual_img, 
                        f"{text[:10]}.. ({prob:.2f})", 
                        (int(x_min), int(y_min) - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, 
                        (0, 255, 0), 
                        2
                    )
                
                # 保存可视化结果
                visual_path = os.path.join(debug_dir, 'easyocr_results.png')
                cv2.imwrite(visual_path, visual_img)
                logger.info(f"EasyOCR识别结果已保存到: {visual_path}")
                
            except Exception as e:
                logger.error(f"EasyOCR识别失败: {e}")
        
        # 步骤6: 识别图像
        logger.info("步骤6: 执行图像识别")
        # 这里您可以添加具体的图像识别测试
        
        logger.info("=== 屏幕识别调试完成 ===")
        
    except Exception as e:
        logger.error(f"调试过程出错: {e}", exc_info=True)

if __name__ == "__main__":
    debug_recognition()
