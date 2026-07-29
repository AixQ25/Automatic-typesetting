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
    
    @property
    def all_entities(self) -> List[DxfEntity]:
        """获取所有实体（外层+内部）"""
        return [self.outer] + self.inner


class ContainmentDetector:
    """包含关系检测器"""
    
    def __init__(self, min_area: float = 10.0):
        """
        初始化检测器
        
        Args:
            min_area: 最小面积阈值（小于此面积的图形忽略）
        """
        self.min_area = min_area
    
    def detect(self, entities: List[DxfEntity]) -> List[ShapeUnit]:
        """
        检测包含关系，将图形分组为单元
        
        Args:
            entities: 实体列表
            
        Returns:
            List[ShapeUnit]: 形状单元列表
        """
        # 过滤有效实体
        valid_entities = [e for e in entities 
                         if e.bbox and e.area >= self.min_area and e.closed]
        
        if not valid_entities:
            return []
        
        # 创建 shapely Polygon
        polygon_data = []
        for entity in valid_entities:
            try:
                poly = Polygon(entity.coordinates)
                if not poly.is_valid:
                    poly = make_valid(poly)
                polygon_data.append({
                    'entity': entity,
                    'polygon': poly,
                    'area': poly.area,
                    'centroid': poly.centroid
                })
            except Exception as e:
                continue
        
        # 按面积降序排序
        polygon_data.sort(key=lambda x: x['area'], reverse=True)
        
        # 检测包含关系，建立父子关系
        parent_map = {}  # handle -> parent_handle
        children_map = {}  # handle -> [child_handles]
        
        for i, data_i in enumerate(polygon_data):
            handle_i = data_i['entity'].handle
            poly_i = data_i['polygon']
            
            # 查找包含当前图形的父图形
            parent = None
            min_parent_area = float('inf')
            
            for j, data_j in enumerate(polygon_data):
                if i == j:
                    continue
                
                handle_j = data_j['entity'].handle
                poly_j = data_j['polygon']
                area_j = data_j['area']
                
                # 父图形必须面积更大
                if area_j <= data_i['area']:
                    continue
                
                # 检测质心是否在父图形内部
                centroid_i = data_i['centroid']
                if poly_j.contains(centroid_i):
                    # 选择面积最小的包含者（最近的父级）
                    if area_j < min_parent_area:
                        min_parent_area = area_j
                        parent = handle_j
            
            if parent:
                parent_map[handle_i] = parent
                if parent not in children_map:
                    children_map[parent] = []
                children_map[parent].append(handle_i)
        
        # 构建形状单元
        entity_map = {e.handle: e for e in valid_entities}
        units = []
        used_handles = set()
        
        # 找到所有顶级图形（没有父图形的）
        top_level = [data for data in polygon_data 
                     if data['entity'].handle not in parent_map]
        
        for data in top_level:
            handle = data['entity'].handle
            entity = data['entity']
            
            # 收集所有子孙实体
            inner_entities = []
            self._collect_descendants(handle, children_map, entity_map, 
                                     inner_entities, used_handles)
            
            unit = ShapeUnit(
                outer=entity,
                inner=inner_entities,
                total_area=data['area'],
                handle=handle
            )
            units.append(unit)
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
