from core.base_classes import SystemModule
from core.interfaces import IDeviceController
import subprocess
import os
import time
import logging
from PIL import Image
import threading
import re
from typing import Tuple, Optional


class TermuxDeviceController(SystemModule, IDeviceController):
    """Termux环境下的Android设备控制器，增强版支持时间戳截图缓存"""
    
    def __init__(self, device_path="/dev/input/event1"):
        """初始化Termux设备控制器
        
        Args:
            device_path: 触摸设备路径，默认为 /dev/input/event1
        """
        super().__init__("TermuxDeviceController", "2.0.0")
        self.device_path = device_path
        self.screen_width = 0
        self.screen_height = 0
        self.density = 0
        self._lock = threading.Lock()
        self._has_root = False
        
        # 使用项目根目录下的screenshots文件夹，确保其他模块可以访问
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._screenshot_dir = os.path.join(project_root, "screenshots")
        self._screenshot_path = os.path.join(self._screenshot_dir, "current_screenshot.png")
        
        # 时间戳截图相关
        self._timestamped_screenshots = {}  # {timestamp: filepath}
        self._max_timestamp_cache = 10  # 最多保留10张带时间戳的截图
        
    def _execute_command(self, cmd, use_root=False, timeout=10):
        """执行命令
        
        Args:
            cmd: 要执行的命令
            use_root: 是否使用root权限
            timeout: 超时时间
            
        Returns:
            tuple: (success, output, error)
        """
        try:
            if use_root and self._has_root:
                if isinstance(cmd, str):
                    cmd = f"su -c '{cmd}'"
                else:
                    cmd = ["su", "-c", " ".join(cmd)]
            
            result = subprocess.run(
                cmd, 
                shell=True if isinstance(cmd, str) else False,
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            return (result.returncode == 0, result.stdout, result.stderr)
            
        except subprocess.TimeoutExpired:
            self.log_error(f"命令执行超时: {cmd}")
            return (False, "", "Timeout")
        except Exception as e:
            self.log_error(f"命令执行失败: {cmd}, 错误: {str(e)}")
            return (False, "", str(e))
    
    def _get_optimal_screenshot_directory(self) -> str:
        """获取最佳的截图存储目录"""
        if self._screenshot_dir:
            return self._screenshot_dir
        
        # 按优先级尝试不同路径
        candidate_paths = [
            "/data/data/com.termux/files/home/automation/screenshots",  # Termux应用内部
            "/storage/emulated/0/termux_automation/screenshots",        # 外部存储
            "/sdcard/termux_automation/screenshots",                    # 传统sdcard路径
            "/data/local/tmp/screenshots",                              # 临时目录
            "/tmp/screenshots"                                          # 系统临时目录
        ]
        
        for path in candidate_paths:
            if self._test_directory_access(path):
                self.log_info(f"选择截图目录: {path}")
                return path
        
        # 如果都不可用，使用当前工作目录
        fallback_path = os.path.join(os.getcwd(), "screenshots")
        self.log_warning(f"使用备用截图目录: {fallback_path}")
        return fallback_path
    
    def _test_directory_access(self, directory_path: str) -> bool:
        """测试目录的读写权限
        
        Args:
            directory_path: 目录路径
            
        Returns:
            bool: 是否可以读写
        """
        try:
            # 尝试创建目录
            success, _, _ = self._execute_command(f"mkdir -p {directory_path}", use_root=self._has_root)
            if not success:
                return False
            
            # 测试写入权限
            test_file = os.path.join(directory_path, "test_write.tmp")
            success, _, _ = self._execute_command(f"touch {test_file}", use_root=self._has_root)
            if not success:
                return False
            
            # 测试读取权限
            success, _, _ = self._execute_command(f"ls {test_file}", use_root=self._has_root)
            if not success:
                return False
            
            # 清理测试文件
            self._execute_command(f"rm -f {test_file}", use_root=self._has_root)
            
            return True
            
        except Exception as e:
            self.log_debug(f"目录访问测试失败 {directory_path}: {str(e)}")
            return False
    
    def _check_root_access(self) -> bool:
        """检查root权限"""
        success, output, error = self._execute_command("whoami", use_root=True)
        if success and "root" in output:
            self.log_info("Root权限验证成功")
            return True
        else:
            self.log_warning("Root权限验证失败，某些功能可能受限")
            return False
    
    def _get_screen_info(self) -> bool:
        """获取屏幕信息"""
        try:
            # 获取屏幕分辨率
            success, output, _ = self._execute_command("wm size")
            if success:
                # 解析输出: Physical size: 1080x2340
                size_match = re.search(r'(\d+)x(\d+)', output)
                if size_match:
                    self.screen_width = int(size_match.group(1))
                    self.screen_height = int(size_match.group(2))
            
            # 获取屏幕密度
            success, output, _ = self._execute_command("wm density")
            if success:
                # 解析输出: Physical density: 420
                density_match = re.search(r'density:\s*(\d+)', output)
                if density_match:
                    self.density = int(density_match.group(1))
            
            if self.screen_width > 0 and self.screen_height > 0:
                self.log_info(f"屏幕信息: {self.screen_width}x{self.screen_height}, 密度: {self.density}")
                return True
            else:
                self.log_error("无法获取屏幕尺寸信息")
                return False
                
        except Exception as e:
            self.log_error(f"获取屏幕信息失败: {str(e)}")
            return False
    
    def _check_required_tools(self) -> bool:
        """检查必要的工具是否可用"""
        required_tools = ["input", "screencap", "am", "wm"]
        missing_tools = []
        
        for tool in required_tools:
            success, _, _ = self._execute_command(f"which {tool}")
            if not success:
                missing_tools.append(tool)
        
        if missing_tools:
            self.log_error(f"缺少必要工具: {', '.join(missing_tools)}")
            return False
        
        self.log_info("所有必要工具检查通过")
        return True

    def initialize(self) -> bool:
        """初始化设备控制器"""
        try:
            self.log_info("开始初始化Termux设备控制器...")
            
            # 检查root权限
            self._has_root = self._check_root_access()
            
            # 检查必要工具
            if not self._check_required_tools():
                return False
            
            # 获取屏幕信息
            if not self._get_screen_info():
                return False
            
            # 创建截图目录
            os.makedirs(self._screenshot_dir, exist_ok=True)
            self.log_info(f"截图将保存到: {self._screenshot_path}")
            
            super().initialize()
            self.log_info("Termux设备控制器初始化成功")
            return True
            
        except Exception as e:
            self.log_error(f"设备初始化失败: {str(e)}")
            return False

    def take_screenshot(self, filename=None):
        """截取屏幕（兼容原接口）"""
        with self._lock:
            try:
                # 使用screencap命令截图到项目目录
                cmd = f"screencap -p {self._screenshot_path}"
                success, _, error = self._execute_command(cmd, use_root=True)
                
                if not success:
                    self.log_error(f"截图失败: {error}")
                    return None if filename is None else False
                
                if filename is None:
                    # 返回Image对象
                    try:
                        img = Image.open(self._screenshot_path)
                        self.log_info(f"截图成功，尺寸: {img.size}")
                        return img
                    except Exception as e:
                        self.log_error(f"无法读取截图文件: {str(e)}")
                        return None
                else:
                    # 保存到指定位置
                    try:
                        os.makedirs(os.path.dirname(filename), exist_ok=True)
                        import shutil
                        shutil.copy2(self._screenshot_path, filename)
                        self.log_info(f"截图已保存到: {filename}")
                        return True
                        
                    except Exception as e:
                        self.log_error(f"无法保存截图到: {filename}, 错误: {str(e)}")
                        return False
                    
            except Exception as e:
                self.log_error(f"截图操作失败: {str(e)}")
                return None if filename is None else False

    def get_screenshot_with_timestamp(self) -> Tuple[Optional[Image.Image], float]:
        """获取带时间戳的截图
        
        Returns:
            tuple: (PIL.Image对象, 时间戳) 或 (None, 0.0)
        """
        with self._lock:
            try:
                # 生成时间戳
                timestamp = time.time()
                timestamp_str = f"{timestamp:.6f}".replace('.', '_')
                
                # 生成带时间戳的文件名
                timestamped_filename = f"screenshot_{timestamp_str}.png"
                timestamped_path = os.path.join(self._screenshot_dir, timestamped_filename)
                
                # 执行截图
                cmd = f"screencap -p {timestamped_path}"
                success, _, error = self._execute_command(cmd, use_root=True)
                
                if not success:
                    self.log_error(f"时间戳截图失败: {error}")
                    return None, 0.0
                
                # 读取图像
                try:
                    img = Image.open(timestamped_path)
                    
                    # 添加到时间戳缓存
                    self._timestamped_screenshots[timestamp] = timestamped_path
                    
                    # 清理过期的时间戳截图
                    self._cleanup_timestamped_screenshots()
                    
                    # 同时更新当前截图（保持兼容性）
                    import shutil
                    shutil.copy2(timestamped_path, self._screenshot_path)
                    
                    self.log_info(f"时间戳截图成功: {timestamp}, 尺寸: {img.size}")
                    return img, timestamp
                    
                except Exception as e:
                    self.log_error(f"无法读取时间戳截图文件: {str(e)}")
                    return None, 0.0
                    
            except Exception as e:
                self.log_error(f"时间戳截图操作失败: {str(e)}")
                return None, 0.0

    def get_screenshot_by_timestamp(self, timestamp: float, tolerance: float = 1.0) -> Optional[Image.Image]:
        """根据时间戳获取截图
        
        Args:
            timestamp: 目标时间戳
            tolerance: 时间容差（秒）
            
        Returns:
            PIL.Image对象或None
        """
        try:
            # 查找最接近的时间戳
            best_match = None
            min_diff = float('inf')
            
            for cached_timestamp, filepath in self._timestamped_screenshots.items():
                time_diff = abs(cached_timestamp - timestamp)
                if time_diff < min_diff and time_diff <= tolerance:
                    min_diff = time_diff
                    best_match = filepath
            
            if best_match and os.path.exists(best_match):
                img = Image.open(best_match)
                self.log_info(f"找到匹配的时间戳截图，时间差: {min_diff:.3f}秒")
                return img
            else:
                self.log_warning(f"未找到匹配的时间戳截图: {timestamp}")
                return None
                
        except Exception as e:
            self.log_error(f"根据时间戳获取截图失败: {str(e)}")
            return None

    def _cleanup_timestamped_screenshots(self):
        """清理过期的时间戳截图"""
        try:
            # 如果超过最大缓存数量，删除最旧的
            while len(self._timestamped_screenshots) > self._max_timestamp_cache:
                oldest_timestamp = min(self._timestamped_screenshots.keys())
                oldest_path = self._timestamped_screenshots[oldest_timestamp]
                
                # 删除文件
                if os.path.exists(oldest_path):
                    os.remove(oldest_path)
                
                # 从缓存中移除
                del self._timestamped_screenshots[oldest_timestamp]
                
                self.log_debug(f"清理过期时间戳截图: {oldest_timestamp}")
                
        except Exception as e:
            self.log_error(f"清理时间戳截图失败: {str(e)}")

    def get_timestamped_screenshots_info(self) -> dict:
        """获取时间戳截图信息"""
        return {
            'cached_count': len(self._timestamped_screenshots),
            'max_cache_size': self._max_timestamp_cache,
            'timestamps': list(self._timestamped_screenshots.keys()),
            'cache_dir': self._screenshot_dir
        }

    def clear_timestamped_cache(self):
        """清空时间戳截图缓存"""
        try:
            # 删除所有时间戳截图文件
            for filepath in self._timestamped_screenshots.values():
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            # 清空缓存字典
            self._timestamped_screenshots.clear()
            
            self.log_info("时间戳截图缓存已清空")
            
        except Exception as e:
            self.log_error(f"清空时间戳截图缓存失败: {str(e)}")

    def tap(self, x, y) -> bool:
        """点击屏幕指定坐标"""
        with self._lock:
            try:
                cmd = f"input tap {x} {y}"
                success, _, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"点击坐标: ({x}, {y})")
                    return True
                else:
                    self.log_error(f"点击失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"点击操作失败: {str(e)}")
                return False

    def swipe(self, x1, y1, x2, y2, duration=300) -> bool:
        """滑动屏幕"""
        with self._lock:
            try:
                cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
                success, _, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"滑动: ({x1},{y1}) -> ({x2},{y2}), 持续{duration}ms")
                    return True
                else:
                    self.log_error(f"滑动失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"滑动操作失败: {str(e)}")
                return False

    def input_text(self, text) -> bool:
        """输入文本"""
        with self._lock:
            try:
                # 转义特殊字符
                escaped_text = text.replace("'", "\\'").replace('"', '\\"').replace(' ', '%s')
                cmd = f"input text '{escaped_text}'"
                success, _, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"输入文本: {text}")
                    return True
                else:
                    self.log_error(f"文本输入失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"文本输入操作失败: {str(e)}")
                return False

    def press_key(self, keycode) -> bool:
        """按下指定按键"""
        with self._lock:
            try:
                cmd = f"input keyevent {keycode}"
                success, _, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"按键: {keycode}")
                    return True
                else:
                    self.log_error(f"按键失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"按键操作失败: {str(e)}")
                return False

    def back(self) -> bool:
        """按下返回键"""
        return self.press_key(4)  # KEYCODE_BACK

    def home(self) -> bool:
        """按下Home键"""
        return self.press_key(3)  # KEYCODE_HOME

    def start_app(self, package_name) -> bool:
        """启动应用程序"""
        with self._lock:
            try:
                # 先尝试获取应用的主Activity
                cmd = f"pm dump {package_name} | grep -A 1 MAIN"
                success, output, _ = self._execute_command(cmd)
                
                if success and output:
                    # 解析主Activity
                    lines = output.split('\n')
                    activity = None
                    for line in lines:
                        if 'android.intent.category.LAUNCHER' in line:
                            # 从上一行获取activity名称
                            prev_line_idx = lines.index(line) - 1
                            if prev_line_idx >= 0:
                                activity_match = re.search(r'(\S+)/(\S+)', lines[prev_line_idx])
                                if activity_match:
                                    activity = activity_match.group(2)
                                    break
                
                # 构建启动命令
                if activity:
                    cmd = f"am start -n {package_name}/{activity}"
                else:
                    # 备用方案：使用monkey启动
                    cmd = f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
                
                success, output, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"已启动应用: {package_name}")
                    time.sleep(2)  # 等待应用启动
                    return True
                else:
                    self.log_error(f"应用启动失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"应用启动操作失败: {str(e)}")
                return False

    def stop_app(self, package_name) -> bool:
        """停止应用程序"""
        with self._lock:
            try:
                cmd = f"am force-stop {package_name}"
                success, _, error = self._execute_command(cmd, use_root=self._has_root)
                
                if success:
                    self.log_info(f"已停止应用: {package_name}")
                    return True
                else:
                    self.log_error(f"应用停止失败: {error}")
                    return False
                    
            except Exception as e:
                self.log_error(f"应用停止操作失败: {str(e)}")
                return False

    def wait(self, seconds) -> None:
        """等待指定秒数"""
        time.sleep(seconds)
    
    def get_current_app(self) -> str:
        """获取当前前台应用包名"""
        try:
            # Android 8.0+ 使用 dumpsys activity activities
            cmd = "dumpsys activity activities | grep mResumedActivity"
            success, output, _ = self._execute_command(cmd)
            
            if success and output:
                # 解析输出获取包名
                package_match = re.search(r'ActivityRecord{[^}]+\s+(\S+)/(\S+)', output)
                if package_match:
                    return package_match.group(1)
            
            # 备用方案
            cmd = "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
            success, output, _ = self._execute_command(cmd)
            
            if success and output:
                package_match = re.search(r'(\w+\.\w+(?:\.\w+)*)', output)
                if package_match:
                    return package_match.group(1)
            
            return ""
            
        except Exception as e:
            self.log_error(f"获取当前应用失败: {str(e)}")
            return ""
    
    def is_app_running(self, package_name) -> bool:
        """检查应用是否正在运行"""
        try:
            cmd = f"ps | grep {package_name}"
            success, output, _ = self._execute_command(cmd)
            return success and package_name in output
            
        except Exception as e:
            self.log_error(f"检查应用状态失败: {str(e)}")
            return False
    
    def get_device_info(self) -> dict:
        """获取设备信息"""
        info = {
            'screen_width': self.screen_width,
            'screen_height': self.screen_height,
            'density': self.density,
            'has_root': self._has_root,
            'android_version': '',
            'device_model': ''
        }
        
        try:
            # 获取Android版本
            success, output, _ = self._execute_command("getprop ro.build.version.release")
            if success:
                info['android_version'] = output.strip()
            
            # 获取设备型号
            success, output, _ = self._execute_command("getprop ro.product.model")
            if success:
                info['device_model'] = output.strip()
                
        except Exception as e:
            self.log_error(f"获取设备信息失败: {str(e)}")
        
        return info
    
    def get_screenshot_path(self) -> str:
        """获取当前截图文件路径，供其他模块使用
        
        Returns:
            str: 截图文件的完整路径
        """
        return self._screenshot_path
    
    def get_screenshot_directory(self) -> str:
        """获取截图存储目录，供其他模块使用
        
        Returns:
            str: 截图存储目录路径
        """
        return self._screenshot_dir