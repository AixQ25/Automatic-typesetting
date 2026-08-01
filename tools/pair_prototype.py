# -*- coding: utf-8 -*-
"""
配对嵌合 (pair-first) 离线原型
================================
验证思路：把能互补的复杂件（左右脚/高脚杯/新月形）旋转180° 嵌合成
“超单元”，再用当前 bbox BLF 排样，对比：
  1) 板数 / 利用率
  2) 真实轮廓重叠数（当前排法是否真的会重叠/混乱）
  3) 配对收益与阈值建议

用法:
    python tools/pair_prototype.py [file.dxf] [--spacing=10]
        --spacing   件间距 (默认 10)
        --boards   板材宽高 如 600x850 (默认 600x850)
        --no-pair  只跑当前 bbox 基线（不配对）
        --pair-only只跑配对版（跳过基线）
        --dump     输出首块板布局文本
        --pair-win 配对收益阈值，低于此(如10%)不成对 (默认 8%)
        --quick    快速模式（配对网格粗一点）

输出:
    - 当前 bbox 排法: 板数/利用率/重叠数
    - 配对后排法    : 板数/利用率/重叠数/配对成功数
    - 建议
"""
import sys
import os
import math
import time

sys.stdout.reconfigure(encoding='utf-8')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import ezdxf
from shapely.geometry import Polygon
from shapely.affinity import translate, rotate
from shapely import prepared

from utils.dxf_parser import DxfParser
from utils.containment_detector import ContainmentDetector


# ---------------------------------------------------------------------------
# 1. 读取 + 聚类成单元（复用现有解析/包含检测，与 LISP 聚类意图一致）
# ---------------------------------------------------------------------------
def load_units(dxf_path):
    parser = DxfParser(dxf_path)
    if not parser.load():
        raise SystemExit(f"[错误] 无法加载 DXF: {dxf_path}")
    entities = parser.parse()
    shapes = [s for s in entities if s.bbox and s.bbox.width > 0 and s.bbox.height > 0]
    units = ContainmentDetector().detect(shapes)
    return [u for u in units if not u.oversized]


def unit_polygon(unit):
    """用外层坐标构造 shapely 多边形"""
    coords = unit.outer.coordinates
    if len(coords) < 3:
        return None
    # 去重首尾重复点
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return None
    try:
        return Polygon(coords)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2. 当前 bbox BLF 排样（复刻 LISP: nest-pack / nest-pack-board / nest-find-pos
#    / nest-can-place / nest-slide / nest-place-best）
# ---------------------------------------------------------------------------
def pack_bbox(items, bw, bh, sp, mg):
    """items: list of (w,h,obj)。返回 boards: list of [(x,y,rot,w,h,obj)]"""
    items = sorted(items, key=lambda it: it[0] * it[1], reverse=True)
    boards = []
    remaining = items[:]
    safe = 0
    while remaining and safe < 500:
        safe += 1
        placed, nrem = _pack_board(remaining, bw, bh, sp, mg)
        if not placed:
            # 这轮一个都放不下（理论上不出现，防死循环）
            break
        boards.append(placed)
        remaining = nrem
    return boards


def _pack_board(items, bw, bh, sp, mg):
    out, nrem = [], []
    for w, h, obj in items:
        best = _place_best(w, h, mg, mg, bw - mg, bh - mg, sp, out)
        if best:
            pos, rot = best
            out.append((pos[0], pos[1], rot, w if not rot else h,
                        h if not rot else w, obj))
        else:
            nrem.append((w, h, obj))
    return out, nrem


