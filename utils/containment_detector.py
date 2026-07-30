"""
包含关系检测器
检测图形之间的包含关系，将外层边界和内部图形合并为一个单元
"""

import sys
import os
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.dxf_parser import DxfEntity


@dataclass
class ShapeUnit:
    """形状单元（外层边界 + 所有内部图形）"""
    outer: DxfEntity           # 外层边界
    inner: List[DxfEntity]     # 内部图形列表
    total_area: float          # 总面积（外层面积）
    handle: str                # 主句柄（外层句柄）
    oversized: bool = False    # 是否为超大容器/单元（应略过）
    
    @property
    def all_entities(self) -> List[DxfEntity]:
        """获取所有实体（外层+内部）"""
        return [self.outer] + self.inner


# 板材可用区域（600x850 - 10mm边距*2 = 580x830）。
# 任一边超过可用区即无法装入板材 → 视为容器/超大，剥离其父级资格（防吞件）。
_MAX_PART_WIDTH = 600 - 20    # 580
_MAX_PART_HEIGHT = 850 - 20   # 830


def _bbox_area(bbox) -> float:
    """边界框面积"""
    return bbox.width * bbox.height


class ContainmentDetector:
    """包含关系检测器"""
    
    def __init__(self, min_area: float = 0.1,
                 max_part_width: float = _MAX_PART_WIDTH,
                 max_part_height: float = _MAX_PART_HEIGHT):
        """
        初始化检测器
        
        Args:
            min_area: 最小面积阈值（仅过滤零长线，小圆不误删）
            max_part_width: 单件最大可用宽度，超过视为容器/超大
            max_part_height: 单件最大可用高度，超过视为容器/超大
        """
        self.min_area = min_area
        self.max_part_width = max_part_width
        self.max_part_height = max_part_height
    
    def detect(self, entities: List[DxfEntity]) -> List[ShapeUnit]:
        """
        检测包含关系，将图形分组为单元
        
        关键：先把“容器/参考框/超大线”剥离，使其不充当父级，
        否则会把整排零件全部吞成一个巨单元（随后被略过 → 大量丢件、小圆丢失）。
        被剥离的容器仍以 oversized 单元返回，供上层按“超大略过”报告。
        
        Args:
            entities: 实体列表
            
        Returns:
            List[ShapeUnit]: 形状单元列表
        """
        # 过滤零长线（保留小圆与小线段）
        valid_entities = [e for e in entities 
                         if e.bbox and (e.area >= self.min_area or len(e.coordinates) >= 2)]
        
        if not valid_entities:
            return []
        
        # 剥离“容器/参考框”：任一边超过板材可用区的实体
        # 这些实体无法排进 600x850，且常是参考框/整排容器，会错误吞并内部零件
        oversized_entities = []
        normal_entities = []
        for e in valid_entities:
            if (e.bbox.width > self.max_part_width or 
                e.bbox.height > self.max_part_height):
                oversized_entities.append(e)
            else:
                normal_entities.append(e)
        
        units: List[ShapeUnit] = []
        
        # 1) 被剥离的容器：各自作为 oversized 单元返回（不参与树，不再吞件）
        #    检测其自身是否也包含正常件之外的内件（一般无），inner 留空
        for e in oversized_entities:
            units.append(ShapeUnit(
                outer=e,
                inner=[],
                total_area=_bbox_area(e.bbox),
                handle=e.handle,
                oversized=True,
            ))
        
        # 2) 正常件之间构建包含树（外框 + 内件成整体）
        units.extend(self._build_tree(normal_entities))
        
        return units
    
    def _build_tree(self, entities: List[DxfEntity]) -> List[ShapeUnit]:
        """在正常尺寸实体间构建外框+内件的整体单元"""
        if not entities:
            return []
        
        # 用边界框面积作为“大小”度量（比 shoelace 面积更稳健，开闭合多线均可用）
        data = []
        for entity in entities:
            try:
                data.append({
                    'entity': entity,
                    'size': _bbox_area(entity.bbox),  # bbox 面积
                    'bbox': entity.bbox,
                })
            except Exception:
                continue
        
        # 按尺寸降序
        data.sort(key=lambda x: x['size'], reverse=True)
        
        # 检测包含关系：bbox_i 被 bbox_j 完全包含 → j 为父
        # 取尺寸最小的包含者（最近父级），避免跨层误并
        parent_map = {}      # handle -> parent_handle
        children_map = {}    # handle -> [child_handles]
        
        for i, di in enumerate(data):
            handle_i = di['entity'].handle
            bbox_i = di['bbox']
            size_i = di['size']
            
            parent = None
            min_parent_size = float('inf')
            
            for j, dj in enumerate(data):
                if i == j:
                    continue
                bbox_j = dj['bbox']
                size_j = dj['size']
                
                # 父级必须更大（严格 >，避免等大的图形互为父子）
                if size_j <= size_i:
                    continue
                
                # bbox 完全包含
                if (bbox_j.x_min <= bbox_i.x_min + 1e-6 and 
                    bbox_j.y_min <= bbox_i.y_min + 1e-6 and
                    bbox_j.x_max >= bbox_i.x_max - 1e-6 and 
                    bbox_j.y_max >= bbox_i.y_max - 1e-6):
                    if size_j < min_parent_size:
                        min_parent_size = size_j
                        parent = dj['entity'].handle
            
            if parent:
                parent_map[handle_i] = parent
                children_map.setdefault(parent, []).append(handle_i)
        
        entity_map = {d['entity'].handle: d['entity'] for d in data}
        used_handles = set()
        units: List[ShapeUnit] = []
        
        # 顶级图形（无父级）→ 成为单元的外层
        for d in data:
            handle = d['entity'].handle
            if handle in parent_map:
                continue
            entity = d['entity']
            
            inner_entities: List[DxfEntity] = []
            self._collect_descendants(handle, children_map, entity_map,
                                       inner_entities, used_handles)
            
            units.append(ShapeUnit(
                outer=entity,
                inner=inner_entities,
                total_area=d['size'],
                handle=handle,
                oversized=False,
            ))
            used_handles.add(handle)
        
        return units
    
    def _collect_descendants(self, handle: str, children_map: Dict,
                           entity_map: Dict, result: List, used_handles: Set):
        """递归收集所有子孙实体"""
        if handle in children_map:
            for child_handle in children_map[handle]:
                if child_handle not in used_handles:
                    result.append(entity_map[child_handle])
                    used_handles.add(child_handle)
                    self._collect_descendants(child_handle, children_map, 
                                           entity_map, result, used_handles)


