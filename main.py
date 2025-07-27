import importlib
import os
import sys
import argparse
from data.database_manager import DatabaseManager
from data.config import Config
from core.base_classes import SystemKernel
from schedulers.task_manager import TaskManager
from schedulers.account_service import AccountService
from schedulers.app_scheduler import AppScheduler

# 修复导入：使用新的TermuxDeviceController
from components.device_controller import TermuxDeviceController
from components.screen_recognizer import ScreenRecognizer
from components.state_manager import StateManager

# 在initialize_task_structure函数中添加以下更新

def initialize_task_structure(task_name):
    """初始化任务目录结构
    Args:
        task_name: 任务名称
    Returns:
        是否成功
    """
    try:
        # 创建任务基本目录结构
        task_dir = f"tasks/{task_name.lower()}"
        directories = [
            task_dir,
            f"{task_dir}/db",
            f"{task_dir}/config",
            f"{task_dir}/templates",
            f"{task_dir}/sub_tasks",
            f"{task_dir}/config_plugins"  # 添加配置插件目录
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            
        # 创建基本文件
        with open(f"{task_dir}/__init__.py", 'w', encoding='utf-8') as f:
            f.write(f"# {task_name} 任务模块\n")
            
        # 创建配置插件模块
        with open(f"{task_dir}/config_plugins/__init__.py", 'w', encoding='utf-8') as f:
            f.write(f"""# {task_name} 配置插件模块

from core.interfaces import IConfigParserPlugin

# 在这里定义任务特定的配置解析器插件
"""
            )
            
        # 创建示例插件文件
        custom_plugin_template = f"""# {task_name} 自定义配置插件示例

import re
import sqlite3
from core.interfaces import IConfigParserPlugin

class CustomConfigPlugin(IConfigParserPlugin):
    \"\"\"自定义配置解析器插件示例\"\"\"
    
    def get_name(self) -> str:
        \"\"\"获取解析器名称\"\"\"
        return "custom"
    
    def parse(self, content: str, task_name: str = None, db_path: str = None) -> bool:
        \"\"\"解析自定义配置
        
        Args:
            content: 配置内容
            task_name: 可选的任务名称
            db_path: 可选的数据库路径
            
        Returns:
            是否成功
        \"\"\"
        # 实现自定义解析逻辑
        pass
"""
        with open(f"{task_dir}/config_plugins/custom_plugin.py", 'w', encoding='utf-8') as f:
            f.write(custom_plugin_template)
            
        # 创建主任务模板
        task_template = f'''
"""
{task_name} 主任务实现
"""

from schedulers.task_base import GameTask

class {task_name.capitalize()}Task(GameTask):
    """
    {task_name} 自动化任务
    """
    
    def __init__(self, task_id, name, app_id, parent_id=None):
        super().__init__(task_id, name, app_id, parent_id, "{task_name.lower()}")
    
    def execute(self):
        # 初始化任务
        if not self.initialize():
            return False
            
        # TODO: 实现任务逻辑
        
        return True
'''
        with open(f"{task_dir}/main_task.py", 'w', encoding='utf-8') as f:
            f.write(task_template.strip())
            
        # 创建配置示例
        coordinates_example = '''# 坐标配置示例
[登录]
开始按钮 = 640, 400, 开始游戏按钮
账号按钮 = 700, 50, 账号设置按钮

[大厅]
经典场 = 302, 408, 进入经典场按钮
菜单按钮 = 1067, 477, 打开菜单按钮

[全局]
返回按钮 = 1237, 58, 返回上一级按钮
'''
        with open(f"{task_dir}/config/coordinates.cfg", 'w', encoding='utf-8') as f:
            f.write(coordinates_example)
            
        # 创建通用分节配置示例
        section_example = '''# 通用分节配置示例
[第一章]
关卡: 1, 2, 3
难度: 普通, 困难

[第二章]
关卡: 1, 2
难度: 普通
'''
        with open(f"{task_dir}/config/sections.cfg", 'w', encoding='utf-8') as f:
            f.write(section_example)
            
        # 创建README
        readme = f'''# {task_name} 自动化任务

## 目录结构
- main_task.py: 主任务实现
- sub_tasks/: 子任务模块
- config/: 配置文件
- db/: 任务数据库
- templates/: 模板图像
- config_plugins/: 配置解析器插件

## 配置文件
- coordinates.cfg: 坐标配置
- sections.cfg: 分节配置

## 配置插件
任务可以定义自己的配置解析器插件，存放在config_plugins目录中。

## 使用方法
1. 编辑配置文件
2. 导入配置: `python -m tasks.{task_name.lower()}.import_config`
3. 运行任务: `python -m tasks.{task_name.lower()}.run_task`
'''
        with open(f"{task_dir}/README.md", 'w', encoding='utf-8') as f:
            f.write(readme)
            
        print(f"任务 {task_name} 目录结构初始化完成")
        return True
        
    except Exception as e:
        print(f"初始化任务结构失败: {str(e)}")
        return False

def list_available_tasks():
    """列出所有可用的任务"""
    try:
        tasks_dir = "tasks"
        if not os.path.exists(tasks_dir):
            print("任务目录不存在")
            return
            
        tasks = []
        for item in os.listdir(tasks_dir):
            task_dir = os.path.join(tasks_dir, item)
            if os.path.isdir(task_dir) and not item.startswith('__'):
                # 检查是否有main_task.py文件
                if os.path.exists(os.path.join(task_dir, "main_task.py")):
                    tasks.append(item)
        
        if tasks:
            print("可用的任务:")
            for i, task in enumerate(tasks, 1):
                print(f"{i}. {task}")
        else:
            print("没有找到可用的任务")
            
    except Exception as e:
        print(f"列出任务失败: {str(e)}")

# 在import_task_configs函数中添加下面的代码来支持插件系统

def import_task_configs(task_name):
    """导入任务配置
    Args:
        task_name: 任务名称
    """
    try:
        # 导入必要模块
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from data.database_manager import DatabaseManager
        from data.config_parser import ConfigParser
        
        # 创建配置解析器
        db_manager = DatabaseManager()
        config_parser = ConfigParser(db_manager)
        
        # 加载任务特定的配置插件
        config_parser.load_plugins_from_task(task_name)
        
        # 注册基础插件
        from data.config_plugins import CoordinatesConfigPlugin, GeneralSectionPlugin
        config_parser.register_plugin(CoordinatesConfigPlugin())
        config_parser.register_plugin(GeneralSectionPlugin())
        
        # 尝试从任务模块导入CampaignConfigPlugin
        try:
            campaign_plugin_module = f"tasks.{task_name}.config_plugins"
            campaign_plugin = importlib.import_module(campaign_plugin_module)
            if hasattr(campaign_plugin, 'CampaignConfigPlugin'):
                config_parser.register_plugin(campaign_plugin.CampaignConfigPlugin())
        except ImportError:
            # 如果没有特定任务的插件，使用默认插件
            from data.config_plugins import CampaignConfigPlugin
            config_parser.register_plugin(CampaignConfigPlugin())
        
        # 配置文件目录
        config_dir = f"tasks/{task_name}/config"
        if not os.path.exists(config_dir):
            print(f"配置目录不存在: {config_dir}")
            return
            
        # 查找并导入所有配置文件
        imported = False
        for filename in os.listdir(config_dir):
            if filename.endswith('.cfg'):
                file_path = os.path.join(config_dir, filename)
                print(f"导入配置: {file_path}")
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 自动检测格式并解析
                result = config_parser.detect_format_and_parse(content, task_name)
                
                if result["success"]:
                    print(f"成功导入 {filename} (格式: {result['format']})")
                    imported = True
                else:
                    print(f"导入 {filename} 失败: {result.get('error', '未知错误')}")
        
        if imported:
            print(f"任务 {task_name} 配置导入完成")
        else:
            print(f"没有找到配置文件")
            
    except Exception as e:
        print(f"导入配置失败: {str(e)}")

def start_system():
    """启动系统"""
    try:
        # 初始化配置
        config = Config()

        # 初始化数据库（会自动创建数据库文件）
        db_path = config.get('database.path', 'automation.db')
        db_manager = DatabaseManager(db_path=db_path)

        # 修改：使用新的TermuxDeviceController
        device = TermuxDeviceController()

        # 修改：传入数据库管理器到屏幕识别器
        recognizer = ScreenRecognizer(device, db_manager)

        # 初始化任务管理器
        task_manager = TaskManager(db_manager)

        # 初始化账号服务
        account_service = AccountService(db_manager)

        # 初始化状态管理器
        state_manager = StateManager(db_manager, recognizer)

        # 初始化应用调度器
        app_scheduler = AppScheduler(db_manager, task_manager, account_service, device)

        # 创建系统内核并注册所有模块
        kernel = SystemKernel()
        kernel.register_module(db_manager)
        kernel.register_module(device)
        kernel.register_module(recognizer)
        kernel.register_module(task_manager)
        kernel.register_module(account_service)
        kernel.register_module(state_manager)
        kernel.register_module(app_scheduler)

        # 启动系统
        if kernel.start():
            print("系统已成功启动")
            return kernel
        else:
            print("系统启动失败")
            return None
    except Exception as e:
        print(f"启动系统失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def register_and_run_task(task_name, app_id):
    """注册并运行指定任务
    Args:
        task_name: 任务名称
        app_id: 应用ID
    """
    try:
        # 导入必要模块
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # 启动系统
        kernel = start_system()
        if not kernel:
            return
            
        # 获取任务管理器
        task_manager = kernel.get_module("TaskManager")
        if not task_manager:
            print("获取任务管理器失败")
            return
            
        # 导入任务状态
        state_manager = kernel.get_module("StateManager")
        if state_manager:
            if hasattr(state_manager, "load_states_from_task"):
                state_manager.load_states_from_task(task_name, app_id)
                print(f"已从任务 {task_name} 加载状态配置")
            
        # 尝试导入并注册任务
        task_module = f"tasks.{task_name}.main_task"
        task_class = f"{task_name.capitalize()}Task"
        full_path = f"{task_module}.{task_class}"
        
        print(f"尝试注册任务: {full_path}")
        print(f"尝试获取类: {task_class}")
        print(f"完整路径: {full_path}")
        
        # 注册任务
        task_config = {
            "name": f"{task_name} 自动任务",
            "app_id": app_id,
            "type": "daily",
            "priority": 5,
            "description": f"{task_name} 游戏自动化任务"
        }
        
        # 使用反射方式注册任务
        if hasattr(task_manager, "register_task_from_module"):
            print("使用 register_task_from_module 方法")
            task_id = task_manager.register_task_from_module(full_path, task_config)
        else:
            # 尝试传统方式
            try:
                module_parts = full_path.split('.')
                module_name = '.'.join(module_parts[:-1])
                class_name = module_parts[-1]
                
                module = __import__(module_name, fromlist=[class_name])
                task_class = getattr(module, class_name)
                
                task_id = task_manager.register_task(task_class, task_config)
            except Exception as e:
                print(f"导入任务类失败: {str(e)}")
                return
        
        if not task_id:
            print("注册任务失败")
            return
            
        print(f"任务已注册，ID: {task_id}")
        
        # 执行任务
        print(f"执行任务 {task_id}")
        if task_manager.execute_task(task_id):
            print("任务执行成功")
        else:
            print("任务执行失败")
            
    except Exception as e:
        print(f"注册并运行任务失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="自动化系统")
    parser.add_argument('--init-task', help='初始化任务目录结构')
    parser.add_argument('--list-tasks', action='store_true', help='列出所有可用任务')
    parser.add_argument('--import-config', help='导入指定任务的配置')
    parser.add_argument('--run-task', nargs=2, metavar=('TASK_NAME', 'APP_ID'), help='运行指定任务')
    parser.add_argument('--start', action='store_true', help='启动系统')
    
    args = parser.parse_args()
    
    if args.init_task:
        initialize_task_structure(args.init_task)
    elif args.list_tasks:
        list_available_tasks()
    elif args.import_config:
        import_task_configs(args.import_config)
    elif args.run_task:
        register_and_run_task(args.run_task[0], args.run_task[1])
    elif args.start:
        start_system()
    else:
        # 默认启动系统
        start_system()
