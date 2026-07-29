"""
矩形排样算法
使用Best Fit Decreasing算法进行矩形排样
"""

from typing import List, Tuple
from dataclasses import dataclass
import heapq


@dataclass
class Rect:
    """矩形"""
    width: float
    height: float
    id: int = 0  # 图形ID
    handle: str = ''  # DXF实体句柄
    layer: str = ''   # 图层名
    
    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class Placement:
    """放置位置"""
    rect: Rect
    x: float
    y: float
    rotated: bool = False  # 是否旋转90°
    
    @property
    def actual_width(self) -> float:
        return self.rect.height if self.rotated else self.rect.width
    
    @property
    def actual_height(self) -> float:
        return self.rect.width if self.rotated else self.rect.height


class RectNesting:
    """矩形排样器"""
    
    def __init__(self, board_width: float, board_height: float, spacing: float = 10.0):
        """
        初始化排样器
        
        Args:
            board_width: 板材宽度
            board_height: 板材高度
            spacing: 图形间距
        """
        self.board_width = board_width
        self.board_height = board_height
        self.spacing = spacing
        
        # 可用位置列表 (x, y)
        self.available_positions = [(0.0, 0.0)]
        
        # 已放置的矩形
        self.placements: List[Placement] = []
        
        # 当前行信息
        self.current_row_height = 0.0
        self.current_row_x = 0.0
    
    def reset(self):
        """重置排样器"""
        self.available_positions = [(0.0, 0.0)]
        self.placements = []
        self.current_row_height = 0.0
        self.current_row_x = 0.0
    
    def nest(self, rects: List[Rect]) -> List[Placement]:
        """
        执行排样
        
        Args:
            rects: 矩形列表
            
        Returns:
            List[Placement]: 放置位置列表
        """
        self.reset()
        
        # 按面积降序排序
        sorted_rects = sorted(rects, key=lambda r: r.area, reverse=True)
        
        # 为每个矩形分配ID
        for i, rect in enumerate(sorted_rects):
            rect.id = i
        
        # 逐个放置矩形
        for rect in sorted_rects:
            placement = self._place_rect(rect)
            if placement:
                self.placements.append(placement)
            else:
                print(f"警告: 矩形 {rect.id} ({rect.width}x{rect.height}) 无法放置")
        
        return self.placements
    
    def _place_rect(self, rect: Rect) -> Placement:
        """
        放置单个矩形
        
        Args:
            rect: 要放置的矩形
            
        Returns:
            Placement: 放置位置，如果无法放置则返回None
        """
        # 尝试不旋转
        placement = self._try_place(rect, rotated=False)
        if placement:
            return placement
        
        # 尝试旋转90°
        placement = self._try_place(rect, rotated=True)
        if placement:
            return placement
        
        return None
    
    def _try_place(self, rect: Rect, rotated: bool) -> Placement:
        """
        尝试放置矩形
        
        Args:
            rect: 矩形
            rotated: 是否旋转
            
        Returns:
            Placement: 放置位置
        """
        # 实际尺寸
        actual_width = rect.height if rotated else rect.width
        actual_height = rect.width if rotated else rect.height
        
        # 添加间距
        total_width = actual_width + self.spacing
        total_height = actual_height + self.spacing
        
        # 遍历所有可用位置
        for x, y in self.available_positions[:]:
            # 检查是否超出板材边界
            if x + total_width > self.board_width:
                continue
            if y + total_height > self.board_height:
                continue
            
            # 检查是否与已放置的矩形碰撞
            if not self._check_collision(x, y, total_width, total_height):
                # 放置成功
                placement = Placement(
                    rect=rect,
                    x=x,
                    y=y,
                    rotated=rotated
                )
                
                # 更新可用位置
                self._update_available_positions(x, y, total_width, total_height)
                
                return placement
        
        return None
    
    def _check_collision(self, x: float, y: float, width: float, height: float) -> bool:
        """
        检查碰撞
        
        Args:
            x, y: 位置
            width, height: 尺寸（包含间距）
            
        Returns:
            bool: 是否碰撞
        """
        for placement in self.placements:
            px = placement.x
            py = placement.y
            pw = placement.actual_width + self.spacing
            ph = placement.actual_height + self.spacing
            
            # 矩形碰撞检测
            if (x < px + pw and x + width > px and
                y < py + ph and y + height > py):
                return True
        
        return False
    
    def _update_available_positions(self, x: float, y: float, width: float, height: float):
        """
        更新可用位置
        
        Args:
            x, y: 放置位置
            width, height: 尺寸（包含间距）
        """
        # 移除被占用的位置
        self.available_positions = [
            (px, py) for px, py in self.available_positions
            if not (x <= px < x + width and y <= py < y + height)
        ]
        
        # 添加新的可用位置（右边和上边）
        new_positions = [
            (x + width, y),  # 右边
            (x, y + height),  # 上边
        ]
        
        for pos in new_positions:
            if pos not in self.available_positions:
                # 检查是否在板材范围内
                if pos[0] < self.board_width and pos[1] < self.board_height:
                    self.available_positions.append(pos)
        
        # 按y坐标排序，然后按x坐标排序
        self.available_positions.sort(key=lambda p: (p[1], p[0]))
    
    def get_utilization(self) -> float:
        """
        计算板材利用率
        
        Returns:
            float: 利用率 (0.0 ~ 1.0)
        """
        if not self.placements:
            return 0.0
        
        total_area = sum(p.rect.area for p in self.placements)
        board_area = self.board_width * self.board_height
        
        return total_area / board_area if board_area > 0 else 0.0
    
    def print_result(self):
        """打印排样结果"""
        print("\n" + "=" * 50)
        print("排样结果")
        print("=" * 50)
        print(f"板材尺寸: {self.board_width} x {self.board_height}")
        print(f"间距: {self.spacing}")
        print(f"放置矩形数: {len(self.placements)}")
        print(f"利用率: {self.get_utilization():.1%}")
        print("\n放置详情:")
        for p in self.placements:
            rotation = " (旋转90°)" if p.rotated else ""
            print(f"  矩形{p.rect.id}: ({p.x:.1f}, {p.y:.1f}) "
                  f"尺寸: {p.rect.width}x{p.rect.height}{rotation}")


def create_rects_from_sizes(sizes: List[Tuple[float, float]]) -> List[Rect]:
    """
    从尺寸列表创建矩形列表
    
    Args:
        sizes: 尺寸列表 [(width1, height1), (width2, height2), ...]
        
    Returns:
        List[Rect]: 矩形列表
    """
    return [Rect(width=w, height=h) for w, h in sizes]


# 测试函数
def test_rect_nesting():
    """测试矩形排样"""
    print("测试矩形排样算法...")
    
    # 板材尺寸
    board_width = 400
    board_height = 850
    spacing = 10
    
    # 创建测试矩形
    sizes = [
        (100, 50),
        (80, 60),
        (120, 40),
        (90, 70),
        (60, 80),
        (110, 55),
        (75, 65),
        (95, 45),
    ]
    
    rects = create_rects_from_sizes(sizes)
    
    # 创建排样器
    nestor = RectNesting(board_width, board_height, spacing)
    
    # 执行排样
    placements = nestor.nest(rects)
    
    # 打印结果
    nestor.print_result()
    
    return nestor


if __name__ == "__main__":
    test_rect_nesting()
