# 屏幕识别模块优化开发文档

## 概述

本文档描述屏幕识别模块的优化方案，主要包括两大功能：
1. **游戏状态识别**：通过轻量级特征识别当前游戏所处的唯一状态
2. **物体检测**：使用YOLO检测游戏中的特定物体并返回位置坐标

## 数据库结构设计

### 1. 游戏状态表 (game_states)

```sql
CREATE TABLE game_states (
    state_id VARCHAR(50) PRIMARY KEY,           -- 状态唯一标识
    app_id VARCHAR(50) NOT NULL,                -- 应用ID
    state_name VARCHAR(100) NOT NULL,           -- 状态名称描述
    feature_vector TEXT,                        -- JSON格式轻量级特征向量
    roi_config TEXT,                           -- JSON格式感兴趣区域配置
    confidence_threshold FLOAT DEFAULT 0.8,    -- 识别置信度阈值
    screenshot_sample VARCHAR(200),             -- 样本截图路径（可选）
    parent_state VARCHAR(50),                  -- 父状态ID（用于层级关系）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(app_id),
    INDEX idx_app_state (app_id, state_id)
);
```

### 2. 物体检测配置表 (object_detection_configs)

```sql
CREATE TABLE object_detection_configs (
    config_id VARCHAR(50) PRIMARY KEY,          -- 配置唯一标识
    app_id VARCHAR(50) NOT NULL,                -- 应用ID
    object_type VARCHAR(50) NOT NULL,           -- 物体类型（如"元宝", "按钮"等）
    yolo_model_path VARCHAR(200),               -- YOLO模型文件路径
    class_names TEXT,                           -- JSON格式类别名称列表
    confidence_threshold FLOAT DEFAULT 0.5,     -- YOLO检测置信度阈值
    nms_threshold FLOAT DEFAULT 0.4,            -- 非极大值抑制阈值
    input_size VARCHAR(20) DEFAULT '640x640',   -- 模型输入尺寸
    roi_filter TEXT,                           -- JSON格式ROI过滤区域
    color_filter TEXT,                         -- JSON格式颜色过滤配置
    size_filter TEXT,                          -- JSON格式尺寸过滤配置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES applications(app_id),
    INDEX idx_app_object (app_id, object_type)
);
```

### 3. 状态识别历史表 (state_recognition_history)

```sql
CREATE TABLE state_recognition_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(50) NOT NULL,
    recognized_state VARCHAR(50),
    confidence_score FLOAT,
    recognition_time_ms INT,                    -- 识别耗时（毫秒）
    screenshot_path VARCHAR(200),              -- 对应截图路径
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_app_time (app_id, timestamp),
    INDEX idx_state_time (recognized_state, timestamp)
);
```

## 模块架构设计

### 时间戳管理责任分工

**设备控制模块 (TermuxDeviceController)**：
- 负责截图的时间戳生成和文件命名
- 维护截图缓存的物理存储
- 提供时间戳查询接口

**屏幕识别模块 (ScreenRecognizer)**：
- 请求指定时间戳或最新的截图
- 执行识别算法
- 缓存识别结果

### 缓存策略

```python
# 截图缓存结构
screenshot_cache = {
    timestamp: {
        'image': PIL.Image,
        'file_path': str,
        'created_at': float,
        'access_count': int
    }
}

# 识别结果缓存结构  
recognition_cache = {
    (timestamp, recognition_type): {
        'result': dict,
        'confidence': float,
        'cached_at': float
    }
}
```

## 接口设计

### 扩展的IScreenRecognizer接口