def _place_best(w, h, minx, miny, maxx, maxy, sp, placed):
    p0 = _find_pos(w, h, minx, miny, maxx, maxy, sp, placed)
    p90 = _find_pos(h, w, minx, miny, maxx, maxy, sp, placed)
    if p0 and p90:
        # 复刻 LISP: 更下优先；同 y 更左优先；同位时更窄优先
        if p90[1] < p0[1] - 1e-4:
            return p90, True
        if abs(p90[1] - p0[1]) < 1e-4 and p90[0] < p0[0]:
            return p90, True
        if (abs(p90[1] - p0[1]) < 1e-4 and abs(p90[0] - p0[0]) < 1e-4
                and h < w):
            return p90, True
        return p0, False
    if p0:
        return p0, False
    if p90:
        return p90, True
    return None


def _find_pos(w, h, minx, miny, maxx, maxy, sp, placed):
    cands = [(minx, miny)]
    for pp in placed:
        px, py, _rot, pw, ph, _o = pp[0], pp[1], pp[2], pp[3], pp[4], pp[5]
        pw += sp
        ph += sp
        top = py + ph
        right = px + pw
        if top + h <= maxy:
            cands.append((px, top))
        if right + w <= maxx:
            cands.append((right, py))
        if right + w <= maxx and top + h <= maxy:
            cands.append((right, top))
        if px - w >= minx:
            cands.append((px - w, py))
            if top + h <= maxy:
                cands.append((px - w, top))
    cands = list(set(cands))
    cands.sort(key=lambda c: (c[1], c[0]))
    for x, y in cands:
        if _can_place(x, y, w, h, minx, miny, maxx, maxy, sp, placed):
            return _slide(x, y, w, h, minx, miny, maxx, maxy, sp, placed)
    return None


def _can_place(x, y, w, h, minx, miny, maxx, maxy, sp, placed):
    if x < minx or y < miny or x + w > maxx or y + h > maxy:
        return False
    for px, py, _r, pw, ph, _o in placed:
        if (x < px + pw + sp and x + w + sp > px
                and y < py + ph + sp and y + h + sp > py):
            return False
    return True


def _slide(x, y, w, h, minx, miny, maxx, maxy, sp, placed):
    step = 1.0
    while y - step >= miny and _can_place(x, y - step, w, h,
                                          minx, miny, maxx, maxy, sp, placed):
        y -= step
    while x - step >= minx and _can_place(x - step, y, w, h,
                                          minx, miny, maxx, maxy, sp, placed):
        x -= step
    while y - step >= miny and _can_place(x, y - step, w, h,
                                          minx, miny, maxx, maxy, sp, placed):
        y -= step
    return x, y


# ---------------------------------------------------------------------------
# 3. 配对嵌合
# ---------------------------------------------------------------------------
def _pair_nest(poly_a, poly_b, sp, quick=False):
    """
    固定 A，尝试 B（自身 / 旋转180°）沿 X/Y 滑动，找最小组合 bbox
    且两件间距 >= sp。所有计算在“A bbox 左下角归一化”的坐标系里做。
    返回 dict:
      {cw, ch, parts:[{poly(世界), rx, ry}]}
    parts 的 rx,ry = 该件世界多边形应平移的量，使 A 的 bbox 左下角落在原点、
    B 落在最佳位置；组合 bbox 即 (cw,ch)。
    """
    ab = poly_a.bounds
    aw, ah = ab[2] - ab[0], ab[3] - ab[1]
    # A 归一化：世界 -> 其 bbox 左下角为原点
    A = translate(poly_a, xoff=-ab[0], yoff=-ab[1])

    best = None
    # 尝试 B 的两种朝向：原样 / 旋转180
    for angle in (0, 180):
        B = poly_b
        if angle == 180:
            B = rotate(poly_b, 180, origin=(poly_b.centroid.x, poly_b.centroid.y))
        bb = B.bounds
        B0 = translate(B, xoff=-bb[0], yoff=-bb[1])  # B 归一化
        r = _scan(A, B0, aw, ah, sp, quick)
        if r is None:
            continue
        cw, ch, bx, by = r
        if best is None or cw * ch < best[0]:
            best = (cw * ch, cw, ch, bx, by, angle)
    if best is None:
        return None

    _, cw, ch, bx, by, angle = best

    # 组合 bbox 的真实最小角（B 可能位于 A 左/下方，故 min 可为负）
    parts = []
    # A 件：世界 poly 平移到其 bbox 左下角到原点
    parts.append({'poly': poly_a, 'rx': -ab[0], 'ry': -ab[1]})
    if angle == 180:
        B = rotate(poly_b, 180, origin=(poly_b.centroid.x, poly_b.centroid.y))
    else:
        B = poly_b
    bb = B.bounds
    parts.append({'poly': B, 'rx': -bb[0] + bx, 'ry': -bb[1] + by})

    # 计算两件在此配置下的联合 bbox，统一平移到 (0,0)
    xs = []
    ys = []
    for pt in parts:
        b = translate(pt['poly'], xoff=pt['rx'], yoff=pt['ry']).bounds
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    minx, miny = min(xs), min(ys)
    cw = max(xs) - minx
    ch = max(ys) - miny
    for pt in parts:
        pt['rx'] -= minx
        pt['ry'] -= miny
    return {'cw': cw, 'ch': ch, 'parts': parts}


