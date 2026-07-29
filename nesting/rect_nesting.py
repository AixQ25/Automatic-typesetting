"""
矩形排样算法
使用改进的底部优先(Bottom-Left)算法
"""

from typing import List, Tuple
from dataclasses import dataclass


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
    """矩形排样器 - 使用改进的底部优先算法"""
    
    def __init__(self, board_width: float, board_height: float, 
                 spacing: float = 10.0, margin: float = 10.0):
        """
        初始化排样器
        
        Args:
            board_width: 板材宽度
            board_height: 板材高度
            spacing: 图形间距
            margin: 边缘留白
        """
        self.board_width = board_width
        self.board_height = board_height
        self.spacing = spacing
        self.margin = margin
        
        # 可用空间边界框
        self.min_x = margin
        self.min_y = margin
        self.max_x = board_width - margin
        self.max_y = board_height - margin
        
        # 已放置的矩形
        self.placements: List[Placement] = []
    
    def reset(self):
        """重置排样器"""
        self.placements = []
    
    def nest(self, rects: List[Rect]) -> List[Placement]:
        """
        执行排样 - 底部优先算法
        
        Args:
            rects: 矩形列表
            
        Returns:
            List[Placement]: 放置位置列表
        """
        self.reset()
        
        if not rects:
            return []
        
        # 按面积降序排序（大图形优先）
        sorted_rects = sorted(rects, key=lambda r: r.area, reverse=True)
        
        # 为每个矩形分配ID
        for i, rect in enumerate(sorted_rects):
            rect.id = i
        
        # 逐个放置矩形
        for rect in sorted_rects:
            placement = self._place_rect(rect)
            if placement:
                self.placements.append(placement)
        
        return self.placements
    
    def _place_rect(self, rect: Rect) -> Placement:
        """
        放置单个矩形 - 尝试不旋转和旋转两种方式
        
        Args:
            rect: 要放置的矩形
            
        Returns:
            Placement: 放置位置，如果无法放置则返回None
        """
        # 尝试不旋转
        placement = self._find_best_position(rect, rotated=False)
        if placement:
            return placement
        
        # 尝试旋转90°
        placement = self._find_best_position(rect, rotated=True)
        if placement:
            return placement
        
        return None
    
    def _find_best_position(self, rect: Rect, rotated: bool) -> Placement:
        """
        查找最佳放置位置 - 改进的底部优先策略（含下滑优化）
        
        Args:
            rect: 矩形
            rotated: 是否旋转
            
        Returns:
            Placement: 放置位置
        """
        actual_width = rect.height if rotated else rect.width
        actual_height = rect.width if rotated else rect.height
        
        total_width = actual_width + self.spacing
        total_height = actual_height + self.spacing
        
        if total_width > self.max_x - self.min_x:
            return None
        if total_height > self.max_y - self.min_y:
            return None
        
        candidates = self._generate_candidates(total_width, total_height)
        candidates.sort(key=lambda p: (p[1], p[0]))
        
        for x, y in candidates:
            if self._can_place(x, y, total_width, total_height):
                # 下滑优化：尽可能向左滑动，再向下滑动
                final_x, final_y = self._slide_to_bottom_left(x, y, total_width, total_height)
                return Placement(
                    rect=rect,
                    x=final_x,
                    y=final_y,
                    rotated=rotated
                )
        
        return None
    
    def _slide_to_bottom_left(self, x: float, y: float, width: float, height: float) -> Tuple[float, float]:
        """下滑优化：将矩形尽可能向左、然后向下滑动"""
        # 向左滑动
        step = 1.0
        while x - step >= self.min_x:
            if not self._can_place(x - step, y, width, height):
                break
            x -= step
        
        # 向下滑动
        while y - step >= self.min_y:
            if not self._can_place(x, y - step, width, height):
                break
            y -= step
        
        return x, y
    
    def _generate_candidates(self, width: float, height: float) -> List[Tuple[float, float]]:
        """
        生成候选放置位置
        
        Args:
            width: 图形宽度（含间距）
            height: 图形高度（含间距）
            
        Returns:
            List[Tuple[float, float]]: 候选位置列表
        """
        candidates = []
        
        # 起始位置（左下角）
        candidates.append((self.min_x, self.min_y))
        
        # 已放置图形的边缘位置
        for p in self.placements:
            px = p.x
            py = p.y
            pw = p.actual_width + self.spacing
            ph = p.actual_height + self.spacing
            
            # 右边
            right_x = px + pw
            if right_x + width <= self.max_x:
                candidates.append((right_x, py))
            
            # 上边
            top_y = py + ph
            if top_y + height <= self.max_y:
                candidates.append((px, top_y))
            
            # 右上角
            if right_x + width <= self.max_x and top_y + height <= self.max_y:
                candidates.append((right_x, top_y))
            
            # 左边（贴合左边已放置图形）
            left_x = px - width
            if left_x >= self.min_x:
                candidates.append((left_x, py))
                candidates.append((left_x, top_y))
        
        # 去重并排序
        candidates = list(set(candidates))
        
        return candidates
    
    def _can_place(self, x: float, y: float, width: float, height: float) -> bool:
        """
        检查是否可以放置
        
        Args:
            x, y: 位置
            width, height: 尺寸（含间距）
            
        Returns:
            bool: 是否可以放置
        """
        # 检查边界
        if x + width > self.max_x:
            return False
        if y + height > self.max_y:
            return False
        if x < self.min_x:
            return False
        if y < self.min_y:
            return False
        
        # 检查碰撞
        for p in self.placements:
            px = p.x
            py = p.y
            pw = p.actual_width + self.spacing
            ph = p.actual_height + self.spacing
            
            # 矩形碰撞检测
            if (x < px + pw and x + width > px and
                y < py + ph and y + height > py):
                return False
        
        return True
    
    def get_utilization(self) -> float:
        """
        计算板材利用率
        
        Returns:
            float: 利用率 (0.0 ~ 1.0)
        """
        if not self.placements:
            return 0.0
        
        total_area = sum(p.rect.area for p in self.placements)
        board_area = (self.max_x - self.min_x) * (self.max_y - self.min_y)
        
        return total_area / board_area if board_area > 0 else 0.0


# 测试
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 创建测试矩形
    rects = [
        Rect(100, 50, id=0, handle='1'),
        Rect(80, 60, id=1, handle='2'),
        Rect(120, 40, id=2, handle='3'),
        Rect(90, 70, id=3, handle='4'),
        Rect(60, 80, id=4, handle='5'),
    ]
    
    nestor = RectNesting(400, 850, 10, 10)
    placements = nestor.nest(rects)
    
    print(f"放置数量: {len(placements)}")
    print(f"利用率: {nestor.get_utilization():.1%}")
    
    for p in placements:
        print(f"  {p.rect.handle}: ({p.x:.1f}, {p.y:.1f}) {p.actual_width:.1f}x{p.actual_height:.1f}")
