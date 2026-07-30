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
        self._last_save_path = None
    
    def write_multi_group_results(self, results: Dict, output_path: str,
                                  gap: float = 50.0, unit_map: Dict = None,
                                  max_row_width: float = 6000.0,
                                  row_gap: float = 50.0) -> bool:
        """
        写入多组排版结果到DXF文件
        
        布局：所有板材（不分厚度）统一横向排列：从左到右依次摆放，
        当本行累计宽度超过 max_row_width 时换行（在新一行继续从左开始）。
        每张板块按其所属厚度分图层着色，框上方标 `长*宽*厚`。
        
        Args:
            results: Dict[float, NestingResult] 按厚度分组的排版结果
            output_path: 输出文件路径
            gap: 同行板材之间的水平间距 (mm)
            unit_map: Dict[str, ShapeUnit] 单元映射（可选，用于保留内部结构）
            max_row_width: 单行最大宽度，超过则换行 (mm)
            row_gap: 行间距 (mm)
            
        Returns:
            bool: 是否成功
        """
        try:
            # 创建目标文件
            self.target_doc = ezdxf.new(dxfversion='R2000')
            self.target_doc.units = units.MM
            msp = self.target_doc.modelspace()
            
            # 从源文件复刻图层表（保留原始图层名与颜色，使零件不改变颜色）
            self._import_source_layers()
            
            # 定义颜色（仅用于"厚度图层"，板块边框使用）
            thickness_colors = {
                0.5: 1,   # 红色
                1.0: 2,   # 黄色
                1.5: 3,   # 绿色
                2.0: 4,   # 青色
                3.0: 5,   # 蓝色
                4.0: 6,   # 洋红
                4.5: 6,   # 洋红
            }
            
            # 把所有厚度的板平铺为一个有序列表：按厚度升序，厚度内按 boards 顺序
            all_boards = []
            for thickness in sorted(results.keys()):
                for board in results[thickness].boards:
                    all_boards.append((thickness, board))
            
            # 横向排列（一行装不下换行）
            x = 0.0
            y = 50.0  # 顶部留 50mm 边距
            row_max_height = 0.0
            
            for thickness, board in all_boards:
                # 换行判定（首板不换）
                if x > 0 and x + board.width > max_row_width + 1e-6:
                    x = 0.0
                    y += row_max_height + row_gap
                    row_max_height = 0.0
                
                # 建图层（按厚度的颜色）
                if thickness >= 1000:
                    layer_name = f"行{int(thickness - 1000 + 1)}"
                    color = thickness_colors.get(thickness, 7)
                else:
                    layer_name = f"{thickness}mm"
                    color = thickness_colors.get(thickness, 7)
                if layer_name not in self.target_doc.layers:
                    self.target_doc.layers.add(layer_name, color=color)
                
                x0 = x
                y0 = y
                
                # 板材边框
                msp.add_lwpolyline([
                    (x0, y0),
                    (x0 + board.width, y0),
                    (x0 + board.width, y0 + board.height),
                    (x0, y0 + board.height),
                    (x0, y0),
                ], dxfattribs={'layer': layer_name})
                
                # 板材标签：长*宽*厚，放框上方
                # 虚拟行组（>=1000）显示为"行N"而非厚度值
                if thickness >= 1000:
                    th_display = f"行{int(thickness - 1000 + 1)}"
                else:
                    th_display = f"{thickness}"
                msp.add_text(
                    f"{board.width:.0f}*{board.height:.0f}*{th_display}",
                    dxfattribs={
                        'layer': layer_name,
                        'height': 15,
                        'insert': (x0 + board.width / 2, y0 + board.height + 10),
                    }
                )
                
                # 放置图形
                for p in board.placements:
                    self._draw_placement_with_unit(msp, p, x0, y0,
                                                 layer_name, unit_map)
                
                x += board.width + gap
                row_max_height = max(row_max_height, board.height)
            
            # 保存文件
            self._last_save_path = output_path
            self.target_doc.saveas(output_path)
            # saveas 会把 EXTMIN/MAX 重置为 ±1e20，须保存后再改并再次保存
            self._recalculate_extents()
            print(f"排版结果已保存到: {output_path}")
            return True
            
        except Exception as e:
            print(f"写入多组结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _import_source_layers(self):
        """从源DXF复刻图层表（名称+颜色），使零件保留原始图层与颜色。"""
        try:
            src = ezdxf.readfile(self.source_path)
        except Exception:
            return
        for src_layer in src.layers:
            name = src_layer.dxf.name
            if name in self.target_doc.layers:
                continue
            try:
                self.target_doc.layers.add(name, color=src_layer.dxf.color)
            except Exception:
                pass
    
    def _recalculate_extents(self):
        """重算 EXTMIN/EXTMAX/LIMMIN/LIMMAX，避免 CAD 打开时视野被无效范围卡死。
        ezdxf saveas 会把 EXTMIN/MAX 强行重置为 ±1e20，导致 AutoCAD 打开后滚轮缩放几乎
        无反应、上下也拖不动。这里在 saveas 之后直接以纯文本方式修补 DXF 文件中
        $EXTMIN/$EXTMAX/$LIMMIN/$LIMMAX 后继数值，避开 ezdxf 的覆盖。
        """
        try:
            path = self._last_save_path
            if not path or not os.path.exists(path):
                return
            # 用 ezdxf 读回，计算实际范围
            doc = ezdxf.readfile(path)
            msp = doc.modelspace()
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')
            found = False
            for e in msp:
                pts = self._entity_xy(e)
                if not pts:
                    continue
                found = True
                for x, y in pts:
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
            if not found:
                return
            padx = pady = 50.0
            min_x -= padx; min_y -= pady
            max_x += padx; max_y += pady
            # 读出纯文本，按 $EXTMIN/$EXTMAX/$LIMMIN/$LIMMAX 标记定位并改后续数值行
            with open(path, 'r', encoding='latin-1') as f:
                lines = f.read().splitlines()
            self._patch_header_var(lines, '$EXTMIN', [min_x, min_y, 0.0])
            self._patch_header_var(lines, '$EXTMAX', [max_x, max_y, 0.0])
            self._patch_header_var(lines, '$LIMMIN', [min_x, min_y])
            self._patch_header_var(lines, '$LIMMAX', [max_x, max_y])
            with open(path, 'w', encoding='latin-1') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception:
            pass
    
    def _patch_header_var(self, lines, var_name, values):
        """在 DXF 文本行中找到 `$VARNAME` (前一行是组码 9) 后续的 10/20(/30) 数值，
        改写为 values 给出的值。values 的长度对应需要改的数值个数（2 或 3）。"""
        idx = 0
        n = len(lines)
        for i in range(n - 1):
            if lines[i].strip() == '9' and lines[i + 1].strip() == var_name:
                idx = i + 2
                break
        if idx == 0:
            return
        # 后继成对出现 "组码 / 数值"；按需要改的组码依次匹配
        want_codes = ['10', '20', '30'][:len(values)]
        code_ptr = 0
        k = idx
        while code_ptr < len(want_codes) and k + 1 < n:
            if lines[k].strip() == want_codes[code_ptr]:
                lines[k + 1] = repr(float(values[code_ptr]))
                code_ptr += 1
                k += 2
            else:
                k += 2
    
    def _entity_xy(self, e):
        """提取实体的(x,y)顶点序列（仅用于计算包围盒）"""
        try:
            dt = e.dxftype()
            if dt == 'LWPOLYLINE':
                return [(p[0], p[1]) for p in e]
            if dt == 'POLYLINE':
                return [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            if dt == 'CIRCLE':
                cx, cy = e.dxf.center.x, e.dxf.center.y; r = e.dxf.radius
                return [(cx - r, cy - r), (cx + r, cy + r)]
            if dt == 'LINE':
                s, ee = e.dxf.start, e.dxf.end
                return [(s.x, s.y), (ee.x, ee.y)]
            if dt in ('TEXT', 'MTEXT'):
                pt = e.dxf.insert
                return [(pt.x, pt.y)]
        except Exception:
            return None
        return None
    
    def _draw_placement_with_unit(self, msp, placement, x0, y0, 
                                 layer_name, unit_map=None):
        """
        绘制放置的图形（包括内部结构，正确处理旋转）
        """
        px = x0 + placement.x
        py = y0 + placement.y
        w = placement.actual_width
        h = placement.actual_height
        
        handle = placement.rect.handle
        unit = unit_map.get(handle) if unit_map else None
        
        if unit:
            outer = unit.outer
            # 原始中心
            orig_cx = (outer.bbox.x_min + outer.bbox.x_max) / 2
            orig_cy = (outer.bbox.y_min + outer.bbox.y_max) / 2
            
            if placement.rotated:
                # 旋转90°：宽高互换
                new_w = outer.bbox.height
                new_h = outer.bbox.width
            else:
                new_w = outer.bbox.width
                new_h = outer.bbox.height
            
            # 新中心 = 放置位置(左下角) + 新尺寸的一半
            new_cx = px + new_w / 2
            new_cy = py + new_h / 2
            
            if placement.rotated:
                # 旋转90° CCW：先移到原中心，旋转，再移到新中心
                def transform(x, y):
                    dx = x - orig_cx
                    dy = y - orig_cy
                    # CCW: (dx, dy) -> (-dy, dx)
                    return (new_cx - dy, new_cy + dx)
            else:
                # 只平移
                def transform(x, y):
                    return (x + (new_cx - orig_cx), y + (new_cy - orig_cy))
            
            # 绘制外层边界和内部图形（共享同一变换）
            self._draw_entity(msp, outer, transform, layer_name)
            for inner in unit.inner:
                self._draw_entity(msp, inner, transform, layer_name)
        else:
            # 无单元信息，绘制矩形占位
            msp.add_lwpolyline([
                (px, py),
                (px + w, py),
                (px + w, py + h),
                (px, py + h),
                (px, py),
            ], dxfattribs={'layer': layer_name})
    
    def _draw_entity(self, msp, entity, transform, layer_name):
        """根据实体类型绘制图形（应用变换函数）
        
        layer_name 为默认图层（厚度图层）；
        实际绘制时优先用实体自身的原始图层名（保留原色），不存在则回退默认。
        """
        etype = entity.entity_type
        coords = [transform(x, y) for x, y in entity.coordinates]
        # 优先使用实体原始图层（保留原色），否则用默认厚度图层
        draw_layer = getattr(entity, 'layer', None) or layer_name
        
        if etype == 'CIRCLE':
            # CIRCLE 实体：用 add_circle 绘制更准确
            if len(coords) >= 36:
                cx = sum(p[0] for p in coords[:36]) / 36
                cy = sum(p[1] for p in coords[:36]) / 36
                r = ((coords[0][0] - cx) ** 2 + (coords[0][1] - cy) ** 2) ** 0.5
                if r > 0.01:
                    msp.add_circle((cx, cy), r, dxfattribs={'layer': draw_layer})
                    return
        
        # POLYLINE / LWPOLYLINE / LINE / POINT / 等：用 lwpolyline 绘制
        if len(coords) >= 2:
            # 只在闭合时添加闭合点，不强制闭合开放线段
            if entity.closed and coords[0] != coords[-1]:
                coords.append(coords[0])
            msp.add_lwpolyline(coords, dxfattribs={'layer': draw_layer})
    
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
