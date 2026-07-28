"""
AutoCAD COM接口封装
用于连接AutoCAD并操作图形
"""

import sys
from typing import List, Tuple, Optional
from dataclasses import dataclass
from pyautocad import Autocad, APoint


@dataclass
class AcadEntity:
    """AutoCAD实体"""
    entity_type: str  # LINE, ARC, CIRCLE, LWPOLYLINE等
    handle: str       # 实体句柄
    layer: str        # 所在图层
    coordinates: List[Tuple[float, float]]  # 顶点坐标


class AutoCADBridge:
    """AutoCAD连接桥接类"""
    
    def __init__(self):
        self.acad = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        连接已运行的AutoCAD
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.acad = Autocad()
            self.connected = True
            print(f"已连接到AutoCAD: {self.acad.doc.Name}")
            return True
        except Exception as e:
            print(f"连接AutoCAD失败: {e}")
            self.connected = False
            return False
    
    def get_selected_entities(self) -> List[AcadEntity]:
        """
        获取用户选中的实体
        
        Returns:
            List[AcadEntity]: 选中的实体列表
        """
        if not self.connected:
            print("未连接到AutoCAD")
            return []
        
        entities = []
        
        try:
            # 提示用户选择
            self.acad.prompt("请在AutoCAD中选择要排版的图形，然后按回车...\n")
            
            # 获取选择集
            selection = self.acad.doc.SelectionSets.Add("temp")
            
            # 尝试获取当前选择
            try:
                selection.Select(0)  # 0 = acSelectionSetAll
            except:
                # 如果没有选择，让用户手动选择
                try:
                    selection.Select(5)  # 5 = acSelectionSetUserSelect
                except:
                    print("未选择任何实体")
                    return []
            
            # 遍历选中的实体
            for entity in selection:
                acad_entity = self._extract_entity(entity)
                if acad_entity:
                    entities.append(acad_entity)
            
            # 删除选择集
            selection.Delete()
            
        except Exception as e:
            print(f"获取选中实体失败: {e}")
        
        return entities
    
    def _extract_entity(self, entity) -> Optional[AcadEntity]:
        """
        提取实体的几何信息
        
        Args:
            entity: AutoCAD实体对象
            
        Returns:
            AcadEntity: 提取的实体信息
        """
        try:
            entity_type = entity.ObjectName
            handle = entity.Handle
            layer = entity.Layer
            
            coordinates = []
            
            if entity_type == "AcDbLine":
                # 直线: 起点和终点
                start = entity.StartPoint
                end = entity.EndPoint
                coordinates = [(start[0], start[1]), (end[0], end[1])]
            
            elif entity_type == "AcDbPolyline":
                # 多段线: 获取所有顶点
                coords = entity.Coordinates
                for i in range(0, len(coords), 2):
                    coordinates.append((coords[i], coords[i+1]))
            
            elif entity_type == "AcDbCircle":
                # 圆: 圆心和半径
                center = entity.Center
                radius = entity.Radius
                # 用多边形近似圆
                import math
                points = 36
                for i in range(points):
                    angle = 2 * math.pi * i / points
                    x = center[0] + radius * math.cos(angle)
                    y = center[1] + radius * math.sin(angle)
                    coordinates.append((x, y))
                coordinates.append(coordinates[0])  # 闭合
            
            elif entity_type == "AcDbArc":
                # 圆弧: 起点、端点、圆心
                center = entity.Center
                radius = entity.Radius
                start_angle = entity.StartAngle
                end_angle = entity.EndAngle
                
                import math
                # 生成弧线上的点
                points = 20
                for i in range(points + 1):
                    angle = start_angle + (end_angle - start_angle) * i / points
                    x = center[0] + radius * math.cos(angle)
                    y = center[1] + radius * math.sin(angle)
                    coordinates.append((x, y))
            
            else:
                # 其他类型暂不支持
                print(f"不支持的实体类型: {entity_type}")
                return None
            
            return AcadEntity(
                entity_type=entity_type,
                handle=handle,
                layer=layer,
                coordinates=coordinates
            )
            
        except Exception as e:
            print(f"提取实体失败: {e}")
            return None
    
    def create_layer(self, layer_name: str, color_index: int = 1) -> bool:
        """
        创建新图层
        
        Args:
            layer_name: 图层名称
            color_index: 颜色索引 (1=红色, 2=黄色, 3=绿色, etc.)
            
        Returns:
            bool: 是否创建成功
        """
        if not self.connected:
            return False
        
        try:
            layers = self.acad.doc.Layers
            try:
                # 尝试获取已存在的图层
                layer = layers.Item(layer_name)
                print(f"图层 '{layer_name}' 已存在")
            except:
                # 创建新图层
                layer = layers.Add(layer_name)
                layer.Color = color_index
                print(f"已创建图层: {layer_name}")
            
            return True
        except Exception as e:
            print(f"创建图层失败: {e}")
            return False
    
    def copy_entity_to_layer(self, entity_handle: str, target_layer: str, 
                             offset_x: float = 0, offset_y: float = 0) -> bool:
        """
        复制实体到指定图层
        
        Args:
            entity_handle: 实体句柄
            target_layer: 目标图层
            offset_x: X偏移量
            offset_y: Y偏移量
            
        Returns:
            bool: 是否复制成功
        """
        if not self.connected:
            return False
        
        try:
            # 通过句柄获取实体
            entity = self.acad.doc.HandleToObject(entity_handle)
            
            # 复制实体
            new_entity = entity.Copy()
            
            # 移动到新位置
            if offset_x != 0 or offset_y != 0:
                new_entity.Move(APoint(0, 0), APoint(offset_x, offset_y))
            
            # 设置图层
            new_entity.Layer = target_layer
            
            return True
        except Exception as e:
            print(f"复制实体失败: {e}")
            return False
    
    def draw_rectangle(self, x: float, y: float, width: float, height: float,
                       layer: str = "0") -> bool:
        """
        绘制矩形
        
        Args:
            x, y: 左下角坐标
            width, height: 宽度和高度
            layer: 图层名称
            
        Returns:
            bool: 是否绘制成功
        """
        if not self.connected:
            return False
        
        try:
            # AutoCAD 需要扁平坐标列表 [x1,y1, x2,y2, ...]
            coords = []
            points = [
                (x, y),
                (x + width, y),
                (x + width, y + height),
                (x, y + height),
                (x, y)  # 闭合
            ]
            
            for px, py in points:
                coords.extend([px, py])
            
            # 创建轻量级多段线
            poly = self.acad.model.AddLightWeightPolyline(coords)
            poly.Layer = layer
            poly.Closed = True
            
            return True
        except Exception as e:
            print(f"绘制矩形失败: {e}")
            return False


# 测试函数
def test_connection():
    """测试AutoCAD连接"""
    bridge = AutoCADBridge()
    
    print("正在连接AutoCAD...")
    if bridge.connect():
        print("连接成功!")
        print(f"当前文档: {bridge.acad.doc.Name}")
        return bridge
    else:
        print("连接失败，请确保AutoCAD已运行")
        return None


if __name__ == "__main__":
    test_connection()
