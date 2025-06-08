#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iperf GUI - A graphical user interface for iperf3 network testing tool
Copyright (C) 2025 startgo@yia.app

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import os
import threading
import json
import time
import math
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, 
                            QTabWidget, QTextEdit, QFileDialog, QMessageBox,
                            QGroupBox, QFormLayout, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSettings, QTimer
from PyQt5.QtGui import QFont, QIcon, QDesktopServices
from PyQt5.QtCore import QUrl

from iperf_controller import IperfController
from graph_view import GraphView
from language_resources import LanguageResources
from config_manager import ConfigManager

class IperfWorker(QThread):
    """用于在后台运行iperf3的线程"""
    output_received = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, controller, params):
        super().__init__()
        self.controller = controller
        self.params = params
        
    def run(self):
        self.controller.run_iperf_command(self.params, 
                                          callback=lambda line: self.output_received.emit(line))
        self.finished.emit()

class PingWorker(QThread):
    """用於在後台運行 ping 的線程"""
    output_received = pyqtSignal(str)
    ping_result = pyqtSignal(float)  # 發送 ping 延遲結果 (ms)
    finished = pyqtSignal()
    
    def __init__(self, host, count=None):
        super().__init__()
        self.host = host  # 可以是域名或 IP 地址
        self.count = count  # None 表示持續 ping
        self.running = True
    
    def run(self):
        import subprocess
        import re
        
        # 根據操作系統選擇 ping 命令
        if sys.platform == "win32":
            # Windows 命令格式
            if self.count is None:
                cmd = ["ping", self.host, "-t"]  # 持續 ping
            else:
                cmd = ["ping", self.host, "-n", str(self.count)]
            
            # 繁體中文 Windows 的輸出格式: 回覆自 8.8.8.8: 位元組=32 時間=5ms TTL=116
            pattern = r"時間=(\d+)ms"
        else:  # Linux/Mac
            # Linux/Mac 命令格式
            if self.count is None:
                cmd = ["ping", self.host]  # 持續 ping
            else:
                cmd = ["ping", "-c", str(self.count), self.host]
            pattern = r"time=([\d\.]+) ms"
        
        self.output_received.emit(f"執行命令: {' '.join(cmd)}")
        
        try:
            # 啟動 ping 進程，使用較大的緩衝區
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行緩衝
                universal_newlines=True
            )
            
            # 讀取輸出
            while self.running:
                line = process.stdout.readline()
                if not line:
                    # 檢查是否有錯誤輸出
                    error = process.stderr.readline()
                    if error:
                        self.output_received.emit(f"錯誤: {error.strip()}")
                    break
                
                self.output_received.emit(line.strip())
                
                # 解析 ping 時間
                match = re.search(pattern, line)
                if match:
                    try:
                        ping_time = float(match.group(1))
                        # 直接發送信號，不進行額外處理
                        self.ping_result.emit(ping_time)
                    except ValueError:
                        self.output_received.emit(f"無法解析延遲值: {match.group(1)}")
            
            # 終止進程
            if not self.running:
                process.terminate()
                process.wait()
                
        except Exception as e:
            self.output_received.emit(f"錯誤: {str(e)}")
        
        self.finished.emit()
    
    def stop(self):
        self.running = False

