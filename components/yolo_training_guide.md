# YOLO模型训练与部署完整指南

## 概述

本指南描述如何为游戏自动化项目训练YOLO物体检测模型，并将训练好的模型集成到Termux环境的自动化系统中。

## 一、训练环境准备（PC端）

### 1.1 环境搭建

```bash
# 创建Python虚拟环境
conda create -n yolo_training python=3.9
conda activate yolo_training

# 安装依赖
pip install ultralytics
pip install labelImg
pip install PyYAML
pip install opencv-python
pip install pillow
```

### 1.2 项目目录结构

```
yolo_training_project/
├── datasets/
│   └── three_kingdoms/
│       ├── images/
│       │   ├── train/           # 训练图片（80%）
│       │   │   ├── img_001.png
│       │   │   ├── img_002.png
│       │   │   └── ...
│       │   └── val/             # 验证图片（20%）
│       │       ├── val_001.png
│       │       └── ...
│       ├── labels/
│       │   ├── train/           # 训练标签
│       │   │   ├── img_001.txt
│       │   │   ├── img_002.txt
│       │   │   └── ...
│       │   └── val/             # 验证标签
│       │       ├── val_001.txt
│       │       └── ...
│       └── dataset.yaml         # 数据集配置
├── models/                      # 训练好的模型
│   ├── three_kingdoms_v1.pt
│   ├── three_kingdoms_v1.onnx
│   └── ...
├── scripts/
│   ├── train.py                 # 训练脚本
│   ├── validate.py              # 验证脚本
│   └── export.py                # 模型导出脚本
├── test_images/                 # 测试图片
└── runs/                        # 训练结果输出
    └── detect/
        └── three_kingdoms_v1/
            ├── weights/
            │   ├── best.pt      # 最佳模型
            │   └── last.pt      # 最后一轮模型
            └── results.png      # 训练结果图
```

## 二、数据收集与标注

### 2.1 数据收集策略

**场景多样化收集**：
- 主界面（无弹窗、有广告、有对话框）
- 战斗界面（元宝掉落）
- 背包界面（元宝展示）
- 不同光照条件
- 不同分辨率和UI缩放

**数量建议**：
- 每个物体类别：100-200张图片
- 总数据集：300-500张图片
- 训练集：验证集 = 8:2

### 2.2 标注工具使用

```bash
# 启动标注工具
labelImg ./datasets/three_kingdoms/images/train ./datasets/three_kingdoms/labels/train

# 标注要点：
# 1. 选择YOLO格式
# 2. 精确框选物体边界
# 3. 包含光效和阴影
# 4. 部分遮挡也要标注
# 5. 类别命名保持一致
```

**标注格式示例**：
```
# img_001.txt
0 0.5123 0.3456 0.0987 0.1234    # class_id x_center y_center width height
1 0.2345 0.7890 0.0567 0.0789    # 所有坐标已归一化到0-1
```

### 2.3 数据集配置

```yaml
# dataset.yaml
path: ./datasets/three_kingdoms
train: images/train
val: images/val

# 类别数量
nc: 4

# 类别名称（顺序对应class_id）
names: 
  0: '元宝'
  1: '银币' 
  2: '道具箱'
  3: '按钮_确定'
```

## 三、模型训练

### 3.1 训练脚本

```python
# scripts/train.py
from ultralytics import YOLO
import yaml
import os

def train_game_model():
    """训练游戏物体检测模型"""
    
    # 检查数据集
    dataset_path = './datasets/three_kingdoms/dataset.yaml'
    if not os.path.exists(dataset_path):
        print("错误：数据集配置文件不存在")
        return
    
    # 加载预训练模型
    model = YOLO('yolov8n.pt')  # nano版本，最轻量
    
    # 训练配置（针对游戏场景优化）
    results = model.train(
        data=dataset_path,
        epochs=100,                # 训练轮数
        imgsz=640,                # 输入图像尺寸
        batch=16,                 # 批次大小（根据显存调整）
        device='0',               # GPU设备（'cpu'使用CPU）
        patience=15,              # 早停策略
        save=True,
        plots=True,
        
        # 项目配置
        project='./runs',
        name='three_kingdoms_v1',
        
        # 数据增强（游戏场景特化）
        augment=True,
        hsv_h=0.02,              # 色调变化（适应光照）
        hsv_s=0.7,               # 饱和度变化
        hsv_v=0.4,               # 亮度变化
        degrees=0,               # 不旋转（游戏界面固定）
        translate=0.1,           # 轻微平移
        scale=0.5,               # 缩放变化
        shear=0.0,               # 不剪切
        perspective=0.0,         # 不透视变换
        flipud=0.0,              # 不上下翻转
        fliplr=0.0,              # 不左右翻转
        
        # 高级增强
        mosaic=1.0,              # 马赛克增强
        mixup=0.1,               # 图像混合
        copy_paste=0.1           # 复制粘贴增强
    )
    
    print("训练完成！")
    print(f"最佳模型: ./runs/three_kingdoms_v1/weights/best.pt")
    return results

if __name__ == "__main__":
    train_game_model()
```

