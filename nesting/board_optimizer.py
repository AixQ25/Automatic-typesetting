"""
多板材装箱算法
自动计算最优板材组合，将图形分配到多张板材上
"""

import sys
import os
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nesting.rect_nesting import Rect, RectNesting, Placement


@dataclass
class Board:
    """板材"""
    width: float
    height: float
    name: str = ""
    placements: List[Placement] = field(default_factory=list)
    utilization: float = 0.0


@dataclass
class NestingResult:
    """排版结果"""
    thickness: float
    boards: List[Board]
    total_shapes: int
    placed_shapes: int
    total_utilization: float


# 可用板材规格
BOARD_SPECS = [
    (600, 850, "600x850"),
    (400, 850, "400x850"),
]


def find_optimal_boards(rects: List[Rect], spacing: float = 10.0, 
                       margin: float = 10.0) -> NestingResult:
    """
    自动计算最优板材组合
    
    Args:
        rects: 矩形列表
        spacing: 间距
        margin: 边缘留白
        
    Returns:
        NestingResult: 排版结果
    """
    if not rects:
        return NestingResult(thickness=0, boards=[], total_shapes=0,
                           placed_shapes=0, total_utilization=0)
    
    # 尝试不同板材组合，找最优方案
    best_result = None
    best_score = float('inf')
    
    # 策略1: 只用600x850
    result1 = _try_single_board_type(rects, 600, 850, "600x850", spacing, margin)
    if result1 and result1.placed_shapes == len(rects):
        score = len(result1.boards) * 1000 + _total_waste(result1)
        if score < best_score:
            best_score = score
            best_result = result1
    
    # 策略2: 只用400x850
    result2 = _try_single_board_type(rects, 400, 850, "400x850", spacing, margin)
    if result2 and result2.placed_shapes == len(rects):
        score = len(result2.boards) * 1000 + _total_waste(result2)
        if score < best_score:
            best_score = score
            best_result = result2
    
    # 策略3: 混合使用（先用600x850排大块，剩余用400x850）
    result3 = _try_mixed_boards(rects, spacing, margin)
    if result3 and result3.placed_shapes == len(rects):
        score = len(result3.boards) * 1000 + _total_waste(result3)
        if score < best_score:
            best_score = score
            best_result = result3
    
    # 如果都排不下，用能排最多的方案
    if best_result is None:
        best_result = result1 or result2 or result3
        if best_result is None:
            best_result = NestingResult(thickness=0, boards=[], 
                                       total_shapes=len(rects),
                                       placed_shapes=0, total_utilization=0)
    
    return best_result


def _try_single_board_type(rects: List[Rect], width: float, height: float,
                           name: str, spacing: float, margin: float = 10.0) -> Optional[NestingResult]:
    """尝试只用一种板材"""
    boards = []
    remaining = list(rects)
    board_index = 0
    
    while remaining:
        nestor = RectNesting(width, height, spacing, margin)
        placements = nestor.nest(remaining)
        
        if not placements:
            break
        
        # 获取成功放置的矩形
        placed_handles = {p.rect.handle for p in placements if p.rect.handle}
        board = Board(
            width=width,
            height=height,
            name=f"{name}#{board_index + 1}",
            placements=placements,
            utilization=nestor.get_utilization()
        )
        boards.append(board)
        
        # 移除已放置的
        remaining = [r for r in remaining if r.handle not in placed_handles]
        board_index += 1
    
    total_placed = sum(len(b.placements) for b in boards)
    total_area = sum(b.width * b.height for b in boards)
    used_area = sum(p.rect.area for b in boards for p in b.placements)
    
    return NestingResult(
        thickness=0,
        boards=boards,
        total_shapes=len(rects),
        placed_shapes=total_placed,
        total_utilization=used_area / total_area if total_area > 0 else 0
    )


def _try_mixed_boards(rects: List[Rect], spacing: float, margin: float = 10.0) -> Optional[NestingResult]:
    """混合使用两种板材"""
    # 按面积降序排序
    sorted_rects = sorted(rects, key=lambda r: r.area, reverse=True)
    
    boards = []
    remaining = list(sorted_rects)
    board_index = 0
    
    # 先尝试用600x850排大的
    while remaining:
        # 尝试600x850
        nestor_large = RectNesting(600, 850, spacing, margin)
        placements_large = nestor_large.nest(remaining)
        
        # 尝试400x850
        nestor_small = RectNesting(400, 850, spacing, margin)
        placements_small = nestor_small.nest(remaining)
        
        # 选择利用率更高的
        if placements_large and (not placements_small or 
            nestor_large.get_utilization() >= nestor_small.get_utilization()):
            placements = placements_large
            width, height, name = 600, 850, "600x850"
            utilization = nestor_large.get_utilization()
        elif placements_small:
            placements = placements_small
            width, height, name = 400, 850, "400x850"
            utilization = nestor_small.get_utilization()
        else:
            break
        
        if not placements:
            break
        
        placed_handles = {p.rect.handle for p in placements if p.rect.handle}
        board = Board(
            width=width,
            height=height,
            name=f"{name}#{board_index + 1}",
            placements=placements,
            utilization=utilization
        )
        boards.append(board)
        
        remaining = [r for r in remaining if r.handle not in placed_handles]
        board_index += 1
    
    total_placed = sum(len(b.placements) for b in boards)
    total_area = sum(b.width * b.height for b in boards)
    used_area = sum(p.rect.area for b in boards for p in b.placements)
    
    return NestingResult(
        thickness=0,
        boards=boards,
        total_shapes=len(rects),
        placed_shapes=total_placed,
        total_utilization=used_area / total_area if total_area > 0 else 0
    )


def _total_waste(result: NestingResult) -> float:
    """计算总浪费面积"""
    total_area = sum(b.width * b.height for b in result.boards)
    used_area = sum(p.rect.area for b in result.boards for p in b.placements)
    return total_area - used_area


# 测试
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 创建测试矩形
    rects = [
        Rect(100, 50, id=0, handle='1'),
        Rect(80, 60, id=1, handle='2'),
        Rect(120, 40, id=2, handle='3'),
        Rect(90, 70, id=3, handle='4'),
        Rect(60, 80, id=4, handle='5'),
        Rect(110, 55, id=5, handle='6'),
        Rect(75, 65, id=6, handle='7'),
        Rect(95, 45, id=7, handle='8'),
        Rect(130, 35, id=8, handle='9'),
        Rect(85, 55, id=9, handle='10'),
    ]
    
    print("=" * 50)
    print("多板材装箱测试")
    print("=" * 50)
    
    result = find_optimal_boards(rects, spacing=10)
    
    print(f"\n总计: {result.total_shapes} 个图形")
    print(f"已放置: {result.placed_shapes} 个")
    print(f"板材数量: {len(result.boards)}")
    print(f"总利用率: {result.total_utilization:.1%}")
    
    for i, board in enumerate(result.boards):
        print(f"\n板材 {i+1}: {board.name}")
        print(f"  尺寸: {board.width} x {board.height}")
        print(f"  图形数: {len(board.placements)}")
        print(f"  利用率: {board.utilization:.1%}")
