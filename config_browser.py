import os
import json
import configparser

class ConfigBrowser:
    """配置文件浏览器"""
    
    @staticmethod
    def list_config_files(root_dir='.'):
        """
        列出所有配置文件
        
        Args:
            root_dir: 搜索的根目录，默认为当前目录
        
        Returns:
            配置文件列表
        """
        config_files = []
        config_extensions = ['.json', '.cfg', '.ini', '.yaml', '.toml']
        config_dirs = ['config', 'tasks']
        
        for dir_name in config_dirs:
            search_dir = os.path.join(root_dir, dir_name)
            if not os.path.exists(search_dir):
                continue
            
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if any(file.endswith(ext) for ext in config_extensions):
                        config_files.append(os.path.join(root, file))
        
        # 添加根目录的配置文件
        for file in os.listdir(root_dir):
            if any(file.endswith(ext) for ext in config_extensions):
                config_files.append(os.path.join(root_dir, file))
        
        return config_files
    
    @staticmethod
    def read_config_file(file_path):
        """
        读取配置文件内容
        
        Args:
            file_path: 配置文件路径
        
        Returns:
            配置文件内容字典
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_ext == '.json':
                    return json.load(f)
                elif file_ext in ['.cfg', '.ini']:
                    config = configparser.ConfigParser()
                    config.read(file_path)
                    return {section: dict(config[section]) for section in config.sections()}
                else:
                    return {"content": f.read()}
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def browse_configs():
        """
        交互式浏览配置文件
        """
        config_files = ConfigBrowser.list_config_files()
        
        if not config_files:
            print("未找到任何配置文件")
            return
        
        print("找到以下配置文件:")
        for i, file in enumerate(config_files, 1):
            print(f"{i}. {file}")
        
        while True:
            try:
                choice = input("\n输入文件序号查看详细内容 (输入 'q' 退出): ")
                
                if choice.lower() == 'q':
                    break
                
                index = int(choice) - 1
                if 0 <= index < len(config_files):
                    file_path = config_files[index]
                    print(f"\n查看文件: {file_path}")
                    config_content = ConfigBrowser.read_config_file(file_path)
                    print(json.dumps(config_content, ensure_ascii=False, indent=2))
                else:
                    print("无效的序号")
            except ValueError:
                print("请输入有效的数字")

if __name__ == "__main__":
    ConfigBrowser.browse_configs()