### 3.2 模型导出

```python
# scripts/export.py
from ultralytics import YOLO

def export_model():
    """导出模型为多种格式"""
    
    # 加载训练好的模型
    model = YOLO('./runs/three_kingdoms_v1/weights/best.pt')
    
    # 导出ONNX格式（推理更快）
    model.export(
        format='onnx',
        optimize=True,
        half=True,              # 半精度（减小模型大小）
        simplify=True
    )
    
    # 也可以导出TensorRT（如果有GPU）
    # model.export(format='engine', half=True)
    
    print("模型导出完成！")
    print("ONNX模型: ./runs/three_kingdoms_v1/weights/best.onnx")

if __name__ == "__main__":
    export_model()
```

### 3.3 训练监控

```bash
# 启动训练
cd yolo_training_project
python scripts/train.py

# 查看训练进度（另一个终端）
tensorboard --logdir ./runs

# 训练完成后查看结果
ls ./runs/three_kingdoms_v1/
# weights/best.pt - 最佳模型
# results.png - 训练曲线
# confusion_matrix.png - 混淆矩阵
# val_batch*.jpg - 验证结果可视化
```

## 四、模型部署到项目

### 4.1 文件结构部署

```bash
# Termux项目中的模型存储位置
termux_automation_project/
├── models/                    # 新建模型目录
│   ├── three_kingdoms/
│   │   ├── v1.0/
│   │   │   ├── model.pt       # 主模型文件
│   │   │   ├── model.onnx     # ONNX格式（可选）
│   │   │   └── config.json    # 模型配置文件
│   │   └── v1.1/             # 版本管理
│   └── other_game/
├── screenshots/
├── cache/
├── debug/
├── data/
├── core/
├── components/
├── tasks/
└── main.py
```

### 4.2 模型传输

```bash
# 方法1：通过ADB传输
adb push ./runs/three_kingdoms_v1/weights/best.pt /sdcard/automation/models/three_kingdoms/v1.0/model.pt

# 方法2：通过网络传输
scp ./runs/three_kingdoms_v1/weights/best.pt termux@phone:/data/data/com.termux/files/home/automation/models/three_kingdoms/v1.0/model.pt

# 方法3：云存储中转
# 上传到云盘，然后在Termux中下载
```

### 4.3 数据库配置

```sql
-- 在项目数据库中添加模型配置
INSERT INTO object_detection_configs (
    config_id,
    app_id,
    object_type,
    yolo_model_path,
    class_names,
    confidence_threshold,
    nms_threshold,
    input_size,
    roi_filter,
    size_filter,
    created_at
) VALUES 
-- 元宝检测配置
('three_kingdoms_yuanbao_v1', 'three_kingdoms', '元宝',
 '/data/data/com.termux/files/home/automation/models/three_kingdoms/v1.0/model.pt',
 '["元宝", "银币", "道具箱", "按钮_确定"]',
 0.6, 0.4, '640x640', NULL, 
 '{"min_width": 20, "max_width": 200, "min_height": 20, "max_height": 200}',
 NOW()),

-- 银币检测配置
('three_kingdoms_yinbi_v1', 'three_kingdoms', '银币',
 '/data/data/com.termux/files/home/automation/models/three_kingdoms/v1.0/model.pt',
 '["元宝", "银币", "道具箱", "按钮_确定"]',
 0.5, 0.4, '640x640', NULL, NULL,
 NOW());
```

### 4.4 模型配置文件

