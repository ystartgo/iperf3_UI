import os
import sys
import subprocess
import signal
import platform

class IperfController:
    """控制iperf3命令的执行"""
    
    def __init__(self):
        self.process = None
        self.iperf_path = self._find_iperf_path()
    
    def _find_iperf_path(self):
        """查找iperf3可执行文件的路径"""
        # 首先检查当前目录和程序所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, "iperf3"),
            os.path.join(current_dir, "iperf3.exe"),
            "iperf3",  # 系统PATH中的iperf3
            "iperf3.exe"
        ]
        
        # 在Windows上，也检查Program Files目录
        if platform.system() == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            
            possible_paths.extend([
                os.path.join(program_files, "iperf3", "iperf3.exe"),
                os.path.join(program_files_x86, "iperf3", "iperf3.exe")
            ])
        
        # 尝试每个可能的路径
        for path in possible_paths:
            try:
                # 尝试运行iperf3 --version来检查是否可用
                subprocess.run([path, "--version"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               check=True)
                return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        # 如果找不到iperf3，返回默认值，后续会检查并提示用户
        return "iperf3"
    
    def run_iperf_command(self, params, callback=None):
        """運行 iperf 命令"""
        cmd = [self.iperf_path]
        
        if params["mode"] == "server":
            cmd.append("-s")
        else:  # client mode
            cmd.append("-c")
            cmd.append(params["host"])
        
        # 添加端口
        cmd.extend(["-p", str(params["port"])])
        
        # 添加時間
        cmd.extend(["-t", str(params["time"])])
        
        # 添加輸出格式
        if params.get("format") == "json":
            cmd.append("-J")
        
        # 添加間隔參數，使 iperf 每 0.5 秒輸出一次結果
        cmd.extend(["-i", "0.5"])
        
        # 添加並行連接數
        if params.get("parallel", 1) > 1:
            cmd.extend(["-P", str(params["parallel"])])
        
        # 添加雙向測試選項
        if params.get("bidirectional", False):
            # 嘗試使用 --bidir 參數（較新版本的 iperf3）
            try:
                test_cmd = [self.iperf_path, "--help"]
                help_output = subprocess.check_output(test_cmd, universal_newlines=True)
                if "--bidir" in help_output:
                    cmd.append("--bidir")
                else:
                    # 舊版本可能使用 -d 或 --dualtest
                    cmd.append("-d")
            except:
                # 如果無法檢查，預設使用 --bidir
                cmd.append("--bidir")
        
        # 添加其他參數
        if "bandwidth" in params:
            cmd.extend(["-b", str(params["bandwidth"])])
        
        # 打印命令
        print(f"Running command: {' '.join(cmd)}")
        
        # 運行命令
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 讀取輸出
            for line in iter(self.process.stdout.readline, ''):
                if callback:
                    callback(line.strip())
                if not line:
                    break
            
            self.process.wait()
        except Exception as e:
            if callback:
                callback(f"Error: {str(e)}")
    
    def stop_iperf(self):
        """停止正在运行的iperf进程"""
        if self.process:
            if platform.system() == "Windows":
                # Windows上使用taskkill强制终止进程
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
            else:
                # Linux/Mac上使用SIGTERM信号
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()  # 如果进程没有及时终止，强制杀死
            
            self.process = None