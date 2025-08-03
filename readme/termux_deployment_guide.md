# Android自动化项目 Termux 部署指南

## 前期准备

### 1. 安装 Termux
- 从 F-Droid 或 GitHub 下载安装 Termux
- 避免从 Google Play 安装（版本较旧）

### 2. 更新 Termux 包管理器
```bash
pkg update && pkg upgrade
```

## 环境配置

### 3. 安装基础依赖
```bash
# 安装 Python 和必要工具
pkg install python git curl wget openssh

# 安装文件管理器（可选）
pkg install tree

# 安装编译工具（某些Python包需要）
pkg install clang cmake make libjpeg-turbo-dev libpng-dev freetype-dev
```

### 4. 安装 Python 依赖包
```bash
# 安装基础科学计算库
pip install numpy opencv-python pillow

# 安装 OCR 相关
pip install pytesseract

# 安装数据库和其他依赖
pip install sqlite3 threading logging argparse importlib
```

### 5. 配置存储权限
```bash
# 允许 Termux 访问外部存储
termux-setup-storage
```

## 项目部署

### 6. 创建项目目录
```bash
# 进入home目录
cd ~

# 创建工作目录
mkdir automation_project
cd automation_project
```

### 7. 传输项目文件（三种方式选一）

#### 方式一：使用 Git（推荐）
```bash
# 如果项目在Git仓库中
git clone <你的仓库地址>
cd <项目名>
```

#### 方式二：使用 SSH/SCP
```bash
# 在电脑端传输到手机
# 首先在Termux中启动SSH服务
pkg install openssh
sshd

# 查看IP地址
ifconfig

# 在电脑端执行（替换IP地址）
scp -r /path/to/your/project user@<termux_ip>:~/automation_project/
```

#### 方式三：手动文件传输
```bash
# 将项目文件复制到 /storage/emulated/0/Download/
# 然后在 Termux 中复制
cp -r /storage/emulated/0/Download/安卓自动化2 ~/automation_project/
```

### 8. 设置项目结构
```bash
cd ~/automation_project/安卓自动化2

# 检查文件结构
tree -L 2

# 创建必要的目录（如果不存在）
mkdir -p logs temp screenshots
```

## 环境适配

### 9. 修改设备控制器
创建 Termux 专用的设备控制器：

```bash
# 编辑设备控制器
nano components/device_controller.py
```

需要替换原有的雷电模拟器控制代码为Termux原生控制：

```python
# 安装 Termux API
pkg install termux-api

# 在Python中使用
import subprocess

def take_screenshot(filename=None):
    """使用 Termux API 截图"""
    if filename:
        subprocess.run(['termux-camera-photo', filename])
    else:
        subprocess.run(['termux-camera-photo', '/tmp/screenshot.jpg'])

def tap(x, y):
    """使用输入事件模拟点击"""
    subprocess.run(['input', 'tap', str(x), str(y)])
```

### 10. 安装额外的 Termux 包
```bash
# 安装 Termux API（用于设备控制）
pkg install termux-api

# 安装输入控制工具
pkg install android-tools

# 测试API功能
termux-vibrate
termux-toast "Termux setup complete"
```

## 项目配置

### 11. 修改配置文件
```bash
# 编辑主配置
nano config.json

# 修改数据库路径为相对路径
# 修改日志路径
# 调整屏幕分辨率设置
```

### 12. 创建启动脚本
```bash
nano start.sh
```

内容：
```bash
#!/bin/bash
cd ~/automation_project/安卓自动化2
export PYTHONPATH=$PYTHONPATH:$(pwd)
python main.py --start
```

```bash
chmod +x start.sh
```

## 初步测试

### 13. 权限测试
```bash
# 测试基础功能
python -c "import cv2; print('OpenCV OK')"
python -c "import pytesseract; print('Tesseract OK')"
python -c "import sqlite3; print('SQLite OK')"
```

### 14. 数据库初始化
```bash
# 初始化数据库
python main.py --start
```

### 15. 组件测试
```bash
# 测试各个组件
python -c "
from components.device_controller import TermuxDeviceController
device = TermuxDeviceController()
print('Device controller test:', device.initialize())
"
```

### 16. 运行基础测试
```bash
# 列出可用任务
python main.py --list-tasks

# 创建测试任务
python main.py --init-task test_task
```

## 问题排查

### 17. 常见问题解决

#### Python 包安装失败
```bash
# 如果某些包无法安装，尝试：
pip install --no-cache-dir <package_name>

# 或者使用conda-forge
pkg install python-numpy  # 使用系统包
```

#### 权限问题
```bash
# 确保有执行权限
chmod +x *.py
chmod +x start.sh

# 检查存储权限
ls -la /storage/emulated/0/
```

#### 依赖问题
```bash
# 安装缺失的系统库
pkg install libxml2 libxslt libiconv

# 检查Python路径
which python
python --version
```

### 18. 性能优化配置
```bash
# 设置环境变量优化性能
echo 'export OMP_NUM_THREADS=4' >> ~/.bashrc
echo 'export OPENBLAS_NUM_THREADS=4' >> ~/.bashrc
source ~/.bashrc
```

## 日志和监控

### 19. 设置日志查看
```bash
# 实时查看日志
tail -f system.log

# 创建日志查看脚本
echo '#!/bin/bash
tail -f ~/automation_project/安卓自动化2/*.log' > ~/view_logs.sh
chmod +x ~/view_logs.sh
```

### 20. 系统资源监控
```bash
# 安装系统监控工具
pkg install htop

# 监控内存和CPU使用
htop
```

## 备份和清理

### 21. 创建备份脚本
```bash
nano backup.sh
```

内容：
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf ~/automation_backup_$DATE.tar.gz ~/automation_project/
echo "Backup created: automation_backup_$DATE.tar.gz"
```

### 22. 测试完成后清理
```bash
# 如果测试完成需要删除
cd ~
rm -rf automation_project/
pip uninstall opencv-python pillow pytesseract  # 卸载大包
```

## 注意事项

1. **设备兼容性**：原项目是为雷电模拟器设计的，需要大量修改才能在真实Android设备上运行
2. **权限限制**：Android系统的权限限制可能影响某些功能
3. **性能考虑**：手机CPU和内存有限，大型OpenCV操作可能较慢
4. **电池优化**：长时间运行会消耗大量电池
5. **Root权限**：某些高级功能可能需要Root权限

## 下一步计划

测试完成后，可以：
1. 评估哪些功能在Termux中可行
2. 确定需要重写的组件
3. 制定完整的移植方案
4. 设计新的Android原生控制接口