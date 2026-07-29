"""
模拟 GUI 工作流程的完整测试
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf
from utils.dxf_parser import DxfParser
from utils.containment_detector import ContainmentDetector
from utils.text_parser import TextParser
from utils.shape_grouper import ShapeGrouper, ShapeGroup
from nesting.rect_nesting import Rect
from nesting.board_optimizer import find_optimal_boards

print("=" * 60)
print("模拟 GUI 工作流程测试")
print("=" * 60)

# 1. 加载文件
print("\n1. 加载 test_pro.dxf ...")
parser = DxfParser('test_pro.dxf')
parser.load()
entities = parser.parse()
shapes = [s for s in entities if s.bbox and s.bbox.width > 0]
print(f"   总实体: {len(entities)}")
print(f"   有效图形: {len(shapes)}")

# 2. 检测包含关系
print("\n2. 检测包含关系...")
detector = ContainmentDetector()
units = detector.detect(shapes)
print(f"   检测到 {len(units)} 个图形单元")

# 3. 过滤超大单元
max_board_width = 600 - 20
max_board_height = 850 - 20

valid_units = []
skipped_units = []
for unit in units:
    w = unit.outer.bbox.width
    h = unit.outer.bbox.height
    if w > max_board_width or h > max_board_height:
        skipped_units.append(unit)
    else:
        valid_units.append(unit)

if skipped_units:
    print(f"   跳过 {len(skipped_units)} 个超大单元")
print(f"   有效单元: {len(valid_units)} 个")

# 4. 解析文字标注
print("\n3. 解析文字标注...")
text_parser = TextParser(parser.doc)
thickness_groups_labels = text_parser.parse()
print(f"   厚度标注: {len(thickness_groups_labels)} 种")

# 5. 按厚度分组
print("\n4. 按厚度分组...")
grouper = ShapeGrouper(y_tolerance=1000, x_search_range=5000)
shape_groups = grouper.group_shapes(
    [{'handle': unit.handle, 'bbox': unit.outer.bbox, 'unit': unit} 
     for unit in valid_units],
    [label for labels in thickness_groups_labels.values() for label in labels],
    text_parser.skip_labels
)

# 找出未分组的单元
grouped_handles = set()
for group in shape_groups.values():
    for shape in group.shapes:
        grouped_handles.add(shape['handle'])

ungrouped_units = [u for u in valid_units if u.handle not in grouped_handles]

if ungrouped_units:
    print(f"   未分组单元: {len(ungrouped_units)} 个，归入默认组")
    # 将未分组的单元添加到默认组
    if 0.0 not in shape_groups:
        shape_groups[0.0] = ShapeGroup(
            thickness=0.0,
            shapes=[],
            label_x=0,
            label_y=0
        )
    for unit in ungrouped_units:
        shape_groups[0.0].shapes.append({
            'handle': unit.handle,
            'bbox': unit.outer.bbox,
            'unit': unit
        })

print(f"\n5. 分组结果:")
total = 0
for thickness, group in sorted(shape_groups.items()):
    print(f"   {thickness}mm: {len(group.shapes)} 个单元")
    total += len(group.shapes)
print(f"   总计: {total}/{len(valid_units)} 个单元")

# 6. 为每组计算最优板材
print("\n6. 计算最优板材...")
spacing = 10
results = {}

for thickness, group in sorted(shape_groups.items()):
    print(f"\n   处理 {thickness}mm 组 ({len(group.shapes)} 个单元)")
    
    # 创建矩形列表
    rects = []
    for i, shape_info in enumerate(group.shapes):
        bbox = shape_info['bbox']
        rects.append(Rect(
            width=bbox.width,
            height=bbox.height,
            id=i,
            handle=shape_info.get('handle', ''),
        ))
    
    # 自动计算最优板材
    result = find_optimal_boards(rects, spacing=spacing)
    results[thickness] = result
    
    print(f"     板材方案: {len(result.boards)} 张")
    print(f"     已放置: {result.placed_shapes}/{result.total_shapes}")
    for board in result.boards[:3]:
        print(f"       - {board.name}: {len(board.placements)} 个单元, "
              f"利用率 {board.utilization:.1%}")
    if len(result.boards) > 3:
        print(f"       ... 还有 {len(result.boards)-3} 张板材")

# 汇总
print("\n" + "=" * 60)
print("测试完成！")
total_boards = sum(len(r.boards) for r in results.values())
total_shapes = sum(r.placed_shapes for r in results.values())
print(f"总板材数: {total_boards}")
print(f"已放置单元: {total_shapes}/{len(valid_units)}")
print("=" * 60)