class IperfGUI(QMainWindow):
    """iperf3 GUI主窗口"""
    
    def __init__(self):
        super().__init__()
        self.controller = IperfController()
        self.worker = None
        self.config_manager = ConfigManager()
        
        # 加载配置
        self.config = self.config_manager.load_config()
        
        # 加载语言资源
        self.lang_resources = LanguageResources.get_languages()

        # 设置当前语言
        self.current_language = self.config.get("language", "zh_tw")
        self.lang = self.lang_resources[self.current_language]
        
        # 初始化数据存储
        self.x_data = []
        self.y_data = []
        
        # 初始化 ping 相關變量
        self.ping_worker = None
        self.ping_running = False
        self.ping_x_data = []
        self.ping_y_data = []
        self.ping_start_time = 0
        self.ping_display_window = 60  # 顯示最近 60 秒的數據
        
        # 添加用於統計的變量
        self.stats = {
            "default": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "sent": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "received": {"max": 0, "min": float('inf'), "sum": 0, "count": 0}
        }
        
        # 創建定時器，每 0.5 秒更新一次圖表
        self.update_timer = QTimer()
        self.update_timer.setInterval(500)  # 500毫秒 = 0.5秒
        self.update_timer.timeout.connect(self.update_graph)
        print("定時器已創建，間隔：", self.update_timer.interval(), "ms")
        
        # 初始化數據系列
        self.series_data = {
            "default": {"x": [], "y": []},
            "sent": {"x": [], "y": []},
            "received": {"x": [], "y": []}
        }
        
        # GitHub 倉庫 URL
        self.github_url = "https://github.com/ystartgo/iperf3_UI"
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        # 设置窗口基本属性
        self.setWindowTitle(self.lang["window_title"])
        self.setGeometry(100, 100, 900, 600)
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # 创建顶部控制区域
        control_group = QGroupBox(self.lang["control"])
        control_layout = QVBoxLayout()
        
        # 创建模式选择区域
        mode_layout = QHBoxLayout()
        mode_group = QButtonGroup(self)
        
        self.server_radio = QRadioButton(self.lang["server"])
        self.client_radio = QRadioButton(self.lang["client"])
        mode_group.addButton(self.server_radio)
        mode_group.addButton(self.client_radio)
        self.client_radio.setChecked(True)  # 默认为客户端模式
        
        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        mode_layout.addStretch()
        
        # 创建参数设置区域
        params_layout = QFormLayout()
        
        # 语言选择
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["繁體中文", "English", "简体中文"])
        lang_index = {"zh_tw": 0, "en": 1, "zh_cn": 2}
        self.lang_combo.setCurrentIndex(lang_index.get(self.current_language, 0))
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        params_layout.addRow(QLabel("Language/語言/语言:"), self.lang_combo)
        
        # 主机输入
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("localhost")
        params_layout.addRow(QLabel(self.lang["host"]), self.host_input)
        
        # 端口输入
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(5201)  # iperf3默认端口
        params_layout.addRow(QLabel(self.lang["port"]), self.port_input)
        
        # 时间输入
        self.time_input = QSpinBox()
        self.time_input.setRange(1, 3600)
        self.time_input.setValue(10)  # 默认10秒
        params_layout.addRow(QLabel(self.lang["test_time"]), self.time_input)
        
        # 添加並行連接數控制
        self.parallel_input = QSpinBox()
        self.parallel_input.setRange(1, 100)
        self.parallel_input.setValue(1)  # 默認1個連接
        params_layout.addRow(QLabel(self.lang["parallel_connections"]), self.parallel_input)
        
        # 添加雙向測試選項
        self.bidirectional_check = QCheckBox(self.lang.get("bidirectional", "Bidirectional Test"))
        self.bidirectional_check.setToolTip(self.lang.get("bidirectional_tooltip", "Test both upload and download speeds simultaneously"))
        params_layout.addRow("", self.bidirectional_check)
        
        # 添加到控制布局
        control_layout.addLayout(mode_layout)
        control_layout.addLayout(params_layout)
        control_group.setLayout(control_layout)
        
        # 创建按钮区域
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton(self.lang["start_test"])
        self.stop_button = QPushButton(self.lang["stop_test"])
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton(self.lang["save_results"])
        self.clear_button = QPushButton(self.lang["clear_results"])
        
        # 添加測試按鈕
        self.test_button = QPushButton(self.lang.get("test_graph", "Test Graph"))
        self.test_button.clicked.connect(self.test_graph)
        
        self.start_button.clicked.connect(self.start_test)
        self.stop_button.clicked.connect(self.stop_test)
        self.save_button.clicked.connect(self.save_results)
        self.clear_button.clicked.connect(self.clear_results)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.test_button)
        
        # 添加 ping 功能
        ping_group = QGroupBox(self.lang.get("ping", "Ping"))
        ping_layout = QHBoxLayout()
        
        self.ping_host_input = QLineEdit()
        self.ping_host_input.setPlaceholderText("例如: 8.8.8.8 或 example.com")
        
        self.ping_button = QPushButton(self.lang.get("start_ping", "Start Ping"))
        self.ping_button.clicked.connect(self.toggle_ping)
        
        ping_layout.addWidget(QLabel(self.lang.get("host", "Host")))
        ping_layout.addWidget(self.ping_host_input)
        ping_layout.addWidget(self.ping_button)
        
        ping_group.setLayout(ping_layout)
        
        # 创建输出区域（使用选项卡）
        self.tab_widget = QTabWidget()
        
        # 文本输出选项卡
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier New", 10))
        self.tab_widget.addTab(self.output_text, self.lang["output"])
        
        # 图形输出选项卡
        self.graph_view = GraphView(self.lang_resources, self.current_language)
        self.tab_widget.addTab(self.graph_view, self.lang["graph"])
        
        # 添加 ping 輸出選項卡
        self.ping_output = QTextEdit()
        self.ping_output.setReadOnly(True)
        self.ping_output.setFont(QFont("Courier New", 10))
        self.tab_widget.addTab(self.ping_output, self.lang.get("ping", "Ping"))
        
        # 添加 ping 圖表選項卡
        self.ping_graph_view = GraphView(self.lang_resources, self.current_language)
        self.ping_graph_view.plot_widget.setTitle(self.lang.get("ping_latency", "Ping Latency"), color="k", size="14pt")
        self.ping_graph_view.plot_widget.setLabel('left', self.lang.get("latency", "Latency"), units='ms', color="k")
        self.tab_widget.addTab(self.ping_graph_view, self.lang.get("ping_graph", "Ping Graph"))
        
        # 添加所有组件到主布局
        main_layout.addWidget(control_group)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(ping_group)
        main_layout.addWidget(self.tab_widget, 1)  # 1表示拉伸因子，让输出区域占据更多空间
        
        self.setCentralWidget(central_widget)
        
        # 状态栏
        self.statusBar().showMessage(self.lang["ready"])
        
        # 连接信号和槽
        self.server_radio.toggled.connect(self.toggle_mode)
        self.client_radio.toggled.connect(self.toggle_mode)
        
        # 初始化模式
        self.toggle_mode()
        
        # 添加版權信息和 GitHub 連結到狀態欄
        copyright_label = QLabel(f"© 2025 GPL-3.0 License | Contact: startgo@yia.app | <a href='{self.github_url}'>GitHub</a>")
        copyright_label.setOpenExternalLinks(True)  # 允許點擊打開外部連結
        copyright_label.linkActivated.connect(self.open_github)  # 連接信號以處理點擊事件
        self.statusBar().addPermanentWidget(copyright_label)
    
    def open_github(self, link):
        """打開 GitHub 倉庫頁面"""
        QDesktopServices.openUrl(QUrl(link))
    
    def toggle_mode(self):
        """切换服务器/客户端模式"""
        is_server = self.server_radio.isChecked()
        self.host_input.setEnabled(not is_server)
    
    def change_language(self):
        """切换界面语言"""
        index = self.lang_combo.currentIndex()
        lang_codes = ["zh_tw", "en", "zh_cn"]
        if index >= 0 and index < len(lang_codes):
            self.current_language = lang_codes[index]
            self.lang = self.lang_resources[self.current_language]
            
            # 更新图表语言
            self.graph_view.set_language(self.lang_resources, self.current_language)
            self.ping_graph_view.set_language(self.lang_resources, self.current_language)
            
            # 保存语言设置
            self.config["language"] = self.current_language
            self.config_manager.save_config(self.config)
            
            # 提示用户重启应用
            QMessageBox.information(self, "Language Changed", 
                                   "Please restart the application for language changes to take effect.")
    
    def start_test(self):
        """开始iperf测试"""
        # 禁用开始按钮，启用停止按钮
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # 清除之前的结果
        self.output_text.clear()
        self.series_data = {
            "default": {"x": [], "y": []},
            "sent": {"x": [], "y": []},
            "received": {"x": [], "y": []}
        }
        self.graph_view.clear_graph()
        
        # 清除之前的統計數據
        self.stats = {
            "default": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "sent": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "received": {"max": 0, "min": float('inf'), "sum": 0, "count": 0}
        }
        
        # 获取测试时间
        test_time = self.time_input.value()
        
        # 准备参数
        params = {
            "mode": "server" if self.server_radio.isChecked() else "client",
            "host": self.host_input.text() if self.client_radio.isChecked() else None,
            "port": self.port_input.value(),
            "time": test_time,
            "format": "json",  # 使用JSON格式以便解析
            "parallel": self.parallel_input.value(),  # 添加並行連接數
            "bidirectional": self.bidirectional_check.isChecked()  # 添加雙向測試選項
        }
        
        # 设置图表的 X 轴范围
        self.graph_view.plot_widget.setXRange(0, min(60, test_time))
        
        # 创建并启动工作线程
        self.worker = IperfWorker(self.controller, params)
        self.worker.output_received.connect(self.process_output)
        self.worker.finished.connect(self.test_finished)
        self.worker.start()
        
        # 確保停止之前的定時器（如果有的話）
        if self.update_timer.isActive():
            self.update_timer.stop()
        
        # 啟動定時器，每 0.2 秒更新一次圖表（更頻繁的更新）
        self.update_timer.setInterval(200)  # 200毫秒 = 0.2秒，更頻繁的更新
        self.update_timer.start()
        print("定時器已啟動，間隔：", self.update_timer.interval(), "ms")
        
        # 切换到图表选项卡
        self.tab_widget.setCurrentIndex(1)
        
        # 更新状态栏
        self.statusBar().showMessage(self.lang["test_running"])
    
    def stop_test(self):
        """停止iperf测试"""
        if self.worker and self.worker.isRunning():
            self.controller.stop_iperf()
            self.update_timer.stop()  # 停止定時器
            print("定時器已停止")
            self.statusBar().showMessage(self.lang["test_stopped"])
    
    def test_finished(self):
        """测试完成后的处理"""
        # 停止定時器
        self.update_timer.stop()
        print("測試完成，定時器已停止")
        
        # 最後更新一次圖表，確保顯示最終結果
        self.update_graph()
        
        # 恢复按钮状态
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # 更新状态栏
        self.statusBar().showMessage(self.lang["test_completed"])
    
    def process_output(self, line):
        """處理 iperf 輸出"""
        # 添加到文本輸出
        self.output_text.append(line)
        
        # 嘗試解析 JSON 數據並更新圖表
        try:
            # 檢查是否是 JSON 格式
            if line.strip().startswith('{') and line.strip().endswith('}'):
                data = json.loads(line)
                print(f"Parsed JSON data keys: {data.keys()}")
                
                # 檢查是否有 intervals 數據
                if "intervals" in data:
                    print(f"Found {len(data['intervals'])} intervals")
                    updated = False
                    
                    for interval in data["intervals"]:
                        if "sum" in interval:
                            # 提取時間和帶寬數據
                            time_sec = interval["sum"]["start"]
                            bandwidth = interval["sum"]["bits_per_second"] / 1000000  # 轉換為 Mbps
                            print(f"Extracted data: time={time_sec}, bandwidth={bandwidth}")
                            self.add_data_point(time_sec, bandwidth)
                            updated = True
                        
                        # 處理雙向測試的數據
                        if "sum_sent" in interval:
                            time_sec = interval["sum_sent"]["start"]
                            bandwidth = interval["sum_sent"]["bits_per_second"] / 1000000
                            print(f"Extracted sent data: time={time_sec}, bandwidth={bandwidth}")
                            self.add_data_point(time_sec, bandwidth, series="sent")
                            updated = True
                        
                        if "sum_received" in interval:
                            time_sec = interval["sum_received"]["start"]
                            bandwidth = interval["sum_received"]["bits_per_second"] / 1000000
                            print(f"Extracted received data: time={time_sec}, bandwidth={bandwidth}")
                            self.add_data_point(time_sec, bandwidth, series="received")
                            updated = True
                    
                    # 如果有更新，強制更新圖表一次（不依賴定時器）
                    if updated:
                        self.update_graph()
                        # 如果當前不是圖表頁面，切換到圖表選項卡
                        if self.tab_widget.currentIndex() != 1:
                            self.tab_widget.setCurrentIndex(1)
                
                # 檢查是否有最終結果
                if "end" in data:
                    if "sum_sent" in data["end"]:
                        final_bandwidth_sent = data["end"]["sum_sent"]["bits_per_second"] / 1000000
                        print(f"Final sent bandwidth: {final_bandwidth_sent} Mbps")
                        # 添加最終發送點
                        test_time = self.time_input.value()
                        self.add_data_point(test_time, final_bandwidth_sent, series="sent")
                    
                    if "sum_received" in data["end"]:
                        final_bandwidth_received = data["end"]["sum_received"]["bits_per_second"] / 1000000
                        print(f"Final received bandwidth: {final_bandwidth_received} Mbps")
                        # 添加最終接收點
                        test_time = self.time_input.value()
                        self.add_data_point(test_time, final_bandwidth_received, series="received")
                    
                    # 最終結果出來後強制更新一次圖表
                    self.update_graph()
        
        # 處理非 JSON 格式的輸出（例如，實時更新）
        except json.JSONDecodeError:
            # 不是 JSON 格式，檢查是否包含帶寬信息
            if "bits/sec" in line:
                print(f"Found bandwidth info in line: {line}")
                # 使用正則表達式提取帶寬數據
                import re
                # 匹配格式如 "0.00-0.50 sec 12.3 MBytes 246 Mbits/sec"
                match = re.search(r'(\d+\.\d+)-(\d+\.\d+)\s+sec\s+\d+\.?\d*\s+\w+\s+(\d+\.?\d*)\s+(Mbits/sec|Kbits/sec|Gbits/sec)', line)
                if match:
                    end_time = float(match.group(2))
                    value = float(match.group(3))
                    unit = match.group(4)
                    
                    # 轉換為統一單位 (Mbits/sec)
                    if unit == "Kbits/sec":
                        value /= 1000
                    elif unit == "Gbits/sec":
                        value *= 1000
                    
                    print(f"Extracted from text: time={end_time}, bandwidth={value}")
                    
                    # 檢測是發送還是接收數據
                    series = "default"
                    if "sender" in line.lower():
                        series = "sent"
                    elif "receiver" in line.lower():
                        series = "received"
                    
                    self.add_data_point(end_time, value, series=series)
                    
                    # 從文本中提取到數據後，也強制更新一次圖表
                    self.update_graph()
        except Exception as e:
            print(f"Error processing output: {e}")
    
    def add_data_point(self, time_sec, bandwidth, series="default"):
        """添加數據點到圖表"""
        # 檢查數據是否有效
        if bandwidth <= 0:
            print(f"Ignoring invalid bandwidth value: {bandwidth}")
            return
        
        # 檢查是否已經有相同時間點的數據，如果有則更新
        for i, t in enumerate(self.series_data[series]["x"]):
            if abs(t - time_sec) < 0.01:  # 允許小誤差
                self.series_data[series]["y"][i] = bandwidth
                print(f"Updating existing data point in series {series}: time={time_sec}, bandwidth={bandwidth}")
                break
        else:
            # 如果沒有相同時間點的數據，則添加新數據點
            self.series_data[series]["x"].append(time_sec)
            self.series_data[series]["y"].append(bandwidth)
            print(f"Adding new data point to series {series}: time={time_sec}, bandwidth={bandwidth}")
        
        # 更新統計數據
        self.stats[series]["max"] = max(self.stats[series]["max"], bandwidth)
        self.stats[series]["min"] = min(self.stats[series]["min"], bandwidth)
        self.stats[series]["sum"] += bandwidth
        self.stats[series]["count"] += 1
        
        # 確保數據按時間排序
        if len(self.series_data[series]["x"]) > 1:
            sorted_indices = sorted(range(len(self.series_data[series]["x"])), 
                                   key=lambda i: self.series_data[series]["x"][i])
            self.series_data[series]["x"] = [self.series_data[series]["x"][i] for i in sorted_indices]
            self.series_data[series]["y"] = [self.series_data[series]["y"][i] for i in sorted_indices]
        
        # 調試輸出
        print(f"Current data in series {series}: {len(self.series_data[series]['y'])} points")
        
        # 獲取測試時間
        test_time = self.time_input.value()
        
        # 注意：不再在這裡調用 update_graph，而是由定時器觸發
        
        # 調整 X 軸範圍，顯示當前時間附近的數據
        current_time = time_sec
        window_size = min(60, test_time)  # 顯示最多 60 秒的數據，或者測試時間（如果小於 60 秒）
        start_time = max(0, current_time - window_size * 0.2)  # 顯示當前時間前 20% 的數據
        end_time = min(test_time, start_time + window_size)  # 顯示最多 window_size 秒的數據
        
        # 設置 X 軸範圍
        self.graph_view.plot_widget.setXRange(start_time, end_time)
    
    def test_graph(self):
        """測試圖表顯示"""
        # 清除之前的數據
        self.series_data = {
            "default": {"x": [], "y": []},
            "sent": {"x": [], "y": []},
            "received": {"x": [], "y": []}
        }
        self.graph_view.clear_graph()
        
        # 清除之前的統計數據
        self.stats = {
            "default": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "sent": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "received": {"max": 0, "min": float('inf'), "sum": 0, "count": 0}
        }
        
        # 設置測試時間
        test_time = self.time_input.value()
        self.graph_view.plot_widget.setXRange(0, test_time)
        
        # 生成更有變化的測試數據
        base_value = 100  # 基準帶寬值
        
        # 創建一個定時器來模擬數據點的逐步添加
        self.test_timer = QTimer()
        self.test_current_time = 0
        
        def add_test_data_point():
            if self.test_current_time <= test_time:
                # 默認系列 - 隨機波動的帶寬
                bandwidth = base_value + random.uniform(-20, 30)
                self.add_data_point(self.test_current_time, bandwidth)
                
                # 如果啟用雙向測試，添加發送和接收數據
                if self.bidirectional_check.isChecked():
                    sent_bw = base_value * 0.7 + random.uniform(-15, 25)
                    recv_bw = base_value * 1.3 + random.uniform(-25, 35)
                    self.add_data_point(self.test_current_time, sent_bw, series="sent")
                    self.add_data_point(self.test_current_time, recv_bw, series="received")
                
                # 更新圖表
                self.update_graph()
                
                # 增加時間
                self.test_current_time += 1
            else:
                # 測試完成，停止定時器
                self.test_timer.stop()
                self.statusBar().showMessage(self.lang.get("test_data_generated", "測試數據已生成"))
        
        # 連接定時器信號
        self.test_timer.timeout.connect(add_test_data_point)
        # 設置間隔為 200 毫秒，使動畫更流暢
        self.test_timer.setInterval(200)
        # 啟動定時器
        self.test_timer.start()
        
        # 切換到圖表選項卡
        self.tab_widget.setCurrentIndex(1)
        
        # 顯示測試信息
        self.statusBar().showMessage(self.lang.get("test_graph_status", "圖表測試模式 - 模擬數據"))
    
    def toggle_ping(self):
        """開始或停止 ping"""
        if self.ping_running:
            self.stop_ping()
        else:
            self.start_ping()

    def start_ping(self):
        """開始 ping"""
        host = self.ping_host_input.text().strip()
        if not host:
            QMessageBox.warning(self, self.lang.get("error", "Error"), 
                               self.lang.get("no_host", "Please enter a host to ping"))
            return
        
        # 清除之前的結果
        self.ping_output.clear()
        self.ping_x_data = []
        self.ping_y_data = []
        self.ping_graph_view.clear_graph()
        self.ping_start_time = time.time()
        
        # 創建並啟動 ping 工作線程
        self.ping_worker = PingWorker(host)
        self.ping_worker.output_received.connect(self.process_ping_output)
        self.ping_worker.ping_result.connect(self.add_ping_data_point)
        self.ping_worker.finished.connect(self.ping_finished)
        self.ping_worker.start()
        
        # 更新 UI
        self.ping_button.setText(self.lang.get("stop_ping", "Stop Ping"))
        self.ping_running = True
        
        # 只在開始 ping 時切換一次到 ping 輸出頁面，之後不再自動切換
        current_tab = self.tab_widget.currentIndex()
        if current_tab != 2 and current_tab != 3:  # 如果當前不是 ping 相關的頁面
            self.tab_widget.setCurrentIndex(2)  # 切換到 ping 輸出頁面

    def stop_ping(self):
        """停止 ping"""
        if self.ping_worker and self.ping_worker.isRunning():
            self.ping_worker.stop()
            self.ping_button.setText(self.lang.get("start_ping", "Start Ping"))
            self.ping_running = False

    def ping_finished(self):
        """ping 完成後的處理"""
        self.ping_button.setText(self.lang.get("start_ping", "Start Ping"))
        self.ping_running = False

    def process_ping_output(self, line):
        """處理 ping 輸出"""
        self.ping_output.append(line)
        
        # 調試輸出 - 檢查是否包含時間信息
        if "時間=" in line or "time=" in line:
            print(f"Found time info in line: {line}")
            
            # 嘗試使用不同的正則表達式模式
            import re
            # 繁體中文 Windows
            match1 = re.search(r"時間=(\d+)ms", line)
            # 英文 Windows/Linux
            match2 = re.search(r"time[=<](\d+)ms", line)
            # Linux/Mac
            match3 = re.search(r"time=([\d\.]+) ms", line)
            
            if match1:
                print(f"Matched pattern 1: {match1.group(1)}")
            elif match2:
                print(f"Matched pattern 2: {match2.group(1)}")
            elif match3:
                print(f"Matched pattern 3: {match3.group(1)}")
            else:
                print(f"No pattern matched for line: {line}")

    def add_ping_data_point(self, ping_time):
        """添加 ping 數據點到圖表"""
        # 獲取當前時間點（相對於開始時間）
        if not self.ping_x_data:
            x = 0
        else:
            x = time.time() - self.ping_start_time
        
        self.ping_x_data.append(x)
        self.ping_y_data.append(ping_time)
        
        # 調試輸出
        print(f"Adding ping data point: time={x}, latency={ping_time}")
        
        # 限制數據點數量，防止內存溢出和提高性能
        max_points = 300  # 增加最大點數
        if len(self.ping_x_data) > max_points:
            self.ping_x_data = self.ping_x_data[-max_points:]
            self.ping_y_data = self.ping_y_data[-max_points:]
        
        # 更新圖表
        self.ping_graph_view.update_graph(self.ping_y_data, x_data=self.ping_x_data)
        
        # 設置 X 軸範圍為最近 60 秒的數據
        if len(self.ping_x_data) > 1:
            current_time = self.ping_x_data[-1]
            start_time = max(0, current_time - self.ping_display_window)
            self.ping_graph_view.plot_widget.setXRange(start_time, current_time)
        
        # 強制更新圖表
        self.ping_graph_view.repaint()
        QApplication.processEvents()  # 強制處理事件，確保圖表更新

    def save_results(self):
        """保存测试结果"""
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            self.lang["save_text_results"],
            "",
            self.lang["text_file"],
            options=options
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.statusBar().showMessage(self.lang["results_saved"])
            except Exception as e:
                QMessageBox.critical(self, self.lang["error"], f"{str(e)}")

    def clear_results(self):
        """清除测试结果"""
        self.output_text.clear()
        self.series_data = {
            "default": {"x": [], "y": []},
            "sent": {"x": [], "y": []},
            "received": {"x": [], "y": []}
        }
        self.stats = {
            "default": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "sent": {"max": 0, "min": float('inf'), "sum": 0, "count": 0},
            "received": {"max": 0, "min": float('inf'), "sum": 0, "count": 0}
        }
        self.graph_view.clear_graph()
        self.statusBar().showMessage(self.lang["results_cleared"])

    def update_graph(self):
        """更新圖表顯示"""
        print(f"更新圖表，時間：{time.time()}")
        
        try:
            # 清除現有曲線，但保留設置
            self.graph_view.clear_graph(keep_settings=True)
            
            # 添加各個數據系列
            # 默認數據系列（單向測試）
            if self.series_data["default"]["x"] and self.series_data["default"]["y"]:
                self.graph_view.add_series(
                    self.series_data["default"]["x"],
                    self.series_data["default"]["y"],
                    name=self.lang.get("bandwidth", "頻寬"),
                    color=(0, 0, 255)
                )
                
                # 添加統計信息
                if self.stats["default"]["count"] > 0:
                    avg = self.stats["default"]["sum"] / self.stats["default"]["count"]
                    max_val = self.stats["default"]["max"]
                    min_val = self.stats["default"]["min"] if self.stats["default"]["min"] != float('inf') else 0
                    
                    # 添加平均值、最大值、最小值標籤
                    stats_text = f"{self.lang.get('average', '平均')}: {avg:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('maximum', '最大')}: {max_val:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('minimum', '最小')}: {min_val:.2f} Mbps"
                    
                    # 計算文本位置 - 放在右上角
                    x_pos = max(self.series_data["default"]["x"]) * 0.7 if self.series_data["default"]["x"] else 0
                    y_pos = max(self.series_data["default"]["y"]) * 0.9 if self.series_data["default"]["y"] else 0
                    
                    self.graph_view.add_text_item(
                        stats_text,
                        x=x_pos,
                        y=y_pos,
                        color=(0, 0, 255)
                    )
                    
                    # 添加水平線表示平均值
                    self.graph_view.add_horizontal_line(
                        avg, 
                        name=self.lang.get('average', '平均'), 
                        color=(0, 0, 255, 100)
                    )
            
            # 發送數據系列（雙向測試）
            if self.series_data["sent"]["x"] and self.series_data["sent"]["y"]:
                self.graph_view.add_series(
                    self.series_data["sent"]["x"],
                    self.series_data["sent"]["y"],
                    name=self.lang.get("bandwidth_sent", "上傳"),
                    color=(255, 0, 0)
                )
                
                # 添加統計信息
                if self.stats["sent"]["count"] > 0:
                    avg = self.stats["sent"]["sum"] / self.stats["sent"]["count"]
                    max_val = self.stats["sent"]["max"]
                    min_val = self.stats["sent"]["min"] if self.stats["sent"]["min"] != float('inf') else 0
                    
                    # 添加平均值、最大值、最小值標籤
                    stats_text = f"{self.lang.get('upload_average', '上傳平均')}: {avg:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('maximum', '最大')}: {max_val:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('minimum', '最小')}: {min_val:.2f} Mbps"
                    
                    # 計算文本位置 - 放在右上角但低於默認系列
                    x_pos = max(self.series_data["sent"]["x"]) * 0.7 if self.series_data["sent"]["x"] else 0
                    y_pos = max(self.series_data["sent"]["y"]) * 0.7 if self.series_data["sent"]["y"] else 0
                    
                    self.graph_view.add_text_item(
                        stats_text,
                        x=x_pos,
                        y=y_pos,
                        color=(255, 0, 0)
                    )
                    
                    # 添加水平線表示平均值
                    self.graph_view.add_horizontal_line(
                        avg, 
                        name=self.lang.get('upload_average', '上傳平均'), 
                        color=(255, 0, 0, 100)
                    )
            
            # 接收數據系列（雙向測試）
            if self.series_data["received"]["x"] and self.series_data["received"]["y"]:
                self.graph_view.add_series(
                    self.series_data["received"]["x"],
                    self.series_data["received"]["y"],
                    name=self.lang.get("bandwidth_received", "下載"),
                    color=(0, 255, 0)
                )
                
                # 添加統計信息
                if self.stats["received"]["count"] > 0:
                    avg = self.stats["received"]["sum"] / self.stats["received"]["count"]
                    max_val = self.stats["received"]["max"]
                    min_val = self.stats["received"]["min"] if self.stats["received"]["min"] != float('inf') else 0
                    
                    # 添加平均值、最大值、最小值標籤
                    stats_text = f"{self.lang.get('download_average', '下載平均')}: {avg:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('maximum', '最大')}: {max_val:.2f} Mbps\n"
                    stats_text += f"{self.lang.get('minimum', '最小')}: {min_val:.2f} Mbps"
                    
                    # 計算文本位置 - 放在右上角但低於其他系列
                    x_pos = max(self.series_data["received"]["x"]) * 0.7 if self.series_data["received"]["x"] else 0
                    y_pos = max(self.series_data["received"]["y"]) * 0.5 if self.series_data["received"]["y"] else 0
                    
                    self.graph_view.add_text_item(
                        stats_text,
                        x=x_pos,
                        y=y_pos,
                        color=(0, 255, 0)
                    )
                    
                    # 添加水平線表示平均值
                    self.graph_view.add_horizontal_line(
                        avg, 
                        name=self.lang.get('download_average', '下載平均'), 
                        color=(0, 255, 0, 100)
                    )
            
            # 強制更新圖表
            self.graph_view.repaint()
            QApplication.processEvents()  # 強制處理事件，確保圖表更新
        except Exception as e:
            print(f"更新圖表時出錯: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = IperfGUI()
    gui.show()
    sys.exit(app.exec_())