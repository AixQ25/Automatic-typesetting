"""
自动排版 回归诊断脚本（无 GUI）

用法:
    python tools/diagnose.py <file.dxf>
    python tools/diagnose.py            # 默认对 test_pro(1).dxf 运行

输出:
    - 容器/参考框剥离数
    - 有效图形单元数、小圆保留数（防丢件核验）
    - 解析出的厚度组与跳过标注
    - 按厚度分组后各组单元数
    - 每组自动排版后的板材数、放置数、未放置数、利用率
    - 汇总：总板材数、总放置数/有效单元数

退出码:
    0  全部单元均成功放置
    1  存在未放置单元（含超大无法装入）
    2  解析失败
"""

import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# 让脚本能在项目根目录或 tools/ 下运行
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402
from utils.dxf_parser import DxfParser  # noqa: E402
from utils.text_parser import TextParser  # noqa: E402
from utils.shape_grouper import ShapeGrouper, ShapeGroup  # noqa: E402
from utils.containment_detector import ContainmentDetector  # noqa: E402
from nesting.rect_nesting import Rect  # noqa: E402
from nesting.board_optimizer import find_optimal_boards  # noqa: E402


def run(filepath: str, spacing: float = None) -> int:
    if spacing is None:
        spacing = config.NESTING_SPACING

    print("=" * 60)
    print(f"诊断文件: {os.path.basename(filepath)}")
    print(f"板材：统一 600x850 | 边距 10mm | 间距 {spacing}mm | 列优先(纵向优先)")
    print("=" * 60)

    parser = DxfParser(filepath)
    if not parser.load():
        print("[错误] 无法加载 DXF 文件")
        return 2
    entities = parser.parse()
    shapes = [s for s in entities if s.bbox and s.bbox.width > 0]
    print(f"解析实体: {len(entities)}  有效图形(bbox.width>0): {len(shapes)}")

    # 容器剥离 + 整体识别
    units = ContainmentDetector().detect(shapes)
    containers = [u for u in units if u.oversized]
    valid = [u for u in units if not u.oversized]
    print(f"容器/参考框剥离(略过): {len(containers)}")
    for u in sorted(containers, key=lambda x: x.outer.bbox.width * x.outer.bbox.height, reverse=True)[:5]:
        print(f"    - {u.handle}: {u.outer.bbox.width:.0f}x{u.outer.bbox.height:.0f}mm")
    if len(containers) > 5:
        print(f"    ... 还有 {len(containers) - 5} 个")
    print(f"有效图形单元: {len(valid)}")

    # 小圆保留核验（防丢件）
    in_circles = sum(1 for s in shapes if s.entity_type == 'CIRCLE')
    kept_circles = sum(1 for u in valid for e in [u.outer] + u.inner
                       if e.entity_type == 'CIRCLE')
    print(f"小圆核验: 输入 CIRCLE 实体 {in_circles} 个, 单元内保留 {kept_circles} 个"
          f" ({'OK' if kept_circles >= in_circles else '丢失 ' + str(in_circles - kept_circles)})")

    # 厚度解析
    tp = TextParser(parser.doc)
    tgroups = tp.parse()
    print(f"厚度标注: {len(tgroups)} 种 -> "
          + ", ".join(f"{k}:{len(v)}" for k, v in sorted(tgroups.items())))
    print(f"跳过标注: {[s.text for s in tp.skip_labels]}")

    # 按厚度分组
    grouper = ShapeGrouper(y_tolerance=1000, x_search_range=5000)
    all_labels = [l for ls in tgroups.values() for l in ls]
    
    if not all_labels:
        print("  未检测到厚度标注，启用按行分组策略...")
        sg = grouper.fallback_row_grouping(
            [{'handle': u.handle, 'bbox': u.outer.bbox,
              'layer': u.outer.layer, 'unit': u} for u in valid],
            row_y_tolerance=80.0
        )
    else:
        sg = grouper.group_shapes(
            [{'handle': u.handle, 'bbox': u.outer.bbox,
              'layer': u.outer.layer, 'unit': u} for u in valid],
            all_labels, tp.skip_labels)
        grouped = {h for grp in sg.values() for h in [s['handle'] for s in grp.shapes]}
        ungrouped = [u for u in valid if u.handle not in grouped]
        if ungrouped:
            print(f"  未分组单元: {len(ungrouped)} 个，按行分组处理")
            row_sg = grouper.fallback_row_grouping(
                [{'handle': u.handle, 'bbox': u.outer.bbox, 'unit': u} for u in ungrouped],
                row_y_tolerance=80.0
            )
            sg.update(row_sg)
    
    print(f"分组结果: " + ", ".join(
        f"{ShapeGrouper.get_row_display_name(k)}:{len(v.shapes)}"
        for k, v in sorted(sg.items())
    ))

    # 排版
    print("-" * 60)
    print("排版")
    print("-" * 60)
    total_boards = 0
    total_placed = 0
    total_unplaced = 0
    for th, grp in sorted(sg.items()):
        rects = [Rect(width=si['bbox'].width, height=si['bbox'].height, id=i,
                      handle=si.get('handle', ''))
                 for i, si in enumerate(grp.shapes)]
        res = find_optimal_boards(rects, spacing=spacing)
        total_boards += len(res.boards)
        total_placed += res.placed_shapes
        unplaced = len(grp.shapes) - res.placed_shapes
        total_unplaced += unplaced
        utils = [round(b.utilization * 100) for b in res.boards]
        th_display = ShapeGrouper.get_row_display_name(th)
        print(f"  {th_display}: 单元 {len(grp.shapes)} | 板材 {len(res.boards)} | "
              f"放置 {res.placed_shapes} | 未放置 {unplaced} | 利用率 {utils}")

    print("-" * 60)
    print(f"汇总: 总板材 {total_boards} | 总放置 {total_placed}/{len(valid)} | "
          f"未放置 {total_unplaced}")
    if total_unplaced == 0 and total_placed == len(valid):
        print("结论: 所有有效单元均已排入，无丢件。")
        return 0
    else:
        print("结论: 存在未放置单元（多为超大无法装入 600x850）。")
        return 1


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    spacing = config.NESTING_SPACING
    for a in sys.argv[1:]:
        if a.startswith('--spacing='):
            spacing = float(a.split('=', 1)[1])
    filepath = args[0] if args else os.path.join(_ROOT, 'test_pro(1).dxf')
    if not os.path.exists(filepath):
        # 兼容相对项目根的路径
        alt = os.path.join(_ROOT, filepath)
        if os.path.exists(alt):
            filepath = alt
    if not os.path.exists(filepath):
        print(f"[错误] 文件不存在: {filepath}")
        return 2
    return run(filepath, spacing=spacing)


if __name__ == '__main__':
    sys.exit(main())