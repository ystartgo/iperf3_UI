import os
import json
import platform
from datetime import datetime

class ConfigManager:
    """配置管理器，处理配置文件的加载和保存"""
    
    def __init__(self):
        self.config_dir = self.get_config_dir()
        self.config_file = os.path.join(self.config_dir, "iperf_gui_config.json")
        self.ensure_config_dir()
        
    def get_config_dir(self):
        """获取配置文件目录"""
        system = platform.system()
        home_dir = os.path.expanduser("~")
        
        if system == "Windows":
            return os.path.join(home_dir, "AppData", "Local", "IperfGUI")
        elif system == "Darwin":  # macOS
            return os.path.join(home_dir, "Library", "Application Support", "IperfGUI")
        else:  # Linux and others
            return os.path.join(home_dir, ".config", "iperf-gui")
    
    def ensure_config_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
    
    def get_results_dir(self):
        """获取结果文件保存目录"""
        results_dir = os.path.join(self.config_dir, "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir, exist_ok=True)
        return results_dir
    
    def load_config(self):
        """加载配置文件"""
        default_config = {
            "language": "zh_tw",
            "last_used_params": {
                "mode": "client",
                "host": "localhost",
                "port": 5201,
                "time": 10,
                "bandwidth": "0",
                "parallel": 1,
                "interval": 1.0,
                "udp": False,
                "reverse": False,
                "format": "normal",
                "extra_params": ""
            },
            "auto_save_results": True
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # 合并默认配置和加载的配置
                    for key in default_config:
                        if key not in config:
                            config[key] = default_config[key]
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            return default_config
    
    def save_config(self, config):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_timestamp(self):
        """获取当前时间戳"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def get_result_file_paths(self, test_type=""):
        """获取结果文件路径"""
        timestamp = self.get_timestamp()
        results_dir = self.get_results_dir()
        
        # 创建以日期为名称的子目录
        date_dir = os.path.join(results_dir, datetime.now().strftime("%Y%m%d"))
        if not os.path.exists(date_dir):
            os.makedirs(date_dir, exist_ok=True)
        
        prefix = f"iperf_{test_type}_" if test_type else "iperf_"
        
        text_path = os.path.join(date_dir, f"{prefix}{timestamp}.txt")
        json_path = os.path.join(date_dir, f"{prefix}{timestamp}.json")
        graph_path = os.path.join(date_dir, f"{prefix}{timestamp}.png")
        
        return text_path, json_path, graph_path