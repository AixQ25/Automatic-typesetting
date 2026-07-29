"""
DXF文件解析器
使用ezdxf读取DXF文件，提取实体几何信息
"""

import math
import sys
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ezdxf
from ezdxf.entities import Polyline, LWPolyline, Circle, Arc, Line, Spline, Ellipse

from geometry_utils import calculate_bounding_box, BoundingBox


@dataclass
class DxfEntity:
    """DXF实体"""
    handle: str                 # 实体句柄
    entity_type: str            # 实体类型
    layer: str                  # 图层名
    coordinates: List[Tuple[float, float]]  # 顶点坐标
    closed: bool = False        # 是否闭合
    bbox: Optional[BoundingBox] = None  # 边界框
    area: float = 0.0           # 面积


class DxfParser:
    """DXF文件解析器"""
    
    def __init__(self, filepath: str):
        """
        初始化解析器
        
        Args:
            filepath: DXF文件路径
        """
        self.filepath = filepath
        self.doc = None
        self.entities: List[DxfEntity] = []
    
    def load(self) -> bool:
        """
        加载DXF文件
        
        Returns:
            bool: 是否加载成功
        """
        try:
            self.doc = ezdxf.readfile(self.filepath)
            return True
        except Exception as e:
            print(f"加载DXF文件失败: {e}")
            return False
    
    def parse(self) -> List[DxfEntity]:
        """
        解析所有实体
        
        Returns:
            List[DxfEntity]: 解析后的实体列表
        """
        if not self.doc:
            print("未加载DXF文件")
            return []
        
        self.entities = []
        msp = self.doc.modelspace()
        
        for entity in msp:
            if entity.dxftype() == 'INSERT':
                # INSERT 实体返回多个几何实体
                parsed_entities = self._parse_insert(entity)
                self.entities.extend(parsed_entities)
            else:
                dxf_entity = self._parse_entity(entity)
                if dxf_entity:
                    self.entities.append(dxf_entity)
        
        return self.entities
    
    def _parse_entity(self, entity) -> Optional[DxfEntity]:
        """
        解析单个实体
        
        Args:
            entity: ezdxf实体对象
            
        Returns:
            DxfEntity: 解析后的实体
        """
        try:
            dxftype = entity.dxftype()
            
            if dxftype == 'POLYLINE':
                return self._parse_polyline(entity)
            elif dxftype == 'LWPOLYLINE':
                return self._parse_lwpolyline(entity)
            elif dxftype == 'CIRCLE':
                return self._parse_circle(entity)
            elif dxftype == 'ARC':
                return self._parse_arc(entity)
            elif dxftype == 'LINE':
                return self._parse_line(entity)
            elif dxftype == 'SPLINE':
                return self._parse_spline(entity)
            elif dxftype == 'ELLIPSE':
                return self._parse_ellipse(entity)
            elif dxftype == 'INSERT':
                return self._parse_insert(entity)
            else:
                return None
                
        except Exception as e:
            print(f"解析实体失败 ({dxftype}): {e}")
            return None
    
    def _parse_polyline(self, entity: Polyline) -> Optional[DxfEntity]:
        """解析POLYLINE实体"""
        vertices = list(entity.vertices)
        if not vertices:
            return None
        
        coords = [(v.dxf.location.x, v.dxf.location.y) for v in vertices]
        closed = bool(entity.is_closed)
        
        bbox = calculate_bounding_box(coords)
        area = abs(calculate_polygon_area(coords))
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='POLYLINE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=closed,
            bbox=bbox,
            area=area
        )
    
    def _parse_lwpolyline(self, entity: LWPolyline) -> Optional[DxfEntity]:
        """解析LWPOLYLINE实体"""
        points = list(entity)
        if not points:
            return None
        
        coords = [(p[0], p[1]) for p in points]
        closed = bool(entity.closed)
        
        bbox = calculate_bounding_box(coords)
        area = abs(calculate_polygon_area(coords))
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='LWPOLYLINE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=closed,
            bbox=bbox,
            area=area
        )
    
    def _parse_circle(self, entity: Circle) -> Optional[DxfEntity]:
        """解析CIRCLE实体"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        
        # 用36个点近似圆
        coords = []
        for i in range(36):
            angle = 2 * math.pi * i / 36
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            coords.append((x, y))
        coords.append(coords[0])  # 闭合
        
        bbox = calculate_bounding_box(coords)
        area = math.pi * radius * radius
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='CIRCLE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=True,
            bbox=bbox,
            area=area
        )
    
    def _parse_arc(self, entity: Arc) -> Optional[DxfEntity]:
        """解析ARC实体"""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle / 180.0 * math.pi
        end_angle = entity.dxf.end_angle / 180.0 * math.pi
        
        # 生成弧线上的点
        coords = []
        steps = 20
        for i in range(steps + 1):
            angle = start_angle + (end_angle - start_angle) * i / steps
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            coords.append((x, y))
        
        bbox = calculate_bounding_box(coords)
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='ARC',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=False,
            bbox=bbox,
            area=0.0
        )
    
    def _parse_line(self, entity: Line) -> Optional[DxfEntity]:
        """解析LINE实体"""
        start = entity.dxf.start
        end = entity.dxf.end
        coords = [(start.x, start.y), (end.x, end.y)]
        
        bbox = calculate_bounding_box(coords)
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='LINE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=False,
            bbox=bbox,
            area=0.0
        )
    
    def _parse_spline(self, entity: Spline) -> Optional[DxfEntity]:
        """解析SPLINE实体"""
        try:
            fit_points = list(entity.fit_points)
            if not fit_points:
                control_points = list(entity.control_points)
                if not control_points:
                    return None
                coords = [(p.x, p.y) for p in control_points]
            else:
                coords = [(p.x, p.y) for p in fit_points]
        except:
            try:
                pts = list(entity.control_points)
                coords = [(p.x, p.y) for p in pts]
            except:
                return None
        
        if not coords:
            return None
        
        bbox = calculate_bounding_box(coords)
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='SPLINE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=bool(entity.closed),
            bbox=bbox,
            area=0.0
        )
    
    def _parse_ellipse(self, entity: Ellipse) -> Optional[DxfEntity]:
        """解析ELLIPSE实体"""
        center = entity.dxf.center
        major = entity.dxf.major_axis
        ratio = entity.dxf.ratio
        
        # 用36个点近似椭圆
        coords = []
        for i in range(36):
            angle = 2 * math.pi * i / 36
            x = center.x + major.x * math.cos(angle) * ratio
            y = center.y + major.y * math.sin(angle)
            coords.append((x, y))
        coords.append(coords[0])
        
        bbox = calculate_bounding_box(coords)
        
        return DxfEntity(
            handle=entity.dxf.handle,
            entity_type='ELLIPSE',
            layer=entity.dxf.layer,
            coordinates=coords,
            closed=True,
            bbox=bbox,
            area=0.0
        )
    
    def _parse_insert(self, entity) -> List[DxfEntity]:
        """解析INSERT实体（块引用），返回所有几何实体"""
        try:
            # 获取块定义
            block_name = entity.dxf.name
            block = self.doc.blocks.get(block_name)
            
            if not block:
                print(f"块定义不存在: {block_name}")
                return []
            
            # 收集块中的所有几何实体
            result = []
            for block_entity in block:
                if block_entity.dxftype() in ['POLYLINE', 'LWPOLYLINE', 'CIRCLE', 'ARC', 'LINE', 'SPLINE', 'ELLIPSE']:
                    parsed = self._parse_entity(block_entity)
                    if parsed:
                        # 更新句柄为 INSERT 的句柄 + 块内实体句柄
                        parsed.handle = f"{entity.dxf.handle}_{block_entity.dxf.handle}"
                        parsed.entity_type = block_entity.dxftype()
                        result.append(parsed)
            
            return result
            
        except Exception as e:
            print(f"解析INSERT失败: {e}")
            return []
    
    def get_shapes_with_mbr(self) -> List[dict]:
        """
        获取所有图形的MBR信息，用于排样
        
        Returns:
            List[dict]: [{'handle': h, 'width': w, 'height': h, 'area': a}, ...]
        """
        result = []
        for e in self.entities:
            if e.bbox:
                result.append({
                    'handle': e.handle,
                    'width': e.bbox.width,
                    'height': e.bbox.height,
                    'area': e.area,
                    'layer': e.layer,
                })
        return result


def calculate_polygon_area(coords: List[Tuple[float, float]]) -> float:
    """
    计算多边形面积 (Shoelace公式)
    """
    if len(coords) < 3:
        return 0.0
    
    area = 0.0
    n = len(coords)
    
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    
    return abs(area) / 2.0


# 测试
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    parser = DxfParser('test.dxf')
    if parser.load():
        entities = parser.parse()
        print(f"解析到 {len(entities)} 个实体:")
        for e in entities:
            bbox = e.bbox
            print(f"  {e.entity_type}: layer={e.layer}, "
                  f"closed={e.closed}, verts={len(e.coordinates)}, "
                  f"MBR=({bbox.width:.1f}, {bbox.height:.1f}), area={e.area:.1f}")
