"""
DXF文字解析器
从DXF文件中提取厚度标注和分组信息
"""

import re
import sys
import os
import math
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ThicknessLabel:
    """厚度标注"""
    value: float           # 厚度值 (1.0, 1.5, etc.)
    x: float               # X坐标
    y: float               # Y坐标
    text: str              # 原始文字


@dataclass
class SkipLabel:
    """跳过标注"""
    x: float
    y: float
    text: str


class TextParser:
    """DXF文字解析器"""
    
    # 纯单数字厚度标注：1.0 / 1.5 / 2.0 / 0.5 / 3.0 / 4.5 ...
    SINGLE_NUM_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*$')
    
    # 长*宽*厚 或 长 x 宽 x 厚（分隔符 * / x / X / ，等），末位为厚度
    # 例：600*850*1.0 / 400x850x1.5 / 600X850X2.0
    DIM_THICKNESS_PATTERN = re.compile(
        r'^\s*\d+(?:\.\d+)?\s*[\*xX,，]\s*\d+(?:\.\d+)?\s*[\*xX,，]\s*(\d+(?:\.\d+)?)\s*$'
    )
    
    # 多数字空格分隔串（图形内的尺寸规格，如 "4.5  5  6  7  8"）→ 忽略，不当厚度
    MULTI_NUM_PATTERN = re.compile(r'^\s*\d+(?:\.\d+)?(\s+\d+(?:\.\d+)?)+\s*$')
    
    # 跳过关键词（no 也视作“暂不/不做”）
    SKIP_KEYWORDS = ['暂不', '跳过', '不做', 'no', 'No', 'NO']
    
    def __init__(self, doc):
        """
        初始化解析器
        
        Args:
            doc: ezdxf文档对象
        """
        self.doc = doc
        self.thickness_labels: List[ThicknessLabel] = []
        self.skip_labels: List[SkipLabel] = []
    
    def parse(self) -> Dict[float, List[ThicknessLabel]]:
        """
        解析文字标注
        
        解析范围：
        - 模型空间内的 TEXT/MTEXT（使用其世界坐标）
        - 被 INSERT 引用的块内的 TEXT/MTEXT（递归应用 INSERT 变换得到世界坐标）
        
        注意：不再遍历所有块定义 —— 未被 INSERT 引用的块（例如模板/废块）
        内的文字会被忽略，避免引入坐标错误的伪厚度标注。
        
        Returns:
            Dict[float, List[ThicknessLabel]]: 按厚度值分组的标注
        """
        self.thickness_labels = []
        self.skip_labels = []
        
        msp = self.doc.modelspace()
        self._parse_entities(msp)
        
        # 按厚度值分组
        thickness_groups = {}
        for label in self.thickness_labels:
            if label.value not in thickness_groups:
                thickness_groups[label.value] = []
            thickness_groups[label.value].append(label)
        
        return thickness_groups
    
    def _parse_entities(self, entities, transform: Optional[Callable] = None):
        """解析实体集合中的 TEXT/MTEXT/INSERT（INSERT 递归并应用变换）"""
        for entity in entities:
            dxftype = entity.dxftype()
            
            if dxftype == 'TEXT':
                self._parse_text(entity, transform=transform)
            elif dxftype == 'MTEXT':
                self._parse_mtext(entity, transform=transform)
            elif dxftype == 'INSERT':
                self._parse_insert_text(entity, transform=transform)
    
    def _parse_insert_text(self, entity, transform: Optional[Callable] = None):
        """递归解析 INSERT 引用块内的 TEXT/MTEXT，应用 INSERT 变换得到世界坐标"""
        try:
            block_name = entity.dxf.name
            block = self.doc.blocks.get(block_name)
            if not block:
                return
            
            insert = entity.dxf.insert
            ix, iy = insert.x, insert.y
            xs = getattr(entity.dxf, 'xscale', 1.0) or 1.0
            ys = getattr(entity.dxf, 'yscale', 1.0) or 1.0
            rot = math.radians(getattr(entity.dxf, 'rotation', 0.0) or 0.0)
            cos_r = math.cos(rot)
            sin_r = math.sin(rot)
            
            def this_tf(x, y):
                sx = x * xs
                sy = y * ys
                rx = sx * cos_r - sy * sin_r
                ry = sx * sin_r + sy * cos_r
                wx = rx + ix
                wy = ry + iy
                return transform(wx, wy) if transform else (wx, wy)
            
            for block_entity in block:
                dt = block_entity.dxftype()
                if dt == 'TEXT':
                    self._parse_text(block_entity, transform=this_tf)
                elif dt == 'MTEXT':
                    self._parse_mtext(block_entity, transform=this_tf)
                elif dt == 'INSERT':
                    self._parse_insert_text(block_entity, transform=this_tf)
        except Exception:
            pass
    
    def _parse_text(self, entity, offset_x=0.0, offset_y=0.0,
                    transform: Optional[Callable] = None):
        """解析TEXT实体"""
        try:
            text = entity.dxf.text.strip()
            x = entity.dxf.insert.x
            y = entity.dxf.insert.y
            if transform:
                x, y = transform(x, y)
            else:
                x += offset_x
                y += offset_y
            
            thickness = self._extract_thickness(text)
            if thickness is not None:
                self.thickness_labels.append(ThicknessLabel(
                    value=thickness,
                    x=x,
                    y=y,
                    text=text
                ))
                return
            
            if self._is_skip_text(text):
                self.skip_labels.append(SkipLabel(
                    x=x,
                    y=y,
                    text=text
                ))
        except Exception:
            pass
    
    def _parse_mtext(self, entity, offset_x=0.0, offset_y=0.0,
                     transform: Optional[Callable] = None):
        """解析MTEXT实体"""
        try:
            text = entity.text.strip()
            x = entity.dxf.insert.x
            y = entity.dxf.insert.y
            if transform:
                x, y = transform(x, y)
            else:
                x += offset_x
                y += offset_y
            
            thickness = self._extract_thickness(text)
            if thickness is not None:
                self.thickness_labels.append(ThicknessLabel(
                    value=thickness,
                    x=x,
                    y=y,
                    text=text
                ))
                return
            
            if self._is_skip_text(text):
                self.skip_labels.append(SkipLabel(
                    x=x,
                    y=y,
                    text=text
                ))
        except Exception:
            pass
    
    def _extract_thickness(self, text: str) -> Optional[float]:
        """
        从文字中提取厚度值
        
        支持格式:
        - 纯单数字："1.0" / "1.5" / "2.0" / "0.5" / "3.0" / "4.5"
        - 长*宽*厚 / 长 x 宽 x 厚："600*850*1.0" / "400x850x1.5"
          （末位为厚度，前两位为板材尺寸，忽略）
        
        忽略（返回 None，不当厚度也不当跳过）：
        - 多数字空格分隔串：如 "4.5  5  6  7  8"（图形内尺寸规格）
        - 其它非厚度文字
        """
        text = text.strip()
        if not text:
            return None
        
        # 1) 多数字空格分隔串 → 忽略（图形尺寸规格）
        if self.MULTI_NUM_PATTERN.match(text):
            return None
        
        # 2) 长*宽*厚 / 长 x 宽 x 厚 → 取末位
        m = self.DIM_THICKNESS_PATTERN.match(text)
        if m:
            try:
                value = float(m.group(1))
                if 0.1 <= value <= 10.0:
                    return value
            except ValueError:
                pass
            return None
        
        # 3) 纯单数字 → 厚度
        m = self.SINGLE_NUM_PATTERN.match(text)
        if m:
            try:
                value = float(m.group(1))
                if 0.1 <= value <= 10.0:
                    return value
            except ValueError:
                pass
            return None
        
        # 4) 其它文字：不做兜底抓数字（避免把无关数字误当厚度）
        return None
    
    def _is_skip_text(self, text: str) -> bool:
        """检查是否是跳过标注"""
        text = text.strip()
        return any(keyword in text for keyword in self.SKIP_KEYWORDS)
    
    def get_skip_regions(self) -> List[Tuple[float, float, float, float]]:
        """
        获取需要跳过的区域
        
        Returns:
            List[(x, y, width, height)]: 跳过区域列表
        """
        regions = []
        for label in self.skip_labels:
            # 假设跳过区域是以标注为中心的矩形
            # 宽度和高度需要根据实际情况调整
            regions.append((label.x - 50, label.y - 20, 100, 40))
        return regions