def _scan(A, B0, aw, ah, sp, quick):
    """
    固定 A（原点，bbox 宽 aw 高 ah），把 B 从右侧滑向 A，找最小组合 bbox。
    对每个 y 偏移，用二分找“B 刚不碰 A 外扩 sp”的最小 x，再在所有 y 里取
    组合 bbox 面积最小者。返回 (cw,ch,bx,by) 或 None。
    """
    pa_buf = prepared.prep(A.buffer(sp))
    bb = B0.bounds
    bw_ = bb[2] - bb[0]
    bh_ = bb[3] - bb[1]
    lo_x = -aw           # B 完全在 A 左侧
    hi_x = aw + bw_ + sp  # B 完全在 A 右侧

    def touches(x, y):
        return pa_buf.intersects(translate(B0, xoff=x, yoff=y))

    ystep = 10 if quick else 5
    ylo, yhi = -ah - bh_, ah + bh_
    best = None
    y = ylo
    while y <= yhi:
        # B 在右侧足够远处不碰，向左二分到刚接触
        if not touches(hi_x, y):
            lo, hi = hi_x, lo_x + 2 * aw + bw_ + 2 * sp
            # 二分边界：hi 一定不碰，lo 一定碰（或直接取 -inf）
            lo = -aw - bw_ - sp
            for _ in range(30):
                mid = (lo + hi) / 2
                if touches(mid, y):
                    lo = mid
                else:
                    hi = mid
            x = hi
            c = translate(B0, xoff=x, yoff=y).bounds
            w = max(c[2], aw) - min(c[0], 0)
            h = max(c[3], ah) - min(c[1], 0)
            if best is None or w * h < best[0]:
                best = (w * h, w, h, x, y)
        y += ystep
    if best is None:
        return None
    # 局部精扫（1mm）
    _, bw_, bh_, bx, by = best
    fine = None
    for iy in range(-5, 6):
        y = by + iy
        for ix in range(-5, 6):
            x = bx + ix
            if not touches(x, y):
                c = translate(B0, xoff=x, yoff=y).bounds
                w = max(c[2], aw) - min(c[0], 0)
                h = max(c[3], ah) - min(c[1], 0)
                if fine is None or w * h < fine[0]:
                    fine = (w * h, w, h, x, y)
    if fine is None:
        fine = best
    return fine[1], fine[2], fine[3], fine[4]


