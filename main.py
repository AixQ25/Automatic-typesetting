"""
自动排版系统 - 主程序入口
基于ezdxf，支持按厚度分组和多板材自动排版
"""

import sys
import os
from typing import List, Dict

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QMessageBox,
                             QFileDialog, QProgressBar, QTextEdit,
                             QDoubleSpinBox, QGroupBox)
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

import config
from utils.dxf_parser import DxfParser
from utils.dxf_writer import DxfWriter
from utils.text_parser import TextParser
from utils.shape_grouper import ShapeGrouper, ShapeGroup
from utils.containment_detector import ContainmentDetector
from nesting.rect_nesting import Rect, RectNesting, Placement
from nesting.board_optimizer import find_optimal_boards, NestingResult, Board


class PreviewCanvas(FigureCanvas):
    """排版预览画布"""
    
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(12, 8))
        super().__init__(self.fig)
        self.setParent(parent)
        self.axes = self.fig.add_subplot(111)
    
    def draw_multi_group(self, results: Dict[float, NestingResult]):
        """绘制多组排版结果"""
        self.axes.clear()
        
        if not results:
            self.axes.text(0.5, 0.5, 'No data', ha='center', va='center',
                          transform=self.axes.transAxes, fontsize=14)
            self.draw()
            return
        
        # 计算布局
        n_groups = len(results)
        board_widths = []
        for thickness, result in sorted(results.items()):
            max_width = max(b.width for b in result.boards) if result.boards else 0
            board_widths.append(max_width)
        
        # 水平排列各组
        x_offset = 0
        gap = 20  # 组间距
        
        colors = ['#2196F3', '#4CAF50', '#FF5722', '#00BCD4', '#E91E63']
        
        for idx, (thickness, result) in enumerate(sorted(results.items())):
            color = colors[idx % len(colors)]
            
            for board_idx, board in enumerate(result.boards):
                # 绘制板材边框
                x0 = x_offset
                y0 = -board.height - board_idx * (board.height + gap)
                
                self.axes.plot([x0, x0 + board.width, x0 + board.width, x0, x0],
                              [y0, y0, y0 + board.height, y0 + board.height, y0],
                              'k-', linewidth=2)
                
                # 绘制板材标签
                self.axes.text(x0 + board.width/2, y0 + board.height + 5,
                              f'{thickness}mm - {board.name}',
                              ha='center', va='bottom', fontsize=8, color=color)
                
                # 绘制放置的图形
                for p in board.placements:
                    px = x0 + p.x
                    py = y0 + p.y
                    w = p.actual_width
                    h = p.actual_height
                    
                    rect = mpatches.Rectangle((px, py), w, h,
                                             linewidth=1, edgecolor=color,
                                             facecolor=color, alpha=0.3)
                    self.axes.add_patch(rect)
                    self.axes.text(px + w/2, py + h/2, str(p.rect.id),
                                  ha='center', va='center', fontsize=6)
            
            # 更新下一组的X偏移
            if result.boards:
                max_width = max(b.width for b in result.boards)
                x_offset += max_width + gap
        
        # 设置坐标轴
        self.axes.set_aspect('equal')
        self.axes.grid(True, alpha=0.3)
        self.axes.set_title(f'排版预览 ({n_groups} 个厚度组)')
        
        self.draw()


