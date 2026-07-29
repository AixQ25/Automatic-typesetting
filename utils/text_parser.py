"""
DXF文字解析器
从DXF文件中提取厚度标注和分组信息
"""

import re
import sys
import os
from typing import List, Tuple, Dict, Optional
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
    
    # 厚度值的正则匹配模式
    THICKNESS_PATTERN = re.compile(r'^(\d+\.?\d*)$')
    
    # 跳过关键词
    SKIP_KEYWORDS = ['暂不', '跳过', '不做']
    
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
        解析所有文字标注（包括 INSERT 块内的 TEXT）
        
        Returns:
            Dict[float, List[ThicknessLabel]]: 按厚度值分组的标注
        """
        self.thickness_labels = []
        self.skip_labels = []
        
        msp = self.doc.modelspace()
        self._parse_entities(msp)
        self._parse_entities_in_blocks()
        
        # 按厚度值分组
        thickness_groups = {}
        for label in self.thickness_labels:
            if label.value not in thickness_groups:
                thickness_groups[label.value] = []
            thickness_groups[label.value].append(label)
        
        return thickness_groups
    
    def _parse_entities(self, entities):
        """解析实体集合中的 TEXT/MTEXT"""
        for entity in entities:
            dxftype = entity.dxftype()
            
            if dxftype == 'TEXT':
                self._parse_text(entity)
            elif dxftype == 'MTEXT':
                self._parse_mtext(entity)
            elif dxftype == 'INSERT':
                self._parse_insert_text(entity)
    
    def _parse_entities_in_blocks(self):
        """解析自定义块中的 TEXT 实体"""
        for block in self.doc.blocks:
            if block.name.startswith('*'):
                continue
            for entity in block:
                if entity.dxftype() == 'TEXT':
                    self._parse_text(entity)
                elif entity.dxftype() == 'MTEXT':
                    self._parse_mtext(entity)
    
    def _parse_insert_text(self, entity):
        """解析 INSERT 实体中块的 TEXT"""
        try:
            block_name = entity.dxf.name
            block = self.doc.blocks.get(block_name)
            if block:
                insert_x = entity.dxf.insert.x
                insert_y = entity.dxf.insert.y
                for block_entity in block:
                    if block_entity.dxftype() == 'TEXT':
                        self._parse_text(block_entity, offset_x=insert_x, offset_y=insert_y)
                    elif block_entity.dxftype() == 'MTEXT':
                        self._parse_mtext(block_entity, offset_x=insert_x, offset_y=insert_y)
        except Exception:
            pass
    
    def _parse_text(self, entity, offset_x=0.0, offset_y=0.0):
        """解析TEXT实体"""
        try:
            text = entity.dxf.text.strip()
            x = entity.dxf.insert.x + offset_x
            y = entity.dxf.insert.y + offset_y
            
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
                
        except Exception as e:
            pass
    
    def _parse_mtext(self, entity, offset_x=0.0, offset_y=0.0):
        """解析MTEXT实体"""
        try:
            text = entity.text.strip()
            x = entity.dxf.insert.x + offset_x
            y = entity.dxf.insert.y + offset_y
            
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
                
        except Exception as e:
            pass
    
    def _extract_thickness(self, text: str) -> Optional[float]:
        """
        从文字中提取厚度值
        
        支持格式:
        - "1.0"
        - "1.5"
        - "2.0"
        - "厚度1.0" (提取数字部分)
        """
        text = text.strip()
        
        # 直接匹配数字
        match = self.THICKNESS_PATTERN.match(text)
        if match:
            try:
                value = float(match.group(1))
                # 过滤合理范围 (0.1 ~ 10.0)
                if 0.1 <= value <= 10.0:
                    return value
            except ValueError:
                pass
        
        # 尝试从文本中提取数字
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            try:
                value = float(match.group(1))
                if 0.1 <= value <= 10.0:
                    return value
            except ValueError:
                pass
        
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
        ("厚度1.0", 1.0),
        ("1.5mm", 1.5),
        ("暂不", None),
        ("跳过", None),
    ]
    
    print("厚度提取测试:")
    for text, expected in test_cases:
        result = parser._extract_thickness(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' -> {result} (期望: {expected})")
    
    print("\n跳过标注测试:")
    for text in ["暂不", "跳过", "不做", "正常文字"]:
        result = parser._is_skip_text(text)
        print(f"  '{text}' -> {result}")