def build_pairs(units, sp, pair_win, quick=False, complex_only=False):
    """
    对所有单元两两尝试（限制：bbox 面积相近的候选），生成超单元。
    每个件选收益最大的配对伙伴（而非第一个合格者）。
    返回 (superunits, unmatched, total_saved_area)。
    """
    cands = []
    for u in units:
        poly = unit_polygon(u)
        if poly is None or poly.area < 100:
            continue
        bb = u.outer.bbox
        if complex_only:
            fill = poly.area / max(bb.width * bb.height, 1e-9)
            if fill > 0.80:
                continue
        cands.append({
            'unit': u, 'poly': poly,
            'w': bb.width, 'h': bb.height, 'area': poly.area,
            'used': False,
        })

    # 按 bbox 尺寸相近聚成候选池，避免 O(n^2)
    cands.sort(key=lambda c: (round(c['w']), round(c['h'])))
    pools = {}
    for c in cands:
        key = (round(c['w']), round(c['h']))
        pools.setdefault(key, []).append(c)

    # 贪心：池内 + 相邻尺寸池，选全局收益最大的一对
    from heapq import heappush, heappop
    heap = []  # (-gain, key)
    pair_cache = {}
    pool_keys = sorted(pools.keys())
    superunits = []
    used_units = set()
    total_saved = 0.0

    def try_pair(a, b):
        big, small = max(a['area'], b['area']), min(a['area'], b['area'])
        if small / max(big, 1e-9) < 0.5:
            return
        res = _pair_nest(a['poly'], b['poly'], sp, quick)
        if res is None:
            return
        cw, ch = res['cw'], res['ch']
        base = a['w'] * a['h'] + b['w'] * b['h']
        gain = 1 - (cw * ch) / base
        if gain >= pair_win / 100.0:
            key = (id(a['unit']), id(b['unit']))
            pair_cache[key] = (res, gain, cw, ch, a, b)
            heappush(heap, (-gain, key))

    # 同池内两两 + 相邻池（尺寸相差 <=1 的池）两两
    for ki, key in enumerate(pool_keys):
        pool = pools[key]
        for i in range(len(pool)):
            ia = pool[i]
            if ia['used']:
                continue
            for j in range(i + 1, len(pool)):
                try_pair(ia, pool[j])
        # 相邻池
        for kk in range(ki + 1, len(pool_keys)):
            key2 = pool_keys[kk]
            dw = abs(key[0] - key2[0])
            dh = abs(key[1] - key2[1])
            if dw <= 1 and dh <= 1:
                for ia in pool:
                    for jb in pools[key2]:
                        try_pair(ia, jb)

    while heap:
        neg, key = heappop(heap)
        ia, jb = key
        a = pair_cache[key][4]
        b = pair_cache[key][5]
        if a['used'] or b['used']:
            continue
        res, gain, cw, ch = pair_cache[key][:4]
        superunits.append({
            'w': cw, 'h': ch,
            'parts': res['parts'],
            'gain': gain,
        })
        total_saved += (a['w'] * a['h'] + b['w'] * b['h']) - cw * ch
        a['used'] = True
        b['used'] = True
        used_units.add(id(a['unit']))
        used_units.add(id(b['unit']))

    unmatched = [u for u in units if id(u) not in used_units]
    return superunits, unmatched, total_saved


# ---------------------------------------------------------------------------
# 4. 重叠校验（真实轮廓 + 间距）
# ---------------------------------------------------------------------------
def _place_poly(poly, x, y, rot, uh, origin_xy=None):
    """
    将世界坐标 poly 按 LISP nest-move-unit 的变换放到放置点 (x,y)。
    rot=True 时：绕 origin_xy（默认 poly 世界 bbox 左下角）旋转 90°，再平移
    (x+uh, y)。origin_xy 用于超单元（整体绕超单元 bbox 左下角旋转）。
    返回放置后的多边形。
    """
    bb = poly.bounds
    if origin_xy is None:
        ox, oy = bb[0], bb[1]
    else:
        ox, oy = origin_xy
    if rot:
        poly = rotate(poly, 90, origin=(ox, oy))
        return translate(poly, xoff=(x + uh - ox), yoff=(y - oy))
    return translate(poly, xoff=(x - ox), yoff=(y - oy))


