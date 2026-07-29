import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf

doc = ezdxf.readfile('test.dxf')
msp = doc.modelspace()

entities = list(msp)
print(f'Total entities: {len(entities)}')
print()

for i, e in enumerate(entities):
    t = e.dxftype()
    try:
        layer = e.dxf.layer
    except:
        layer = '?'
    
    if t == 'POLYLINE':
        verts = list(e.vertices)
        coords = [(v.dxf.location.x, v.dxf.location.y) for v in verts]
        print(f'{i}: {t}, layer={layer}, closed={e.is_closed}, verts={len(verts)}')
    elif t == 'LWPOLYLINE':
        pts = list(e)
        print(f'{i}: {t}, layer={layer}, closed={e.closed}, verts={len(pts)}')
    else:
        print(f'{i}: {t}, layer={layer}')
