import os
import cv2
import numpy as np
import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from core.interfaces import IScreenRecognizer, IDeviceController, IDatabaseManager
from core.base_classes import SystemModule
from PIL import Image

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logging.warning("YOLO未安装，物体检测功能将不可用。安装命令: pip install ultralytics")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("screen_recognizer.log"), logging.StreamHandler()]
)
logger = logging.getLogger('screen_recognizer')


class ScreenshotCache:
    """截图缓存管理器"""
    
    def __init__(self, max_cache_size=5, max_age_seconds=3.0):
        self.max_cache_size = max_cache_size
        self.max_age_seconds = max_age_seconds
        self.cache = {}  # {timestamp: {'image': PIL.Image, 'file_path': str, 'created_at': float}}
        
    def add_screenshot(self, timestamp: float, image: Image.Image, file_path: str = None):
        """添加截图到缓存"""
        self.cache[timestamp] = {
            'image': image,
            'file_path': file_path,
            'created_at': time.time(),
            'access_count': 0
        }
        
        # 清理过期和超量缓存
        self._cleanup_cache()
    
    def get_screenshot(self, timestamp: float = None, max_age: float = None) -> Optional[Image.Image]:
        """获取截图"""
        if max_age is None:
            max_age = self.max_age_seconds
            
        current_time = time.time()
        
        if timestamp is None:
            # 获取最新的有效截图
            valid_timestamps = [
                ts for ts, data in self.cache.items()
                if current_time - data['created_at'] <= max_age
            ]
            if valid_timestamps:
                timestamp = max(valid_timestamps)
            else:
                return None
        
        if timestamp in self.cache:
            data = self.cache[timestamp]
            if current_time - data['created_at'] <= max_age:
                data['access_count'] += 1
                return data['image']
        
        return None
    
    def _cleanup_cache(self):
        """清理过期和超量缓存"""
        current_time = time.time()
        
        # 移除过期项
        expired_keys = [
            ts for ts, data in self.cache.items()
            if current_time - data['created_at'] > self.max_age_seconds
        ]
        for key in expired_keys:
            del self.cache[key]
        
        # 如果仍然超量，移除最旧的项
        while len(self.cache) > self.max_cache_size:
            oldest_key = min(self.cache.keys())
            del self.cache[oldest_key]


class RecognitionResultCache:
    """识别结果缓存"""
    
    def __init__(self, max_cache_size=50, ttl_seconds=10.0):
        self.max_cache_size = max_cache_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}  # {(timestamp, recognition_type, params_hash): result}
        
    def get_cached_result(self, timestamp: float, recognition_type: str, params_hash: str):
        """获取缓存的识别结果"""
        key = (timestamp, recognition_type, params_hash)
        if key in self.cache:
            result_data = self.cache[key]
            if time.time() - result_data['cached_at'] <= self.ttl_seconds:
                return result_data['result']
            else:
                del self.cache[key]
        return None
    
    def cache_result(self, timestamp: float, recognition_type: str, params_hash: str, result):
        """缓存识别结果"""
        key = (timestamp, recognition_type, params_hash)
        self.cache[key] = {
            'result': result,
            'cached_at': time.time()
        }
        
        # 清理超量缓存
        if len(self.cache) > self.max_cache_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['cached_at'])
            del self.cache[oldest_key]