def count_overlaps(boards, sp):
    """返回真实轮廓重叠的对数（间距不足也算）。仅在同一板内比较。"""
    n = 0
    eps = 0.1  # 允许恰好 = sp 的间距（buffer 触碰不算违规）
    for board in boards:
        polys = []
        for x, y, rot, pw, ph, obj in board:
            if isinstance(obj, dict) and 'parts' in obj:
                # 超单元：整体绕其 bbox 左下角 (0,0) 旋转/平移
                for p in obj['parts']:
                    local = translate(p['poly'], xoff=p['rx'], yoff=p['ry'])
                    polys.append(_place_poly(local, x, y, rot, obj['h'],
                                             origin_xy=(0.0, 0.0)))
            else:
                poly = unit_polygon(obj)
                if poly is None:
                    continue
                # LISP nest-move-unit: rot 时 dx += uh(原始高)。原始高=放置宽 pw
                polys.append(_place_poly(poly, x, y, rot, pw if rot else ph))
        prepped = [prepared.prep(p) for p in polys]
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                a, b = polys[i], polys[j]
                if not _bb_overlap(a.bounds, b.bounds):
                    continue
                # 间距 < sp 视为重叠（略减 eps 避免边界触碰误判）
                if a.buffer(sp - eps).intersects(b):
                    n += 1
    return n


def _bb_overlap(ba, bb):
    return (ba[0] <= bb[2] and bb[0] <= ba[2]
            and ba[1] <= bb[3] and bb[1] <= ba[3])