# 测试
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import ezdxf
    
    # 测试厚度提取
    parser = TextParser(None)
    
    test_cases = [
        ("1.0", 1.0),
        ("1.5", 1.5),
        ("2.0", 2.0),
        ("3.0", 3.0),
        ("4.0", 4.0),
        ("4.5", 4.5),
        ("0.5", 0.5),
        ("400*850*0.5", 0.5),
        ("600*850*1.0", 1.0),
        ("400x850x1.5", 1.5),
        ("600X850X2.0", 2.0),
        ("4.5  5  6  7  8", None),   # 图形内尺寸规格 → 忽略
        ("4.0 2正 短钉", None),       # 部件标签 → 忽略
        ("暂不", None),
        ("跳过", None),
        ("厚度1.0", None),            # 非纯数字/规格串 → 忽略
        ("1.5mm", None),
    ]
    
    print("厚度提取测试:")
    for text, expected in test_cases:
        result = parser._extract_thickness(text)
        status = "OK" if result == expected else "FAIL"
        print(f"  [{status}] '{text}' -> {result} (期望: {expected})")
    
    print("\n跳过标注测试:")
    for text in ["暂不", "跳过", "不做", "no", "No", "NO", "正常文字", "1.0"]:
        result = parser._is_skip_text(text)
        print(f"  '{text}' -> {result}")
