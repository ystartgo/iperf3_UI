import sys
import os
import argparse
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from iperf_gui import IperfGUI

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='iperf3 GUI - 网络性能测试工具')
    parser.add_argument('--lang', choices=['zh_tw', 'en', 'zh_cn'], 
                        help='设置界面语言 (zh_tw: 繁體中文, en: English, zh_cn: 简体中文)')
    parser.add_argument('--server', action='store_true', help='以服务器模式启动')
    parser.add_argument('--client', metavar='HOST', help='以客户端模式启动并连接到指定主机')
    parser.add_argument('--port', type=int, help='指定端口号')
    parser.add_argument('--time', type=int, help='测试持续时间(秒)')
    parser.add_argument('--parallel', type=int, help='並行連接數量')
    parser.add_argument('--bidir', action='store_true', help='啟用雙向測試')
    
    return parser.parse_args()

def main():
    # 解析命令行参数
    args = parse_args()
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格，在所有平台上看起来一致
    
    # 创建主窗口
    main_window = IperfGUI()
    
    # 应用命令行参数
    if args.lang:
        lang_index = {'zh_tw': 0, 'en': 1, 'zh_cn': 2}
        main_window.lang_combo.setCurrentIndex(lang_index[args.lang])
    
    if args.server:
        main_window.server_radio.setChecked(True)
    
    if args.client:
        main_window.client_radio.setChecked(True)
        main_window.host_input.setText(args.client)
    
    if args.port:
        main_window.port_input.setValue(args.port)
    
    if args.time:
        main_window.time_input.setValue(args.time)
    
    # 處理新增的命令行參數
    if args.parallel:
        main_window.parallel_input.setValue(args.parallel)
    
    if args.bidir:
        main_window.bidirectional_check.setChecked(True)
    
    main_window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()