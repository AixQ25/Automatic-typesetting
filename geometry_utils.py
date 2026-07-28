"""
几何工具函数
用于计算图形的几何属性
"""

import math
from typing import List, Tuple
from dataclasses import dataclass
from shapely.geometry import Polygon, MultiPolygon
from shapely.affinity import rotate, translate


@dataclass
class BoundingBox:
    """边界框"""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    
    @property
    def width(self) -> float:
        return self.x_max - self.x_min
    
    @property
    def height(self) -> float:
        return self.y_max - self.y_min
    
    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)


def calculate_bounding_box(coordinates: List[Tuple[float, float]]) -> BoundingBox:
    """
    计算坐标的边界框
    
    Args:
        coordinates: 坐标列表 [(x1,y1), (x2,y2), ...]
        
    Returns:
        BoundingBox: 边界框
    """
    if not coordinates:
        return BoundingBox(0, 0, 0, 0)
    
    x_coords = [p[0] for p in coordinates]
    y_coords = [p[1] for p in coordinates]
    
    return BoundingBox(
        x_min=min(x_coords),
        y_min=min(y_coords),
        x_max=max(x_coords),
        y_max=max(y_coords)
    )


def calculate_area(coordinates: List[Tuple[float, float]]) -> float:
    """
    计算多边形面积 (Shoelace公式)
    
    Args:
        coordinates: 坐标列表
        
    Returns:
        float: 面积
    """
    if len(coordinates) < 3:
        return 0.0
    
    area = 0.0
    n = len(coordinates)
    
    for i in range(n):
        j = (i + 1) % n
        area += coordinates[i][0] * coordinates[j][1]
        area -= coordinates[j][0] * coordinates[i][1]
    
    return abs(area) / 2.0


def calculate_mbr(coordinates: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    计算最小外接矩形 (Minimum Bounding Rectangle)
    考虑旋转0°, 90°, 180°, 270°
    
    Args:
        coordinates: 坐标列表
        
    Returns:
        Tuple[float, float]: (宽度, 高度)
    """
    if not coordinates:
        return (0, 0)
    
    # 尝试不同旋转角度
    min_area = float('inf')
    best_width, best_height = 0, 0
    
    for angle in [0, 90, 180, 270]:
        # 旋转坐标
        rotated = rotate_coordinates(coordinates, angle)
        
        # 计算边界框
        bbox = calculate_bounding_box(rotated)
        area = bbox.width * bbox.height
        
        if area < min_area:
            min_area = area
            best_width = bbox.width
            best_height = bbox.height
    
    return (best_width, best_height)


def rotate_coordinates(coordinates: List[Tuple[float, float]], 
                      angle_degrees: float,
                      center: Tuple[float, float] = None) -> List[Tuple[float, float]]:
    """
    旋转坐标
    
    Args:
        coordinates: 坐标列表
        angle_degrees: 旋转角度（度）
        center: 旋转中心，默认为坐标中心
        
    Returns:
        List[Tuple[float, float]]: 旋转后的坐标
    """
    if not coordinates:
        return []
    
    # 计算旋转中心
    if center is None:
        bbox = calculate_bounding_box(coordinates)
        center = bbox.center
    
    # 转换为弧度
    angle_rad = math.radians(angle_degrees)
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)
    
    rotated = []
    for x, y in coordinates:
        # 平移到原点
        dx = x - center[0]
        dy = y - center[1]
        
        # 旋转
        new_x = dx * cos_angle - dy * sin_angle
        new_y = dx * sin_angle + dy * cos_angle
        
        # 平移回原位置
        rotated.append((new_x + center[0], new_y + center[1]))
    
    return rotated


def translate_coordinates(coordinates: List[Tuple[float, float]],
                         offset_x: float,
                         offset_y: float) -> List[Tuple[float, float]]:
    """
    平移坐标
    
    Args:
        coordinates: 坐标列表
        offset_x: X偏移量
        offset_y: Y偏移量
        
    Returns:
        List[Tuple[float, float]]: 平移后的坐标
    """
    return [(x + offset_x, y + offset_y) for x, y in coordinates]


def create_shapely_polygon(coordinates: List[Tuple[float, float]]) -> Polygon:
    """
    创建Shapely多边形对象
    
    Args:
        coordinates: 坐标列表
        
    Returns:
        Polygon: Shapely多边形
    """
    if len(coordinates) < 3:
        raise ValueError("至少需要3个点才能创建多边形")
    
    # 确保多边形闭合
    if coordinates[0] != coordinates[-1]:
        coordinates = coordinates + [coordinates[0]]
    
    return Polygon(coordinates)


def add_spacing_to_polygon(polygon: Polygon, spacing: float) -> Polygon:
    """
    为多边形添加间距（buffer）
    
    Args:
        polygon: Shapely多边形
        spacing: 间距（总间距，会除以2得到半间距）
        
    Returns:
        Polygon: 添加间距后的多边形
    """
    return polygon.buffer(spacing / 2)


def check_collision(polygon1: Polygon, polygon2: Polygon) -> bool:
    """
    检查两个多边形是否碰撞
    
    Args:
        polygon1, polygon2: Shapely多边形
        
    Returns:
        bool: 是否碰撞
    """
    return polygon1.intersects(polygon2)


def calculate_utilization(shapes: List[dict], board_width: float, board_height: float) -> float:
    """
    计算板材利用率
    
    Args:
        shapes: 排版后的图形列表 [{'width': w, 'height': h, 'x': x, 'y': y}, ...]
        board_width: 板材宽度
        board_height: 板材高度
        
    Returns:
        float: 利用率 (0.0 ~ 1.0)
    """
    if not shapes:
        return 0.0
    
    total_area = sum(s['width'] * s['height'] for s in shapes)
    board_area = board_width * board_height
    
    return total_area / board_area if board_area > 0 else 0.0


# 测试函数
def test_geometry_utils():
    """测试几何工具函数"""
    print("测试几何工具函数...")
    
    # 测试坐标
    coords = [(0, 0), (10, 0), (10, 5), (0, 5)]
    
    # 测试边界框
    bbox = calculate_bounding_box(coords)
    print(f"边界框: {bbox}")
    print(f"宽度: {bbox.width}, 高度: {bbox.height}")
    
    # 测试面积
    area = calculate_area(coords)
    print(f"面积: {area}")
    
    # 测试MBR
    width, height = calculate_mbr(coords)
    print(f"MBR: {width} x {height}")
    
    # 测试旋转
    rotated = rotate_coordinates(coords, 90)
    print(f"旋转90°: {rotated}")
    
    # 测试Shapely多边形
    poly = create_shapely_polygon(coords)
    print(f"Shapely面积: {poly.area}")
    
    print("测试完成!")


if __name__ == "__main__":
    test_geometry_utils()
