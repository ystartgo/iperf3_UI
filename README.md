# iperf3 GUI

一个跨平台的iperf3图形用户界面，支持控制各种参数和图形化显示网络流量。

## 功能特点

- 支持Windows、macOS和Linux平台
- 多语言支持（繁體中文、English、简体中文）
- 客户端和服务器模式
- 可配置的iperf3参数
- 实时图形化显示网络流量
- 自动保存测试结果（文本、JSON和图表）
- 自动应用上次使用的参数
- 命令行参数支持
## 依赖项

- Python 3.6+
- PyQt5
- pyqtgraph
- iperf3（命令行工具）

## 安装

1. 确保已安装iperf3命令行工具，并添加到系统路径中
2. 安装Python依赖项：

```bash
pip install -r requirements.txt