# ---------------------------------------------------------------------------
# 5. 汇总报告
# ---------------------------------------------------------------------------
def summarize(boards, bw, bh, label):
    n_boards = len(boards)
    n_parts = sum(len(b) for b in boards)
    used = sum(w * h for b in boards for x, y, r, w, h, o in b)
    util = used / (n_boards * bw * bh) * 100 if n_boards else 0
    return n_boards, n_parts, util


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith('--spacing='):
            kw['sp'] = float(a.split('=', 1)[1])
        elif a.startswith('--boards='):
            kw['board'] = a.split('=', 1)[1]
        elif a.startswith('--pair-win='):
            kw['pair_win'] = float(a.split('=', 1)[1])
        elif a == '--no-pair':
            kw['no_pair'] = True
        elif a == '--pair-only':
            kw['pair_only'] = True
        elif a == '--dump':
            kw['dump'] = True
        elif a == '--quick':
            kw['quick'] = True
        elif a == '--complex-only':
            kw['complex_only'] = True
        elif a.startswith('--only-shapes='):
            kw['only_shapes'] = a.split('=', 1)[1]
        elif a.startswith('--max-units='):
            kw['max_units'] = int(a.split('=', 1)[1])

    sp = kw.get('sp', 10.0)
    mg = 10.0
    board_s = kw.get('board', '600x850')
    try:
        bw, bh = [float(x) for x in board_s.lower().split('x')]
    except Exception:
        raise SystemExit(f"[错误] 板材格式应为 宽x高，如 600x850，得到 {board_s}")
    pair_win = kw.get('pair_win', 8.0)
    quick = kw.get('quick', False)

    dxf_path = args[0] if args else None
    if not dxf_path:
        dxf_path = os.path.join(_ROOT, 'QDG193264913.dxf')
    if not os.path.exists(dxf_path):
        alt = os.path.join(_ROOT, dxf_path)
        if os.path.exists(alt):
            dxf_path = alt
    if not os.path.exists(dxf_path):
        raise SystemExit(f"[错误] 文件不存在: {dxf_path}")

    print("=" * 62)
    print(f"配对嵌合原型 | 文件: {os.path.basename(dxf_path)}")
    print(f"板材 {bw}x{bh} | 间距 {sp}mm | 边距 {mg}mm | 配对收益阈值 {pair_win}%")
    print("=" * 62)

    t0 = time.time()
    units = load_units(dxf_path)
    # 只保留“可入板”的真实件（bbox 不超可用区）
    usable = [u for u in units
              if u.outer.bbox.width <= bw - 2 * mg + 1e-6
              and u.outer.bbox.height <= bh - 2 * mg + 1e-6]
    if kw.get('only_shapes'):
        # 模拟“框选一批同类件”：只保留 bbox 落在 WxH±tol 的单元
        try:
            ow, oh = [float(x) for x in kw['only_shapes'].lower().split('x')]
        except Exception:
            raise SystemExit(f"[错误] --only-shapes 应为 宽x高，如 250x95")
        usable = [u for u in usable
                  if abs(u.outer.bbox.width - ow) <= 5
                  and abs(u.outer.bbox.height - oh) <= 5]
    if kw.get('max_units'):
        # 调试用：只取前 N 个（按 bbox 面积降序，保留大件）
        usable = sorted(usable, key=lambda u: -u.outer.bbox.width * u.outer.bbox.height)
        usable = usable[:kw['max_units']]
    print(f"聚类单元 {len(units)}，可入板 {len(usable)} ({(time.time() - t0):.1f}s)")

    # ---- 基线：当前 bbox 排法（不配对） ----
    t0 = time.time()
    base_items = [(u.outer.bbox.width, u.outer.bbox.height, u) for u in usable]
    base_boards = pack_bbox(base_items, bw, bh, sp, mg)
    b_n, b_p, b_u = summarize(base_boards, bw, bh, '基线')
    b_ov = count_overlaps(base_boards, sp)
    print(f"[基线] bbox排法: {b_n} 板 | {b_p} 件 | 利用率 {b_u:.1f}% "
          f"| 真实重叠 {b_ov} ({(time.time() - t0):.1f}s)")

    # ---- 配对版 ----
    if kw.get('no_pair', False):
        return 0
    t0 = time.time()
    superunits, unmatched, saved_area = build_pairs(
        usable, sp, pair_win, quick,
        complex_only=kw.get('complex_only', False))
    print(f"[配对] 成功超单元 {len(superunits)}，未配对 {len(unmatched)} "
          f"| 节省面积 {saved_area:,.0f} mm² ({100 * saved_area / max(sum(u.outer.bbox.width * u.outer.bbox.height for u in usable), 1e-9):.1f}%) "
          f"({(time.time() - t0):.1f}s)")
    if kw.get('pair_only', False):
        base_boards = None
        base_items = []

    items = []
    for su in superunits:
        items.append((su['w'], su['h'], su))
    for u in unmatched:
        items.append((u.outer.bbox.width, u.outer.bbox.height, u))
    pair_boards = pack_bbox(items, bw, bh, sp, mg)
    p_n, p_p, p_u = summarize(pair_boards, bw, bh, '配对')
    p_ov = count_overlaps(pair_boards, sp)
    print(f"[配对] 排样结果: {p_n} 板 | {p_p} 件 | 利用率 {p_u:.1f}% "
          f"| 真实重叠 {p_ov}")

    # ---- 对比 ----
    if base_boards is not None:
        print("-" * 62)
        print(f"板数: {b_n} -> {p_n}   (节省 {b_n - p_n})")
        print(f"利用率: {b_u:.1f}% -> {p_u:.1f}%   (+{p_u - b_u:.1f}pp)")
        print(f"重叠: {b_ov} -> {p_ov}")
        if p_ov == 0 and p_n < b_n:
            print("结论: 配对嵌合有效且零重叠，值得移植 LISP。")
        elif p_ov == 0:
            print("结论: 配对零重叠但板数未减，需调低配对阈值或换样本验证。")
        else:
            print("结论: 配对后仍有重叠，嵌合/间距逻辑需修复。")
    return 0


if __name__ == '__main__':
    sys.exit(main())