```json
// models/three_kingdoms/v1.0/config.json
{
    "model_info": {
        "version": "1.0",
        "created_date": "2025-07-20",
        "framework": "ultralytics_yolov8n",
        "input_size": [640, 640],
        "classes": ["元宝", "银币", "道具箱", "按钮_确定"],
        "performance": {
            "mAP50": 0.89,
            "mAP50-95": 0.67,
            "inference_time_ms": 25
        }
    },
    "deployment_settings": {
        "default_confidence": 0.6,
        "default_nms": 0.4,
        "preferred_format": "pt",
        "fallback_format": "onnx"
    },
    "class_mapping": {
        "元宝": 0,
        "银币": 1,
        "道具箱": 2,
        "按钮_确定": 3
    }
}
```

## 五、使用示例

### 5.1 在任务中使用

```python
# tasks/three_kingdoms/yuanbao_collector.py
from core.base_classes import Task

class YuanbaoCollector(Task):
    def execute(self):
        # 获取屏幕识别器
        recognizer = self.get_module("ScreenRecognizer")
        device = self.get_module("DeviceController")
        
        # 检测所有元宝
        yuanbao_results = recognizer.detect_objects_yolo(
            app_id="three_kingdoms",
            object_type="元宝",
            max_detections=20
        )
        
        # 点击收集
        for detection in yuanbao_results:
            center_x, center_y = detection['center_point']
            confidence = detection['confidence']
            
            self.log(f"发现元宝 位置:({center_x}, {center_y}) 置信度:{confidence:.2f}")
            
            # 点击收集
            device.tap(center_x, center_y)
            device.wait(0.3)  # 等待动画
        
        self.log(f"收集完成，共收集 {len(yuanbao_results)} 个元宝")
        return len(yuanbao_results) > 0
```

### 5.2 调用示例

```python
# 在main.py或任务脚本中
from components.screen_recognizer import ScreenRecognizer
from components.device_controller import TermuxDeviceController

# 初始化
device = TermuxDeviceController()
recognizer = ScreenRecognizer(device, db_manager)

# 加载配置
recognizer.load_recognition_configs("three_kingdoms")

# 执行检测
results = recognizer.detect_objects_yolo(
    app_id="three_kingdoms",
    object_type="元宝"
)

print(f"检测到 {len(results)} 个元宝:")
for i, result in enumerate(results):
    print(f"  {i+1}. 位置: {result['center_point']}, 置信度: {result['confidence']:.2f}")
```

## 六、模型管理

### 6.1 版本管理

```bash
# 模型版本命名规范
models/three_kingdoms/
├── v1.0/          # 初始版本
├── v1.1/          # 增加新类别
├── v1.2/          # 优化精度
└── latest -> v1.2  # 软链接指向最新版本
```

### 6.2 性能监控

```python
# 在代码中添加性能监控
def monitor_model_performance():
    stats = recognizer.get_recognition_performance_stats("three_kingdoms")
    
    print(f"平均识别时间: {stats['avg_time_ms']:.1f}ms")
    print(f"缓存命中率: {stats['cache_hit_rate']:.1%}")
    print(f"总识别次数: {stats['total_recognitions']}")
```

### 6.3 模型更新流程

1. **训练新版本**（PC端）
2. **验证效果**
3. **导出模型文件**
4. **传输到Termux**
5. **更新数据库配置**
6. **测试运行**
7. **切换到新版本**

## 七、故障排除

### 7.1 常见问题

**模型加载失败**：
- 检查文件路径是否正确
- 确认文件权限
- 验证模型文件完整性

**检测精度不高**：
- 增加训练数据
- 调整置信度阈值
- 检查标注质量

**推理速度慢**：
- 使用ONNX格式
- 减小输入图像尺寸
- 考虑模型量化

### 7.2 性能优化

```python
# 优化建议
- 使用模型缓存（已实现）
- 批量检测多张图片
- 调整输入尺寸平衡精度和速度
- 考虑使用TensorRT（如果有GPU）
```

## 八、总结

通过本指南，你可以：
1. 在PC上训练专用的游戏物体检测模型
2. 将模型部署到Termux自动化项目中
3. 在游戏任务中使用YOLO检测功能
4. 管理和更新模型版本

模型部署后，系统会自动处理物体检测，你只需要调用相应的接口即可实现复杂的游戏自动化功能。