# 测试
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import ezdxf
    
    # 测试包含关系检测
    print("测试包含关系检测...")
    
    # 创建模拟数据
    from geometry_utils import BoundingBox
    
    # 外层矩形
    outer = DxfEntity(
        handle='1',
        entity_type='POLYLINE',
        layer='0',
        coordinates=[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)],
        closed=True,
        bbox=BoundingBox(0, 0, 100, 100),
        area=10000
    )
    
    # 内层小矩形
    inner1 = DxfEntity(
        handle='2',
        entity_type='POLYLINE',
        layer='0',
        coordinates=[(20, 20), (40, 20), (40, 40), (20, 40), (20, 20)],
        closed=True,
        bbox=BoundingBox(20, 20, 40, 40),
        area=400
    )
    
    inner2 = DxfEntity(
        handle='3',
        entity_type='POLYLINE',
        layer='0',
        coordinates=[(60, 60), (80, 60), (80, 80), (60, 80), (60, 60)],
        closed=True,
        bbox=BoundingBox(60, 60, 80, 80),
        area=400
    )
    
    # 独立矩形（不在任何图形内部）
    independent = DxfEntity(
        handle='4',
        entity_type='POLYLINE',
        layer='0',
        coordinates=[(200, 200), (300, 200), (300, 300), (200, 300), (200, 200)],
        closed=True,
        bbox=BoundingBox(200, 200, 300, 300),
        area=10000
    )
    
    detector = ContainmentDetector()
    units = detector.detect([outer, inner1, inner2, independent])
    
    print(f"检测到 {len(units)} 个单元:")
    for i, unit in enumerate(units):
        print(f"  单元 {i+1}:")
        print(f"    外层: {unit.outer.handle} (面积: {unit.total_area:.1f})")
        print(f"    内部: {[e.handle for e in unit.inner]}")
