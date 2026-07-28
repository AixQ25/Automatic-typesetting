"""
自动排版系统 - 主程序入口
AutoCAD插件，实现图形自动排版
"""

import sys
import os
from typing import List, Tuple

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QSpinBox, QDoubleSpinBox, QMessageBox, QGroupBox)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import config
from autocad_bridge import AutoCADBridge
from nesting.rect_nesting import RectNesting, Rect, Placement


class PreviewCanvas(FigureCanvas):
    """排版预览画布"""
    
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 6))
        super().__init__(self.fig)
        self.setParent(parent)
        self.axes = self.fig.add_subplot(111)
    
    def draw_nesting(self, placements: List[Placement], board_width: float, board_height: float):
        """绘制排版结果"""
        self.axes.clear()
        
        # 绘制板材边界
        self.axes.plot([0, board_width, board_width, 0, 0],
                      [0, 0, board_height, board_height, 0],
                      'k-', linewidth=2, label='板材')
        
        # 绘制放置的矩形
        colors = ['blue', 'green', 'red', 'cyan', 'magenta', 'yellow', 'orange', 'purple']
        
        for i, p in enumerate(placements):
            color = colors[i % len(colors)]
            x = p.x
            y = p.y
            w = p.actual_width
            h = p.actual_height
            
            # 绘制矩形
            rect = matplotlib.patches.Rectangle((x, y), w, h,
                                               linewidth=1,
                                               edgecolor=color,
                                               facecolor=color,
                                               alpha=0.3)
            self.axes.add_patch(rect)
            
            # 标注编号
            self.axes.text(x + w/2, y + h/2, str(p.rect.id),
                          ha='center', va='center', fontsize=8)
        
        self.axes.set_xlim(-10, board_width + 10)
        self.axes.set_ylim(-10, board_height + 10)
        self.axes.set_aspect('equal')
        self.axes.grid(True, alpha=0.3)
        self.axes.legend()
        
        self.draw()


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setGeometry(100, 100, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        
        # AutoCAD连接
        self.bridge = AutoCADBridge()
        self.connected = False
        
        # 排版结果
        self.placements = []
        
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 顶部控制区
        control_layout = QHBoxLayout()
        
        # AutoCAD连接按钮
        self.connect_btn = QPushButton("连接AutoCAD")
        self.connect_btn.clicked.connect(self.connect_autocad)
        control_layout.addWidget(self.connect_btn)
        
        # 板材选择
        board_group = QGroupBox("板材选择")
        board_layout = QHBoxLayout(board_group)
        
        board_layout.addWidget(QLabel("板材:"))
        self.board_combo = QComboBox()
        self.board_combo.addItems(config.BOARD_SIZES.keys())
        self.board_combo.setCurrentText(config.DEFAULT_BOARD)
        board_layout.addWidget(self.board_combo)
        
        control_layout.addWidget(board_group)
        
        # 间距设置
        spacing_group = QGroupBox("排版参数")
        spacing_layout = QHBoxLayout(spacing_group)
        
        spacing_layout.addWidget(QLabel("间距(mm):"))
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(0, 100)
        self.spacing_spin.setValue(config.NESTING_SPACING)
        spacing_layout.addWidget(self.spacing_spin)
        
        control_layout.addWidget(spacing_group)
        
        # 操作按钮
        self.nest_btn = QPushButton("执行排版")
        self.nest_btn.clicked.connect(self.execute_nesting)
        self.nest_btn.setEnabled(False)
        control_layout.addWidget(self.nest_btn)
        
        self.write_btn = QPushButton("写入CAD")
        self.write_btn.clicked.connect(self.write_to_cad)
        self.write_btn.setEnabled(False)
        control_layout.addWidget(self.write_btn)
        
        layout.addLayout(control_layout)
        
        # 预览区域
        self.preview_canvas = PreviewCanvas(self)
        layout.addWidget(self.preview_canvas)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def connect_autocad(self):
        """连接AutoCAD"""
        self.statusBar().showMessage("正在连接AutoCAD...")
        
        if self.bridge.connect():
            self.connected = True
            self.connect_btn.setText("已连接")
            self.connect_btn.setEnabled(False)
            self.nest_btn.setEnabled(True)
            self.statusBar().showMessage(f"已连接到: {self.bridge.acad.doc.Name}")
        else:
            QMessageBox.critical(self, "错误", 
                               "连接AutoCAD失败！\n\n请确保:\n1. AutoCAD已运行\n2. 已打开一个文档")
    
    def execute_nesting(self):
        """执行排版"""
        if not self.connected:
            QMessageBox.warning(self, "警告", "请先连接AutoCAD")
            return
        
        self.statusBar().showMessage("正在获取选中图形...")
        
        # 获取选中的实体
        entities = self.bridge.get_selected_entities()
        
        if not entities:
            QMessageBox.warning(self, "警告", "未选中任何图形！\n请在AutoCAD中选择要排版的图形")
            return
        
        # 转换为矩形列表（简化处理：使用边界框）
        rects = []
        for entity in entities:
            # 计算边界框
            x_coords = [p[0] for p in entity.coordinates]
            y_coords = [p[1] for p in entity.coordinates]
            
            if x_coords and y_coords:
                width = max(x_coords) - min(x_coords)
                height = max(y_coords) - min(y_coords)
                
                if width > 0 and height > 0:
                    rects.append(Rect(width=width, height=height))
        
        if not rects:
            QMessageBox.warning(self, "警告", "无法提取图形尺寸")
            return
        
        # 获取板材尺寸
        board_key = self.board_combo.currentText()
        board_width, board_height, _ = config.BOARD_SIZES[board_key]
        
        # 获取间距
        spacing = self.spacing_spin.value()
        
        # 执行排样
        self.statusBar().showMessage("正在排版...")
        
        nestor = RectNesting(board_width, board_height, spacing)
        self.placements = nestor.nest(rects)
        
        # 显示结果
        utilization = nestor.get_utilization()
        self.statusBar().showMessage(f"排版完成！放置 {len(self.placements)} 个图形，利用率: {utilization:.1%}")
        
        # 绘制预览
        self.preview_canvas.draw_nesting(self.placements, board_width, board_height)
        
        # 启用写入按钮
        self.write_btn.setEnabled(True)
        
        # 显示结果摘要
        QMessageBox.information(self, "排版完成", 
                               f"已放置 {len(self.placements)} 个图形\n"
                               f"利用率: {utilization:.1%}\n\n"
                               f"点击'写入CAD'将结果写入AutoCAD")
    
    def write_to_cad(self):
        """将排版结果写入AutoCAD"""
        if not self.placements:
            QMessageBox.warning(self, "警告", "没有排版结果可写入")
            return
        
        self.statusBar().showMessage("正在写入AutoCAD...")
        
        # 创建图层
        if not self.bridge.create_layer(config.LAYER_NAME, config.LAYER_COLOR):
            QMessageBox.critical(self, "错误", "创建图层失败")
            return
        
        # 写入实体
        success_count = 0
        for placement in self.placements:
            # 计算偏移量
            offset_x = placement.x
            offset_y = placement.y
            
            # 这里简化处理：直接绘制矩形
            # 实际应该复制原始实体并移动
            if self.bridge.draw_rectangle(
                offset_x, offset_y,
                placement.actual_width, placement.actual_height,
                config.LAYER_NAME
            ):
                success_count += 1
        
        self.statusBar().showMessage(f"已写入 {success_count} 个图形到图层 '{config.LAYER_NAME}'")
        
        QMessageBox.information(self, "写入完成", 
                               f"已写入 {success_count} 个图形\n"
                               f"图层: {config.LAYER_NAME}\n\n"
                               f"请在AutoCAD中查看结果")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
