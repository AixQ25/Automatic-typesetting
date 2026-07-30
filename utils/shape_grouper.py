"""
形状分组器
根据位置将图形与厚度标注关联，按厚度分组

核心规则：
    每个图形按其中心点找最近的厚度标注，归入该标注对应厚度的分组。
    每件独立判定（不做整批多数票合并），同批同厚度自然成立 ——
    凡同尺寸、同图层、又落到同一标注范围下的零件会被同一个标注命中，从而统一厚度；
    而同尺寸但落到其它标注范围下的零件会落到各自的厚度。这样既不会把本应分开的
    不同厚度零件错并入一个组，也不会把同一标注下的同形零件拆散。
"""

import sys
import os
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.text_parser import ThicknessLabel, SkipLabel


@dataclass
class ShapeGroup:
    """形状分组"""
    thickness: float           # 厚度值
    shapes: List[dict]         # 图形列表 [{'handle': h, 'bbox': bbox, 'entity': e}, ...]
    label_x: float             # 标注X坐标
    label_y: float             # 标注Y坐标


class ShapeGrouper:
    """形状分组器"""
    
    def __init__(self, y_tolerance: float = 500.0, x_search_range: float = 2000.0):
        """
        初始化分组器
        
        Args:
            y_tolerance: Y坐标容差（同一行的判断标准）
            x_search_range: X搜索范围（搜索标注的距离）
        """
        self.y_tolerance = y_tolerance
        self.x_search_range = x_search_range
    
    def group_shapes(self, shapes: List[dict], 
                     thickness_labels: List[ThicknessLabel],
                     skip_labels: List[SkipLabel] = None) -> Dict[float, ShapeGroup]:
        """
        将图形按厚度分组（每件按就近最近标注独立归属）
        
        Args:
            shapes: 图形列表，每个图形包含 'handle', 'bbox', 'entity', 'unit' 等
            thickness_labels: 厚度标注列表
            skip_labels: 跳过标注列表
            
        Returns:
            Dict[float, ShapeGroup]: 按厚度值分组的图形
        """
        if not shapes or not thickness_labels:
            return {}
        
        # 计算跳过区域
        skip_regions = self._get_skip_regions(skip_labels or [])
        
        # 过滤掉在跳过区域内的图形
        filtered_shapes = [s for s in shapes
                           if not self._is_in_skip_region(s, skip_regions)]
        
        # 每件按就近最近标注直接归属
        groups: Dict[float, ShapeGroup] = {}
        for shape in filtered_shapes:
            bbox = shape.get('bbox')
            if not bbox:
                continue
            shape_x = (bbox.x_min + bbox.x_max) / 2
            shape_y = (bbox.y_min + bbox.y_max) / 2
            best_label = self._find_nearest_label(shape_x, shape_y, thickness_labels)
            if best_label is None:
                continue
            th = best_label.value
            if th not in groups:
                groups[th] = ShapeGroup(
                    thickness=th,
                    shapes=[],
                    label_x=best_label.x,
                    label_y=best_label.y,
                )
            groups[th].shapes.append(shape)
        
        return groups
    
    def _find_nearest_label(self, shape_x: float, shape_y: float,
                           labels: List[ThicknessLabel]) -> Optional[ThicknessLabel]:
        """
        找到最近的厚度标注
        
        规则:
        1. X距离不能太远 (|label_x - shape_x| < x_search_range)
        2. Y坐标相近 (|label_y - shape_y| < y_tolerance)
        3. 选择距离最近的
        """
        best_label = None
        best_distance = float('inf')
        
        for label in labels:
            # X距离不能太远
            x_distance = abs(label.x - shape_x)
            if x_distance > self.x_search_range:
                continue
            
            # Y坐标必须相近
            y_distance = abs(label.y - shape_y)
            if y_distance > self.y_tolerance:
                continue
            
            # 计算综合距离
            distance = (x_distance ** 2 + y_distance ** 2) ** 0.5
            
            if distance < best_distance:
                best_distance = distance
                best_label = label
        
        return best_label
    
    def _get_skip_regions(self, skip_labels: List[SkipLabel]) -> List[Tuple[float, float, float, float]]:
        """获取跳过区域"""
        regions = []
        for label in skip_labels:
            # 简单处理：以标注为中心的矩形区域
            # 实际可能需要更复杂的逻辑
            regions.append((
                label.x - 100,  # x_min
                label.y - 50,   # y_min
                label.x + 100,  # x_max
                label.y + 50    # y_max
            ))
        return regions
    
    def _is_in_skip_region(self, shape: dict, 
                          skip_regions: List[Tuple[float, float, float, float]]) -> bool:
        """检查图形是否在跳过区域内"""
        bbox = shape.get('bbox')
        if not bbox:
            return False
        
        shape_x = (bbox.x_min + bbox.x_max) / 2
        shape_y = (bbox.y_min + bbox.y_max) / 2
        
        for x_min, y_min, x_max, y_max in skip_regions:
            if x_min <= shape_x <= x_max and y_min <= shape_y <= y_max:
                return True
        
        return False


# 测试
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 模拟数据
    thickness_labels = [
        ThicknessLabel(value=1.0, x=100, y=500, text="1.0"),
        ThicknessLabel(value=1.5, x=100, y=400, text="1.5"),
        ThicknessLabel(value=1.0, x=500, y=500, text="1.0"),
    ]
    
    skip_labels = [
        SkipLabel(x=800, y=300, text="暂不")
    ]
    
    # 模拟图形
    shapes = [
        {'handle': '1', 'bbox': type('BBox', (), {'x_min': 200, 'x_max': 300, 'y_min': 480, 'y_max': 520})()},
        {'handle': '2', 'bbox': type('BBox', (), {'x_min': 200, 'x_max': 300, 'y_min': 380, 'y_max': 420})()},
        {'handle': '3', 'bbox': type('BBox', (), {'x_min': 600, 'x_max': 700, 'y_min': 480, 'y_max': 520})()},
        {'handle': '4', 'bbox': type('BBox', (), {'x_min': 700, 'x_max': 800, 'y_min': 280, 'y_max': 320})()},  # 在跳过区域内
    ]
    
    grouper = ShapeGrouper()
    groups = grouper.group_shapes(shapes, thickness_labels, skip_labels)
    
    print("分组结果:")
    for thickness, group in sorted(groups.items()):
        print(f"  {thickness}mm: {len(group.shapes)} 个图形")
        for shape in group.shapes:
            print(f"    - {shape['handle']}")