class ScreenRecognizer(SystemModule, IScreenRecognizer):
    """优化后的屏幕识别器"""

    def __init__(self, device_controller: IDeviceController, db_manager: IDatabaseManager = None):
        """初始化屏幕识别器

        Args:
            device_controller: 设备控制器实例
            db_manager: 数据库管理器实例
        """
        super().__init__("ScreenRecognizer", "2.0")
        self.device = device_controller
        self.db_manager = db_manager
        
        # 缓存系统
        self.screenshot_cache = ScreenshotCache()
        self.result_cache = RecognitionResultCache()
        
        # 配置数据
        self.state_configs = {}  # {app_id: {state_id: config}}
        self.object_configs = {}  # {app_id: {object_type: config}}
        
        # YOLO模型缓存
        self.yolo_models = {}  # {model_path: YOLO}
        
        # 性能统计
        self.performance_stats = {
            'recognition_count': 0,
            'total_time_ms': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        self.debug_mode = False

    def initialize(self) -> bool:
        """初始化识别器"""
        if self._initialized:
            return True

        self.log_info("初始化优化后的屏幕识别器")

        # 检查必要依赖
        try:
            cv_version = cv2.__version__
            self.log_info(f"OpenCV版本: {cv_version}")
        except Exception as e:
            self.log_error(f"OpenCV不可用: {str(e)}")
            return False

        # 检查YOLO可用性
        if YOLO_AVAILABLE:
            self.log_info("YOLO可用，物体检测功能已启用")
        else:
            self.log_warning("YOLO不可用，物体检测功能将被禁用")

        self._initialized = True
        self.log_info("屏幕识别器初始化完成")
        return True
        
    def shutdown(self) -> bool:
        """关闭识别器"""
        # 清理模型缓存
        self.yolo_models.clear()
        self._initialized = False
        self.log_info("屏幕识别器已关闭")
        return True

    # ==================== 缓存管理方法 ====================
    
    def _get_screenshot_with_cache(self, timestamp: float = None) -> Optional[Image.Image]:
        """获取截图（优先使用缓存）"""
        # 先尝试从缓存获取
        cached_screenshot = self.screenshot_cache.get_screenshot(timestamp)
        
        if cached_screenshot is not None:
            self.performance_stats['cache_hits'] += 1
            return cached_screenshot
        
        # 缓存未命中，获取新截图
        self.performance_stats['cache_misses'] += 1
        
        if hasattr(self.device, 'get_screenshot_with_timestamp'):
            # 如果设备控制器支持时间戳截图
            screenshot, actual_timestamp = self.device.get_screenshot_with_timestamp()
        else:
            # 传统方式
            screenshot = self.device.take_screenshot()
            actual_timestamp = time.time()
        
        if screenshot:
            # 添加到缓存
            self.screenshot_cache.add_screenshot(actual_timestamp, screenshot)
            return screenshot
        
        return None

    # ==================== 原有方法保留 ====================

    def find_image(self, template_path: str, threshold: float = 0.8, roi: tuple = None):
        """在屏幕上查找模板图像（保留原有实现）"""
        if not self._initialized:
            self.log_error("识别器未初始化")
            return None
            
        try:
            # 获取屏幕截图（使用缓存）
            screenshot = self._get_screenshot_with_cache()
            if screenshot is None:
                self.log_error("获取屏幕截图失败")
                return None
                
            # 转换为OpenCV格式
            screenshot_np = np.array(screenshot)
            screenshot_np = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            
            # 如果指定了ROI，裁剪图像
            if roi:
                x1, y1, x2, y2 = roi
                screenshot_np = screenshot_np[y1:y2, x1:x2]

            # 读取模板图像
            template = cv2.imread(template_path)
            if template is None:
                self.log_error(f"无法读取模板图像: {template_path}")
                return None

            # 模板匹配
            result = cv2.matchTemplate(screenshot_np, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 检查匹配度
            if max_val >= threshold:
                w, h = template.shape[1], template.shape[0]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                
                # 如果使用了ROI，调整坐标
                if roi:
                    center_x += roi[0]
                    center_y += roi[1]
                    
                self.log_info(f"找到图像 {template_path}，位置: ({center_x}, {center_y})，匹配度: {max_val:.2f}")
                return (center_x, center_y, w, h)
            else:
                self.log_info(f"未找到图像: {template_path}，最佳匹配度: {max_val:.2f}")
                return None
                
        except Exception as e:
            self.log_error(f"图像识别出错: {str(e)}")
            return None

    def find_text(self, text: str, lang: str = None, config: str = None, roi: tuple = None, threshold: float = 0.6):
        """查找文本（保留接口，暂时留空实现）"""
        self.log_warning("文本识别功能暂时禁用，等待更好的技术方案")
        return None

    def get_screen_text(self, lang: str = 'chi_sim+eng') -> str:
        """获取屏幕文本（保留接口，暂时留空实现）"""
        self.log_warning("屏幕文本识别功能暂时禁用，等待更好的技术方案")
        return ""

    def recognize_scene(self, scene_configs: Dict[str, Any]) -> Optional[str]:
        """识别当前场景（保留原实现，使用缓存优化）"""
        if not self._initialized:
            self.log_error("识别器未初始化")
            return None
            
        for scene_name, config in scene_configs.items():
            try:
                if config["type"] == "image":
                    # 图像识别
                    result = self.find_image(
                        config["template_path"],
                        threshold=config.get("threshold", 0.8),
                        roi=config.get("roi")
                    )
                    if result:
                        self.log_info(f"识别到场景: {scene_name}")
                        return scene_name
                # 注意：文本识别暂时跳过
                        
            except Exception as e:
                self.log_error(f"场景 {scene_name} 识别出错: {str(e)}")
                
        self.log_info("未能识别当前场景")
        return None

    # ==================== 新增功能：游戏状态识别 ====================

    def recognize_game_state(self, app_id: str, screenshot_timestamp: float = None) -> Dict[str, Any]:
        """识别游戏状态"""
        start_time = time.time()
        
        try:
            # 生成缓存键
            params_hash = f"{app_id}_{screenshot_timestamp or 'latest'}"
            
            # 检查缓存
            cached_result = self.result_cache.get_cached_result(
                screenshot_timestamp or time.time(), 
                'game_state', 
                params_hash
            )
            if cached_result:
                return cached_result
            
            # 获取截图
            screenshot = self._get_screenshot_with_cache(screenshot_timestamp)
            if screenshot is None:
                return {
                    'state_id': 'unknown',
                    'confidence': 0.0,
                    'recognition_time_ms': 0,
                    'error': 'screenshot_failed'
                }
            
            # 确保配置已加载
            if app_id not in self.state_configs:
                self.load_recognition_configs(app_id)
            
            if app_id not in self.state_configs:
                return {
                    'state_id': 'unknown',
                    'confidence': 0.0,
                    'recognition_time_ms': int((time.time() - start_time) * 1000),
                    'error': 'no_configs'
                }
            
            # 提取轻量级特征
            features = self._extract_state_features(screenshot, app_id)
            
            # 匹配最佳状态
            best_match = self._find_best_matching_state(features, app_id)
            
            recognition_time_ms = int((time.time() - start_time) * 1000)
            
            result = {
                'state_id': best_match['state_id'] if best_match else 'unknown',
                'confidence': best_match['confidence'] if best_match else 0.0,
                'recognition_time_ms': recognition_time_ms,
                'timestamp': screenshot_timestamp or time.time()
            }
            
            # 缓存结果
            self.result_cache.cache_result(
                screenshot_timestamp or time.time(),
                'game_state',
                params_hash,
                result
            )
            
            # 更新性能统计
            self.performance_stats['recognition_count'] += 1
            self.performance_stats['total_time_ms'] += recognition_time_ms
            
            return result
            
        except Exception as e:
            self.log_error(f"游戏状态识别失败: {str(e)}")
            return {
                'state_id': 'unknown',
                'confidence': 0.0,
                'recognition_time_ms': int((time.time() - start_time) * 1000),
                'error': str(e)
            }

    def _extract_state_features(self, screenshot: Image.Image, app_id: str) -> np.ndarray:
        """提取状态识别的轻量级特征"""
        try:
            # 转换为numpy数组
            img_array = np.array(screenshot)
            
            features = []
            
            # 1. 全局颜色直方图特征
            hist_b = cv2.calcHist([img_array], [0], None, [16], [0, 256])
            hist_g = cv2.calcHist([img_array], [1], None, [16], [0, 256])
            hist_r = cv2.calcHist([img_array], [2], None, [16], [0, 256])
            
            features.extend(hist_b.flatten())
            features.extend(hist_g.flatten())
            features.extend(hist_r.flatten())
            
            # 2. ROI区域特征（如果配置了）
            app_states = self.state_configs.get(app_id, {})
            roi_configs = {}
            for state_id, state_config in app_states.items():
                if 'roi_config' in state_config and state_config['roi_config']:
                    roi_data = json.loads(state_config['roi_config'])
                    roi_configs.update(roi_data)
            
            for roi_name, roi_bbox in roi_configs.items():
                if len(roi_bbox) >= 4:
                    x1, y1, x2, y2 = roi_bbox[:4]
                    roi_region = img_array[y1:y2, x1:x2]
                    if roi_region.size > 0:
                        roi_mean_color = np.mean(roi_region, axis=(0, 1))
                        features.extend(roi_mean_color)
            
            # 3. 边缘密度特征
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])
            features.append(edge_density)
            
            return np.array(features)
            
        except Exception as e:
            self.log_error(f"特征提取失败: {str(e)}")
            return np.array([])

    def _find_best_matching_state(self, features: np.ndarray, app_id: str) -> Optional[Dict[str, Any]]:
        """找到最佳匹配的状态"""
        if features.size == 0:
            return None
            
        best_match = None
        best_distance = float('inf')
        
        app_states = self.state_configs.get(app_id, {})
        
        for state_id, state_config in app_states.items():
            try:
                if 'feature_vector' not in state_config or not state_config['feature_vector']:
                    continue
                    
                stored_features = np.array(json.loads(state_config['feature_vector']))
                
                # 确保特征向量长度一致
                min_len = min(len(features), len(stored_features))
                if min_len == 0:
                    continue
                    
                # 计算欧几里得距离
                distance = np.linalg.norm(features[:min_len] - stored_features[:min_len])
                
                # 转换为相似度
                confidence = 1.0 / (1.0 + distance)
                
                # 检查是否超过阈值
                threshold = state_config.get('confidence_threshold', 0.8)
                
                if confidence >= threshold and distance < best_distance:
                    best_distance = distance
                    best_match = {
                        'state_id': state_id,
                        'confidence': confidence,
                        'distance': distance
                    }
                    
            except Exception as e:
                self.log_error(f"状态匹配失败 {state_id}: {str(e)}")
                
        return best_match

    # ==================== 新增功能：YOLO物体检测 ====================

    def detect_objects_yolo(self, app_id: str, object_type: str, 
                           screenshot_timestamp: float = None, 
                           max_detections: int = 20) -> List[Dict[str, Any]]:
        """YOLO物体检测"""
        if not YOLO_AVAILABLE:
            self.log_error("YOLO不可用，无法执行物体检测")
            return []
            
        start_time = time.time()
        
        try:
            # 生成缓存键
            params_hash = f"{app_id}_{object_type}_{max_detections}_{screenshot_timestamp or 'latest'}"
            
            # 检查缓存
            cached_result = self.result_cache.get_cached_result(
                screenshot_timestamp or time.time(),
                'yolo_detection',
                params_hash
            )
            if cached_result:
                return cached_result
            
            # 获取截图
            screenshot = self._get_screenshot_with_cache(screenshot_timestamp)
            if screenshot is None:
                self.log_error("获取截图失败")
                return []
            
            # 确保配置已加载
            if app_id not in self.object_configs:
                self.load_recognition_configs(app_id)
            
            # 获取物体检测配置
            object_config = self.object_configs.get(app_id, {}).get(object_type)
            if not object_config:
                self.log_error(f"未找到物体检测配置: {app_id}.{object_type}")
                return []
            
            # 加载YOLO模型
            model = self._get_yolo_model(object_config['yolo_model_path'])
            if not model:
                self.log_error(f"无法加载YOLO模型: {object_config['yolo_model_path']}")
                return []
            
            # 执行检测
            detections = self._run_yolo_detection(
                model, screenshot, object_config, max_detections
            )
            
            # 缓存结果
            self.result_cache.cache_result(
                screenshot_timestamp or time.time(),
                'yolo_detection',
                params_hash,
                detections
            )
            
            recognition_time_ms = int((time.time() - start_time) * 1000)
            self.log_info(f"YOLO检测完成: {len(detections)}个物体，耗时{recognition_time_ms}ms")
            
            return detections
            
        except Exception as e:
            self.log_error(f"YOLO物体检测失败: {str(e)}")
            return []

    def _get_yolo_model(self, model_path: str):
        """获取YOLO模型（缓存机制）"""
        if model_path in self.yolo_models:
            return self.yolo_models[model_path]
        
        try:
            if not os.path.exists(model_path):
                self.log_error(f"YOLO模型文件不存在: {model_path}")
                return None
                
            model = YOLO(model_path)
            self.yolo_models[model_path] = model
            self.log_info(f"YOLO模型加载成功: {model_path}")
            return model
            
        except Exception as e:
            self.log_error(f"YOLO模型加载失败: {str(e)}")
            return None

    def _run_yolo_detection(self, model, screenshot: Image.Image, 
                           config: Dict[str, Any], max_detections: int) -> List[Dict[str, Any]]:
        """执行YOLO检测"""
        try:
            # 获取配置参数
            confidence_threshold = config.get('confidence_threshold', 0.5)
            nms_threshold = config.get('nms_threshold', 0.4)
            class_names = json.loads(config.get('class_names', '[]'))
            
            # 执行推理
            results = model(screenshot, conf=confidence_threshold, iou=nms_threshold)
            
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                    
                for i, box in enumerate(boxes):
                    if len(detections) >= max_detections:
                        break
                        
                    # 提取检测结果
                    xyxy = box.xyxy[0].cpu().numpy()  # 边界框坐标
                    conf = float(box.conf[0].cpu().numpy())  # 置信度
                    cls = int(box.cls[0].cpu().numpy())  # 类别
                    
                    # 计算中心点和尺寸
                    x1, y1, x2, y2 = xyxy
                    width = x2 - x1
                    height = y2 - y1
                    center_x = x1 + width / 2
                    center_y = y1 + height / 2
                    
                    # 获取类别名称
                    class_name = class_names[cls] if cls < len(class_names) else f"class_{cls}"
                    
                    detection = {
                        'bbox': (int(x1), int(y1), int(width), int(height)),
                        'confidence': conf,
                        'class_name': class_name,
                        'center_point': (int(center_x), int(center_y)),
                        'class_id': cls
                    }
                    
                    # 应用过滤器
                    if self._apply_detection_filters(detection, config):
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            self.log_error(f"YOLO检测执行失败: {str(e)}")
            return []

    def _apply_detection_filters(self, detection: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """应用检测过滤器"""
        try:
            # ROI过滤
            if 'roi_filter' in config and config['roi_filter']:
                roi_config = json.loads(config['roi_filter'])
                center_x, center_y = detection['center_point']
                
                if 'bbox' in roi_config:
                    rx1, ry1, rx2, ry2 = roi_config['bbox']
                    if not (rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2):
                        return False
            
            # 尺寸过滤
            if 'size_filter' in config and config['size_filter']:
                size_config = json.loads(config['size_filter'])
                width, height = detection['bbox'][2], detection['bbox'][3]
                
                if 'min_width' in size_config and width < size_config['min_width']:
                    return False
                if 'max_width' in size_config and width > size_config['max_width']:
                    return False
                if 'min_height' in size_config and height < size_config['min_height']:
                    return False
                if 'max_height' in size_config and height > size_config['max_height']:
                    return False
            
            return True
            
        except Exception as e:
            self.log_error(f"过滤器应用失败: {str(e)}")
            return True  # 过滤器失败时允许通过

    # ==================== 配置加载和管理 ====================

    def load_recognition_configs(self, app_id: str) -> bool:
        """从数据库加载识别配置"""
        if not self.db_manager:
            self.log_error("数据库管理器未初始化")
            return False
            
        try:
            # 加载状态识别配置
            state_query = """
                SELECT state_id, state_name, feature_vector, roi_config, confidence_threshold
                FROM game_states 
                WHERE app_id = ?
            """
            states = self.db_manager.fetch_all(state_query, (app_id,))
            
            if app_id not in self.state_configs:
                self.state_configs[app_id] = {}
                
            for state in states:
                self.state_configs[app_id][state['state_id']] = {
                    'state_name': state['state_name'],
                    'feature_vector': state['feature_vector'],
                    'roi_config': state['roi_config'],
                    'confidence_threshold': state['confidence_threshold']
                }
            
            # 加载物体检测配置
            object_query = """
                SELECT object_type, yolo_model_path, class_names, confidence_threshold,
                       nms_threshold, roi_filter, size_filter
                FROM object_detection_configs
                WHERE app_id = ?
            """
            objects = self.db_manager.fetch_all(object_query, (app_id,))
            
            if app_id not in self.object_configs:
                self.object_configs[app_id] = {}
                
            for obj in objects:
                self.object_configs[app_id][obj['object_type']] = {
                    'yolo_model_path': obj['yolo_model_path'],
                    'class_names': obj['class_names'],
                    'confidence_threshold': obj['confidence_threshold'],
                    'nms_threshold': obj['nms_threshold'],
                    'roi_filter': obj['roi_filter'],
                    'size_filter': obj['size_filter']
                }
            
            self.log_info(f"配置加载完成: {app_id} - {len(states)}个状态, {len(objects)}个物体类型")
            return True
            
        except Exception as e:
            self.log_error(f"配置加载失败: {str(e)}")
            return False

    def get_recognition_performance_stats(self, app_id: str = None) -> Dict[str, Any]:
        """获取识别性能统计"""
        stats = {
            'total_recognitions': self.performance_stats['recognition_count'],
            'total_time_ms': self.performance_stats['total_time_ms'],
            'avg_time_ms': 0,
            'cache_hit_rate': 0,
            'cache_stats': {
                'hits': self.performance_stats['cache_hits'],
                'misses': self.performance_stats['cache_misses'],
                'screenshot_cache_size': len(self.screenshot_cache.cache),
                'result_cache_size': len(self.result_cache.cache)
            }
        }
        
        if self.performance_stats['recognition_count'] > 0:
            stats['avg_time_ms'] = self.performance_stats['total_time_ms'] / self.performance_stats['recognition_count']
        
        total_cache_requests = self.performance_stats['cache_hits'] + self.performance_stats['cache_misses']
        if total_cache_requests > 0:
            stats['cache_hit_rate'] = self.performance_stats['cache_hits'] / total_cache_requests
        
        return stats

    # ==================== 调试和工具方法 ====================

    def enable_debug_mode(self, enable: bool = True):
        """启用/禁用调试模式"""
        self.debug_mode = enable
        self.log_info(f"调试模式已{'启用' if enable else '禁用'}")

    def clear_caches(self):
        """清空所有缓存"""
        self.screenshot_cache.cache.clear()
        self.result_cache.cache.clear()
        self.log_info("所有缓存已清空")

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'screenshot_cache': {
                'size': len(self.screenshot_cache.cache),
                'max_size': self.screenshot_cache.max_cache_size,
                'timestamps': list(self.screenshot_cache.cache.keys())
            },
            'result_cache': {
                'size': len(self.result_cache.cache),
                'max_size': self.result_cache.max_cache_size,
                'keys': [f"{k[1]}_{k[2]}" for k in self.result_cache.cache.keys()]
            },
            'model_cache': {
                'loaded_models': list(self.yolo_models.keys()),
                'count': len(self.yolo_models)
            }
        }

    def save_debug_screenshot(self, filename: str = None) -> str:
        """保存当前截图用于调试"""
        try:
            screenshot = self._get_screenshot_with_cache()
            if screenshot is None:
                return ""
            
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"debug_screenshot_{timestamp}.png"
            
            debug_dir = os.path.join(os.getcwd(), 'debug', 'temp')
            os.makedirs(debug_dir, exist_ok=True)
            
            filepath = os.path.join(debug_dir, filename)
            screenshot.save(filepath)
            
            self.log_info(f"调试截图已保存: {filepath}")
            return filepath
            
        except Exception as e:
            self.log_error(f"保存调试截图失败: {str(e)}")
            return ""
                