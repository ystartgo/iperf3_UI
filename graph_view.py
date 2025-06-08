import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

class GraphView(QWidget):
    """用於顯示圖形數據的視圖"""
    
    def __init__(self, lang_resources, current_language):
        super().__init__()
        
        # 設置語言資源
        self.set_language(lang_resources, current_language)
        
        # 初始化UI
        self.init_ui()
    
    def set_language(self, lang_resources, current_language):
        """設置語言"""
        self.lang_resources = lang_resources
        self.current_language = current_language
        self.lang = lang_resources[current_language]
    
    def init_ui(self):
        """初始化UI"""
        # 創建佈局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 設置白色背景
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        # 創建繪圖窗口
        self.plot_widget = pg.PlotWidget()
        
        # 設置標題和軸標籤 - 確保使用正確的語言資源
        title = self.lang.get("bandwidth_graph", "網絡頻寬圖表")
        bandwidth_label = self.lang.get("bandwidth", "頻寬")
        time_label = self.lang.get("time", "時間")
        
        self.plot_widget.setTitle(title, color="k", size="14pt")
        self.plot_widget.setLabel('left', bandwidth_label, units='Mbps', color="k")
        self.plot_widget.setLabel('bottom', time_label, units='s', color="k")
        
        # 設置網格
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 設置字體
        font = QFont()
        font.setPointSize(10)
        self.plot_widget.getAxis("bottom").tickFont = font
        self.plot_widget.getAxis("left").tickFont = font
        
        # 添加圖例
        self.legend = self.plot_widget.addLegend()
        
        # 添加到佈局
        layout.addWidget(self.plot_widget)
        
        # 初始化數據曲線
        self.curves = {}
        
        # 初始化文本項和線條列表
        self.text_items = []
        self.lines = []
    
    def add_series(self, x_data, y_data, name="Data", color=(0, 0, 255)):
        """添加數據系列到圖表"""
        # 創建筆
        pen = pg.mkPen(color=color, width=2)
        
        # 如果曲線已經存在，更新數據
        if name in self.curves:
            self.curves[name].setData(x_data, y_data)
        else:
            # 創建新曲線
            curve = self.plot_widget.plot(x_data, y_data, name=name, pen=pen)
            self.curves[name] = curve
    
    def update_graph(self, y_data, x_data=None, name="Data", color=(0, 0, 255)):
        """更新圖表數據"""
        # 如果沒有提供 x 數據，則使用索引
        if x_data is None:
            x_data = list(range(len(y_data)))
        
        # 添加或更新數據系列
        self.add_series(x_data, y_data, name=name, color=color)
    
    def clear_graph(self, keep_settings=False):
        """清除圖表"""
        self.plot_widget.clear()
        self.curves = {}
        
        # 清除保存的文本項和線條引用
        self.text_items = []
        self.lines = []
        
        # 重新設置標題和軸標籤
        if keep_settings:
            title = self.lang.get("bandwidth_graph", "網絡頻寬圖表")
            bandwidth_label = self.lang.get("bandwidth", "頻寬")
            time_label = self.lang.get("time", "時間")
            
            self.plot_widget.setTitle(title, color="k", size="14pt")
            self.plot_widget.setLabel('left', bandwidth_label, units='Mbps', color="k")
            self.plot_widget.setLabel('bottom', time_label, units='s', color="k")
            
            # 重新添加圖例
            self.legend = self.plot_widget.addLegend()
    
    def add_text_item(self, text, x, y, color=(0, 0, 0)):
        """添加文本項到圖表"""
        # 創建文本項
        text_item = pg.TextItem(text=text, color=color, anchor=(0, 0))
        text_item.setPos(x, y)
        
        # 添加到圖表
        self.plot_widget.addItem(text_item)
        
        # 保存引用以便後續清除
        self.text_items.append(text_item)
        
        return text_item
    
    def add_horizontal_line(self, y_value, name="Average", color=(0, 0, 255, 100)):
        """添加水平線到圖表"""
        # 創建水平線
        line = pg.InfiniteLine(
            pos=y_value, 
            angle=0, 
            pen=pg.mkPen(color=color, width=1, style=Qt.DashLine),
            label=name,
            labelOpts={
                'position': 0.95, 
                'color': color[:3], 
                'movable': True, 
                'fill': (200, 200, 200, 100)
            }
        )
        
        # 添加到圖表
        self.plot_widget.addItem(line)
        
        # 保存引用以便後續清除
        self.lines.append(line)
        
        return line
    
    def set_x_range(self, min_x, max_x):
        """設置 X 軸範圍"""
        self.plot_widget.setXRange(min_x, max_x)
    
    def set_y_range(self, min_y, max_y):
        """設置 Y 軸範圍"""
        self.plot_widget.setYRange(min_y, max_y)
    
    def set_auto_range(self):
        """設置自動範圍"""
        self.plot_widget.enableAutoRange()
    
    def set_title(self, title):
        """設置圖表標題"""
        self.plot_widget.setTitle(title, color="k", size="14pt")
    
    def set_x_label(self, label, units=None):
        """設置 X 軸標籤"""
        self.plot_widget.setLabel('bottom', label, units=units, color="k")
    
    def set_y_label(self, label, units=None):
        """設置 Y 軸標籤"""
        self.plot_widget.setLabel('left', label, units=units, color="k")
    
    def export_image(self, filename):
        """將圖表導出為圖像"""
        exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
        exporter.export(filename)