```python
class IScreenRecognizer(ABC):
    # === 原有方法保留 ===
    @abstractmethod
    def find_image(self, template_path: str, threshold: float = 0.8, roi: tuple = None): pass
    
    @abstractmethod
    def recognize_scene(self, scene_configs: Dict[str, Any]) -> Optional[str]: pass
    
    # === 新增方法 ===
    @abstractmethod
    def recognize_game_state(self, app_id: str, screenshot_timestamp: float = None) -> Dict[str, Any]:
        """识别游戏状态
        
        Args:
            app_id: 应用ID
            screenshot_timestamp: 指定截图时间戳，None表示使用最新截图
            
        Returns:
            {
                'state_id': str,
                'confidence': float,
                'recognition_time_ms': int,
                'timestamp': float
            }
        """
        pass
    
    @abstractmethod  
    def detect_objects_yolo(self, app_id: str, object_type: str, 
                           screenshot_timestamp: float = None, 
                           max_detections: int = 20) -> List[Dict[str, Any]]:
        """YOLO物体检测
        
        Args:
            app_id: 应用ID
            object_type: 物体类型
            screenshot_timestamp: 指定截图时间戳
            max_detections: 最大检测数量
            
        Returns:
            [
                {
                    'bbox': (x, y, width, height),
                    'confidence': float,
                    'class_name': str,
                    'center_point': (center_x, center_y)
                }
            ]
        """
        pass
    
    @abstractmethod
    def load_recognition_configs(self, app_id: str) -> bool:
        """从数据库加载识别配置"""
        pass
    
    @abstractmethod
    def get_recognition_performance_stats(self, app_id: str) -> Dict[str, Any]:
        """获取识别性能统计"""
        pass
```

## 实现要点

### 1. 轻量级状态特征提取

```python
def extract_state_features(self, screenshot, roi_configs):
    """提取状态识别特征"""
    features = []
    
    # 1. 全局颜色直方图
    hist = cv2.calcHist([screenshot], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
    features.extend(hist.flatten()[:64])  # 取前64维
    
    # 2. ROI区域特征
    for roi_name, roi_bbox in roi_configs.items():
        roi_region = screenshot[roi_bbox[1]:roi_bbox[3], roi_bbox[0]:roi_bbox[2]]
        roi_mean_color = np.mean(roi_region, axis=(0,1))
        features.extend(roi_mean_color)
    
    # 3. 边缘密度特征
    gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])
    features.append(edge_density)
    
    return np.array(features)
```

### 2. YOLO集成方案

使用ultralytics的YOLOv8n（nano版本）：
- 模型大小：~6MB
- 推理速度：~2-10ms (CPU)
- 部署简单：pip install ultralytics

### 3. 性能监控

记录每次识别的性能指标：
- 识别耗时
- 置信度分布
- 缓存命中率
- 错误识别统计

## 部署配置

### 环境依赖

```bash
# 核心依赖
pip install ultralytics>=8.0.0
pip install opencv-python>=4.5.0
pip install numpy>=1.21.0
pip install pillow>=8.0.0

# 可选加速
pip install onnxruntime  # CPU推理加速
```

### 配置文件示例

```json
{
    "recognition_config": {
        "cache_settings": {
            "screenshot_cache_size": 5,
            "screenshot_max_age_seconds": 3.0,
            "recognition_cache_size": 20,
            "recognition_cache_ttl_seconds": 10.0
        },
        "performance_settings": {
            "max_recognition_time_ms": 100,
            "enable_performance_logging": true,
            "log_failed_recognitions": true
        },
        "yolo_settings": {
            "default_confidence_threshold": 0.5,
            "default_nms_threshold": 0.4,
            "max_detections_per_image": 20,
            "use_gpu_if_available": false
        }
    }
}
```

## 后续扩展计划

1. **模型训练工具集**：独立的状态分类器训练脚本
2. **自动数据收集**：运行时自动收集困难样本
3. **A/B测试框架**：对比不同识别策略的效果
4. **分布式识别**：支持多设备协同识别

## 注意事项

1. **文本识别模块**：当前留空，等待更好的技术方案
2. **YOLO模型管理**：模型文件需要合理的版本管理和更新机制
3. **内存管理**：大量截图缓存需要注意内存泄漏
4. **数据库性能**：识别历史表可能增长很快，需要定期清理策略