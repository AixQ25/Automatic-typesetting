"""
DXF文件写入器
将排版结果写入新的DXF文件
"""

import os
import sys
import math
from typing import List, Tuple, Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ezdxf
from ezdxf import units

from nesting.rect_nesting import Placement


class DxfWriter:
    """DXF文件写入器"""
    
    def __init__(self, source_dxf_path: str):
        """
        初始化写入器
        
        Args:
            source_dxf_path: 源DXF文件路径
        """
        self.source_path = source_dxf_path
        self.source_doc = None
        self.target_doc = None
    
    def write_multi_group_results(self, results: Dict, output_path: str,
                                  gap: float = 50.0, unit_map: Dict = None) -> bool:
        """
        写入多组排版结果到DXF文件
        
        Args:
            results: Dict[float, NestingResult] 按厚度分组的排版结果
            output_path: 输出文件路径
            gap: 组间距 (mm)，默认50mm
            unit_map: Dict[str, ShapeUnit] 单元映射（可选，用于保留内部结构）
            
        Returns:
            bool: 是否成功
        """
        try:
            # 创建目标文件
            self.target_doc = ezdxf.new(dxfversion='R2000')
            self.target_doc.units = units.MM
            msp = self.target_doc.modelspace()
            
            # 定义颜色
            thickness_colors = {
                0.5: 1,   # 红色
                1.0: 2,   # 黄色
                1.5: 3,   # 绿色
                2.0: 4,   # 青色
                3.0: 5,   # 蓝色
                4.0: 6,   # 洋红
            }
            
            # 水平排列各组
            x_offset = 0
            
            for thickness in sorted(results.keys()):
                result = results[thickness]
                if not result.boards:
                    continue
                
                # 创建图层
                layer_name = f"{thickness}mm"
                color = thickness_colors.get(thickness, 7)
                if layer_name not in self.target_doc.layers:
                    self.target_doc.layers.add(layer_name, color=color)
                
                # 计算本组最大宽度
                max_board_width = max(b.width for b in result.boards)
                
                # 绘制每个板材
                y_offset = 50  # 顶部留50mm边距，方便操作
                
                for board_idx, board in enumerate(result.boards):
                    # 板材边框
                    x0 = x_offset
                    y0 = y_offset
                    
                    # 绘制板材边框
                    msp.add_lwpolyline([
                        (x0, y0),
                        (x0 + board.width, y0),
                        (x0 + board.width, y0 + board.height),
                        (x0, y0 + board.height),
                        (x0, y0),
                    ], dxfattribs={'layer': layer_name})
                    
                    # 添加板材标签（格式：长*宽*厚，在框的上方）
                    msp.add_text(
                        f"{board.width:.0f}*{board.height:.0f}*{thickness}",
                        dxfattribs={
                            'layer': layer_name,
                            'height': 15,  # 字体高度15mm
                            'insert': (x0 + board.width / 2, y0 + board.height + 10)
                        }
                    )
                    
                    # 绘制放置的图形
                    for p in board.placements:
                        self._draw_placement_with_unit(msp, p, x0, y0, 
                                                     layer_name, unit_map)
                    
                    # 更新Y偏移（板材间距改为50mm）
                    y_offset += board.height + 50
                
                # 更新X偏移
                x_offset += max_board_width + gap
            
            # 保存文件
            self.target_doc.saveas(output_path)
            print(f"排版结果已保存到: {output_path}")
            return True
            
        except Exception as e:
            print(f"写入多组结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _draw_placement_with_unit(self, msp, placement, x0, y0, 
                                 layer_name, unit_map=None):
        """
        绘制放置的图形（包括内部结构）
        
        Args:
            msp: 模型空间
            placement: 放置信息
            x0, y0: 板材偏移
            layer_name: 图层名
            unit_map: 单元映射
        """
        px = x0 + placement.x
        py = y0 + placement.y
        w = placement.actual_width
        h = placement.actual_height
        
        # 计算偏移量（从原始位置到新位置）
        handle = placement.rect.handle
        unit = unit_map.get(handle) if unit_map else None
        
        if unit:
            # 有单元信息，绘制完整结构
            outer = unit.outer
            outer_bbox = outer.bbox
            
            # 计算外层边界原始左下角
            orig_x = outer_bbox.x_min
            orig_y = outer_bbox.y_min
            
            # 计算偏移量
            dx = px - orig_x
            dy = py - orig_y
            
            # 绘制外层边界（外围框）
            outer_coords = [(x + dx, y + dy) for x, y in outer.coordinates]
            # 确保闭合
            if outer_coords[0] != outer_coords[-1]:
                outer_coords.append(outer_coords[0])
            msp.add_lwpolyline(outer_coords, dxfattribs={'layer': layer_name})
            
            # 绘制内部图形
            for inner in unit.inner:
                inner_coords = [(x + dx, y + dy) for x, y in inner.coordinates]
                # 确保闭合
                if inner_coords[0] != inner_coords[-1]:
                    inner_coords.append(inner_coords[0])
                msp.add_lwpolyline(inner_coords, dxfattribs={'layer': layer_name})
        else:
            # 无单元信息，绘制矩形占位
            msp.add_lwpolyline([
                (px, py),
                (px + w, py),
                (px + w, py + h),
                (px, py + h),
                (px, py),
            ], dxfattribs={'layer': layer_name})
    
    def create_nested_dxf(self, placements: List[Placement],
                          output_path: str,
                          board_width: float,
                          board_height: float) -> bool:
        """
        创建排版后的DXF文件
        
        Args:
            placements: 排版结果列表
            output_path: 输出文件路径
            board_width: 板材宽度
            board_height: 板材高度
            
        Returns:
            bool: 是否成功
        """
        try:
            # 加载源文件
            self.source_doc = ezdxf.readfile(self.source_path)
            
            # 创建目标文件
            self.target_doc = ezdxf.new(dxfversion='R2000')
            self.target_doc.units = units.MM
            msp = self.target_doc.modelspace()
            
            # 创建图层
            if '排版结果' not in self.target_doc.layers:
                self.target_doc.layers.add('排版结果', color=1)
            
            # 从源文件提取所有实体的坐标信息（按句柄索引）
            source_coords = {}
            source_msp = self.source_doc.modelspace()
            for e in source_msp:
                try:
                    handle = e.dxf.handle
                    coords = self._extract_coords(e)
                    if coords:
                        source_coords[handle] = coords
                except:
                    pass
            
            # 处理每个排版位置
            for i, placement in enumerate(placements):
                handle = getattr(placement.rect, 'handle', None)
                
                if handle and handle in source_coords:
                    coords = source_coords[handle]
                    # 计算原始左下角
                    xs = [p[0] for p in coords]
                    ys = [p[1] for p in coords]
                    orig_x = min(xs)
                    orig_y = min(ys)
                    
                    # 计算偏移量
                    dx = placement.x - orig_x
                    dy = placement.y - orig_y
                    
                    # 在新文件中绘制
                    new_coords = [(x + dx, y + dy) for x, y in coords]
                    
                    # 用LWPOLYLINE绘制（兼容性最好）
                    msp.add_lwpolyline(
                        new_coords,
                        dxfattribs={'layer': '排版结果'}
                    )
                else:
                    # 占位矩形
                    self._draw_placeholder(msp, placement, i)
            
            # 绘制板材边框
            self._draw_board_outline(msp, board_width, board_height)
            
            # 保存文件
            self.target_doc.saveas(output_path)
            print(f"排版结果已保存到: {output_path} ({len(placements)} 个图形)")
            return True
            
        except Exception as e:
            print(f"创建排版DXF失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _extract_coords(self, entity) -> Optional[List[Tuple[float, float]]]:
        """提取实体的坐标列表"""
        try:
            dxftype = entity.dxftype()
            
            if dxftype == 'POLYLINE':
                verts = list(entity.vertices)
                if not verts:
                    return None
                coords = [(v.dxf.location.x, v.dxf.location.y) for v in verts]
                if entity.is_closed and coords[0] != coords[-1]:
                    coords.append(coords[0])
                return coords
            
            elif dxftype == 'LWPOLYLINE':
                pts = list(entity)
                if not pts:
                    return None
                coords = [(p[0], p[1]) for p in pts]
                return coords
            
            elif dxftype == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                coords = []
                for i in range(36):
                    angle = 2 * 3.141592653589793 * i / 36
                    x = center.x + radius * math.cos(angle)
                    y = center.y + radius * math.sin(angle)
                    coords.append((x, y))
                coords.append(coords[0])
                return coords
            
            elif dxftype == 'LINE':
                s = entity.dxf.start
                e = entity.dxf.end
                return [(s.x, s.y), (e.x, e.y)]
            
            else:
                return None
                
        except:
            return None
    
    def _draw_placeholder(self, msp, placement, index):
        """绘制占位矩形"""
        x = placement.x
        y = placement.y
        w = placement.actual_width
        h = placement.actual_height
        
        msp.add_lwpolyline([
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
            (x, y),
        ], dxfattribs={'layer': '排版结果', 'color': 1})
    
    def _draw_board_outline(self, msp, width: float, height: float):
        """绘制板材边框"""
        msp.add_lwpolyline([
            (0, 0),
            (width, 0),
            (width, height),
            (0, height),
            (0, 0),
        ], dxfattribs={'layer': '排版结果', 'color': 2})  # 黄色边框


def create_nested_dxf_simple(placements: List[Placement],
                             output_path: str,
                             board_width: float,
                             board_height: float,
                             source_path: str = None) -> bool:
    """
    创建排版结果的DXF文件（简化版）
    如果源文件可用则复制实体，否则绘制矩形
    
    Args:
        placements: 排版结果
        output_path: 输出路径
        board_width: 板材宽度
        board_height: 板材高度
        source_path: 源DXF文件路径
        
    Returns:
        bool: 是否成功
    """
    if source_path and os.path.exists(source_path):
        writer = DxfWriter(source_path)
        return writer.create_nested_dxf(placements, output_path,
                                        board_width, board_height)
    else:
        writer = DxfWriter.__new__(DxfWriter)
        writer.target_doc = ezdxf.new(dxfversion='R2000')
        writer.target_doc.units = units.MM
        msp = writer.target_doc.modelspace()
        
        if '排版结果' not in writer.target_doc.layers:
            writer.target_doc.layers.add('排版结果', color=1)
        
        for i, p in enumerate(placements):
            writer._draw_placeholder(msp, p, i)
        
        writer._draw_board_outline(msp, board_width, board_height)
        writer.target_doc.saveas(output_path)
        print(f"排版结果已保存到: {output_path}")
        return True


# 测试
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    from nesting.rect_nesting import Rect, RectNesting
    
    # 先获取源文件的实体句柄
    handles = []
    layers = []
    if os.path.exists('test.dxf'):
        from utils.dxf_parser import DxfParser
        parser = DxfParser('test.dxf')
        if parser.load():
            entities = parser.parse()
            handles = [e.handle for e in entities]
            layers = [e.layer for e in entities]
    
    # 使用前10个实体的MBR创建矩形
    rects = []
    for i, e in enumerate(parser.entities[:10]):
        if e.bbox:
            rects.append(Rect(
                width=e.bbox.width,
                height=e.bbox.height,
                id=i,
                handle=e.handle,
            ))
    
    nestor = RectNesting(400, 850, 10)
    placements = nestor.nest(rects)
    
    # 写出版本1：简单矩形
    output1 = 'test_output_simple.dxf'
    create_nested_dxf_simple(placements, output1, 400, 850)
    
    # 写出版本2：从源文件复制
    if os.path.exists('test.dxf'):
        output2 = 'test_output_copy.dxf'
        create_nested_dxf_simple(placements, output2, 400, 850, 'test.dxf')
