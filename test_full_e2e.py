"""
完整端到端测试：DXF读取 → 厚度分组 → 多板材排版 → DXF写入
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from utils.dxf_parser import DxfParser
from utils.dxf_writer import DxfWriter
from utils.text_parser import TextParser
from utils.shape_grouper import ShapeGrouper
from nesting.rect_nesting import Rect, RectNesting
from nesting.board_optimizer import find_optimal_boards

print("=" * 60)
print("完整端到端测试")
print("=" * 60)

# 1. 读取DXF
print("\n1. 读取 test.dxf ...")
parser = DxfParser('test.dxf')
parser.load()
entities = parser.parse()
shapes = [s for s in entities if s.bbox and s.bbox.width > 0]
print(f"   有效图形: {len(shapes)} 个")

# 2. 解析文字标注
print("\n2. 解析文字标注...")
text_parser = TextParser(parser.doc)
thickness_groups_labels = text_parser.parse()
print(f"   厚度标注: {len(thickness_groups_labels)} 种")

for thickness, labels in sorted(thickness_groups_labels.items()):
    print(f"     {thickness}mm: {len(labels)} 个标注")

# 3. 按厚度分组
print("\n3. 按厚度分组...")
grouper = ShapeGrouper()
shape_groups = grouper.group_shapes(
    [{'handle': s.handle, 'bbox': s.bbox, 'entity': s} for s in shapes],
    list(thickness_groups_labels.values())[0] if thickness_groups_labels else [],
    text_parser.skip_labels
)

# 如果没有厚度标注，将所有图形作为一组
if not shape_groups:
    print("   未找到厚度标注，将所有图形作为一组")
    from utils.shape_grouper import ShapeGroup
    shape_groups = {0.0: ShapeGroup(
        thickness=0.0,
        shapes=[{'handle': s.handle, 'bbox': s.bbox} for s in shapes],
        label_x=0,
        label_y=0
    )}

for thickness, group in sorted(shape_groups.items()):
    print(f"   {thickness}mm: {len(group.shapes)} 个图形")

# 4. 为每组计算最优板材
print("\n4. 计算最优板材...")
results = {}

for thickness, group in sorted(shape_groups.items()):
    rects = []
    for i, shape_info in enumerate(group.shapes):
        bbox = shape_info['bbox']
        rects.append(Rect(
            width=bbox.width,
            height=bbox.height,
            id=i,
            handle=shape_info.get('handle', ''),
        ))
    
    result = find_optimal_boards(rects, spacing=10)
    results[thickness] = result
    
    print(f"\n   {thickness}mm 组:")
    print(f"     图形数: {len(rects)}")
    print(f"     板材数: {len(result.boards)}")
    for board in result.boards:
        print(f"       - {board.name}: {len(board.placements)} 个, 利用率 {board.utilization:.1%}")

# 5. 写入DXF
print("\n5. 导出 DXF...")
writer = DxfWriter('test.dxf')
success = writer.write_multi_group_results(results, 'test_output_multi.dxf', gap=20)

if success:
    print("   导出成功！")
else:
    print("   导出失败！")

print("\n" + "=" * 60)
print("测试完成！")
print("请在AutoCAD中打开 test_output_multi.dxf 查看结果")
print("=" * 60)