class AutoNestingApp(QMainWindow):
    """自动排版主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setGeometry(50, 50, 1200, 800)
        
        self.source_dxf_path = None
        self.parser = None
        self.results: Dict[float, NestingResult] = {}
        
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 顶部控制区
        control_layout = QHBoxLayout()
        
        # DXF文件选择
        self.open_btn = QPushButton("导入DXF")
        self.open_btn.clicked.connect(self.open_dxf)
        control_layout.addWidget(self.open_btn)
        
        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet("color: gray; min-width: 200px;")
        control_layout.addWidget(self.file_label)
        
        control_layout.addStretch()
        
        # 间距设置
        spacing_group = QGroupBox("间距设置")
        spacing_layout = QHBoxLayout(spacing_group)
        spacing_layout.addWidget(QLabel("图形间距:"))
        self.spacing_spin = QDoubleSpinBox()
        self.spacing_spin.setRange(3.0, 10.0)
        self.spacing_spin.setValue(config.NESTING_SPACING)
        self.spacing_spin.setSuffix(" mm")
        self.spacing_spin.setSingleStep(0.5)
        spacing_layout.addWidget(self.spacing_spin)
        control_layout.addWidget(spacing_group)
        
        # 操作按钮
        self.nest_btn = QPushButton("执行排版")
        self.nest_btn.clicked.connect(self.execute_nesting)
        self.nest_btn.setEnabled(False)
        control_layout.addWidget(self.nest_btn)
        
        self.export_btn = QPushButton("导出DXF")
        self.export_btn.clicked.connect(self.export_dxf)
        self.export_btn.setEnabled(False)
        control_layout.addWidget(self.export_btn)
        
        layout.addLayout(control_layout)
        
        # 中间区域：预览 + 日志
        middle_layout = QHBoxLayout()
        
        # 预览区域
        self.preview_canvas = PreviewCanvas(self)
        middle_layout.addWidget(self.preview_canvas, stretch=3)
        
        # 日志区域
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.addWidget(QLabel("排版日志"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        middle_layout.addWidget(log_widget, stretch=1)
        
        layout.addLayout(middle_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态栏
        self.statusBar().showMessage("请导入DXF文件开始")
    
    def log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
    
    def open_dxf(self):
        """打开DXF文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择DXF文件", "",
            "DXF Files (*.dxf);;All Files (*.*)"
        )
        
        if not filepath:
            return
        
        self.source_dxf_path = filepath
        self.file_label.setText(os.path.basename(filepath))
        self.file_label.setStyleSheet("color: black;")
        
        self.statusBar().showMessage("正在解析DXF...")
        self.log(f"打开文件: {os.path.basename(filepath)}")
        
        self.parser = DxfParser(filepath)
        
        if self.parser.load():
            entities = self.parser.parse()
            
            # 解析文字标注
            text_parser = TextParser(self.parser.doc)
            thickness_groups = text_parser.parse()
            
            shapes = [s for s in entities if s.bbox and s.bbox.width > 0]
            
            self.log(f"  实体总数: {len(entities)}")
            self.log(f"  有效图形: {len(shapes)}")
            self.log(f"  厚度标注: {len(thickness_groups)} 种")
            
            for thickness, labels in sorted(thickness_groups.items()):
                self.log(f"    {thickness}mm: {len(labels)} 个标注")
            
            self.nest_btn.setEnabled(True)
            self.statusBar().showMessage(
                f"已加载: {len(shapes)} 个图形, {len(thickness_groups)} 种厚度"
            )
        else:
            QMessageBox.critical(self, "错误", "无法解析DXF文件")
    
    def execute_nesting(self):
        """执行排版"""
        if not self.parser:
            QMessageBox.warning(self, "警告", "请先导入DXF文件")
            return
        
        self.statusBar().showMessage("正在排版...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # 无限进度条
        
        # 获取有效图形
        shapes = [s for s in self.parser.entities if s.bbox and s.bbox.width > 0]
        
        if not shapes:
            QMessageBox.warning(self, "警告", "没有有效图形")
            return
        
        # 检测包含关系
        self.log("\n检测图形包含关系...")
        detector = ContainmentDetector()
        units = detector.detect(shapes)
        
        self.log(f"  检测到 {len(units)} 个图形单元")
        
        # 过滤超大单元（宽度或高度超过最大板材）
        max_board_width = 600 - 20  # 板材宽度 - 边距
        max_board_height = 850 - 20  # 板材高度 - 边距
        
        valid_units = []
        skipped_units = []
        for unit in units:
            w = unit.outer.bbox.width
            h = unit.outer.bbox.height
            if w > max_board_width or h > max_board_height:
                skipped_units.append(unit)
            else:
                valid_units.append(unit)
        
        if skipped_units:
            self.log(f"  跳过 {len(skipped_units)} 个超大单元:")
            for unit in skipped_units[:5]:
                self.log(f"    - {unit.handle}: {unit.outer.bbox.width:.0f}x{unit.outer.bbox.height:.0f}mm")
            if len(skipped_units) > 5:
                self.log(f"    ... 还有 {len(skipped_units)-5} 个")
        
        self.log(f"  有效单元: {len(valid_units)} 个")
        
        # 解析文字标注
        text_parser = TextParser(self.parser.doc)
        thickness_groups_labels = text_parser.parse()
        
        # 按厚度分组（使用单元的外层边界）
        grouper = ShapeGrouper()
        shape_groups = grouper.group_shapes(
            [{'handle': unit.handle, 'bbox': unit.outer.bbox, 'unit': unit} 
             for unit in valid_units],
            list(thickness_groups_labels.values())[0] if thickness_groups_labels else [],
            text_parser.skip_labels
        )
        
        self.log(f"\n{'='*40}")
        self.log("开始排版")
        self.log(f"{'='*40}")
        
        # 如果没有厚度标注，将所有单元作为一组
        if not shape_groups:
            self.log("未找到厚度标注，将所有图形作为一组处理")
            all_rects = []
            for i, unit in enumerate(valid_units):
                all_rects.append(Rect(
                    width=unit.outer.bbox.width,
                    height=unit.outer.bbox.height,
                    id=i,
                    handle=unit.handle,
                ))
            
            # 记录单元映射
            self.unit_map = {unit.handle: unit for unit in valid_units}
            
            # 获取用户设置的间距
            spacing = self.spacing_spin.value()
            
            result = find_optimal_boards(all_rects, spacing=spacing)
            shape_groups = {0.0: ShapeGroup(
                thickness=0.0,
                shapes=[{'handle': unit.handle, 'bbox': unit.outer.bbox, 'unit': unit} 
                        for unit in valid_units],
                label_x=0,
                label_y=0
            )}
            self.results = {0.0: result}
        else:
            # 为每组计算最优板材
            self.results = {}
            self.unit_map = {unit.handle: unit for unit in valid_units}
            
            # 获取用户设置的间距
            spacing = self.spacing_spin.value()
            
            for thickness, group in sorted(shape_groups.items()):
                self.log(f"\n处理 {thickness}mm 组 ({len(group.shapes)} 个单元)")
                
                # 创建矩形列表
                rects = []
                for i, shape_info in enumerate(group.shapes):
                    bbox = shape_info['bbox']
                    rects.append(Rect(
                        width=bbox.width,
                        height=bbox.height,
                        id=i,
                        handle=shape_info.get('handle', ''),
                    ))
                
                # 自动计算最优板材
                result = find_optimal_boards(rects, spacing=spacing)
                self.results[thickness] = result
                
                self.log(f"  板材方案: {len(result.boards)} 张")
                for board in result.boards:
                    self.log(f"    - {board.name}: {len(board.placements)} 个单元, "
                           f"利用率 {board.utilization:.1%}")
        
        self.progress_bar.setVisible(False)
        
        # 绘制预览
        self.preview_canvas.draw_multi_group(self.results)
        self.export_btn.setEnabled(True)
        
        # 显示结果摘要
        total_boards = sum(len(r.boards) for r in self.results.values())
        total_shapes = sum(r.placed_shapes for r in self.results.values())
        
        self.log(f"\n{'='*40}")
        self.log(f"排版完成！")
        self.log(f"总板材数: {total_boards}")
        self.log(f"已放置单元: {total_shapes}/{len(valid_units)}")
        self.log(f"{'='*40}")
        
        self.statusBar().showMessage(
            f"排版完成: {total_boards} 张板材, {total_shapes} 个单元"
        )
        
        QMessageBox.information(self, "排版完成",
                               f"排版完成！\n\n"
                               f"厚度组数: {len(self.results)}\n"
                               f"总板材数: {total_boards}\n"
                               f"已放置: {total_shapes}/{len(valid_units)} 个单元")
    
    def export_dxf(self):
        """导出排版结果为DXF文件"""
        if not self.results:
            QMessageBox.warning(self, "警告", "没有排版结果")
            return
        
        output_path, _ = QFileDialog.getSaveFileName(
            self, "保存排版结果", "排版结果.dxf",
            "DXF Files (*.dxf);;All Files (*.*)"
        )
        
        if not output_path:
            return
        
        self.statusBar().showMessage("正在导出...")
        self.log(f"\n导出到: {output_path}")
        
        # 创建写入器
        writer = DxfWriter(self.source_dxf_path) if self.source_dxf_path else None
        
        # 获取单元映射
        unit_map = getattr(self, 'unit_map', None)
        
        # 写入DXF
        success = writer.write_multi_group_results(
            self.results, output_path,
            gap=20,  # 组间距20mm
            unit_map=unit_map
        ) if writer else False
        
        if not success:
            # 简化模式
            from utils.dxf_writer import create_nested_dxf_simple
            # 合并所有排版结果
            all_placements = []
            for thickness, result in self.results.items():
                for board in result.boards:
                    all_placements.extend(board.placements)
            
            board_width = max(max(b.width for r in self.results.values() 
                                for b in r.boards) if r.boards else 400)
            board_height = max(max(b.height for r in self.results.values() 
                                 for b in r.boards) if r.boards else 850)
            
            success = create_nested_dxf_simple(
                all_placements, output_path, board_width, board_height,
                self.source_dxf_path
            )
        
        if success:
            self.log("导出成功！")
            self.statusBar().showMessage(f"已导出: {output_path}")
            QMessageBox.information(self, "导出成功",
                                   f"排版结果已保存到:\n{output_path}")
        else:
            self.log("导出失败！")
            QMessageBox.critical(self, "错误", "导出失败")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = AutoNestingApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
