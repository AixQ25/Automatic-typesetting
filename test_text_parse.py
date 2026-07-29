import sys
sys.stdout.reconfigure(encoding='utf-8')
import ezdxf

doc = ezdxf.readfile('test.dxf')
msp = doc.modelspace()

print("=== TEXT entities ===")
for e in msp:
    if e.dxftype() == 'TEXT':
        try:
            text = e.dxf.text
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            print(f'  TEXT: "{text}", pos=({x:.1f}, {y:.1f}), layer={e.dxf.layer}')
        except Exception as ex:
            print(f'  TEXT error: {ex}')

print("\n=== MTEXT entities ===")
for e in msp:
    if e.dxftype() == 'MTEXT':
        try:
            text = e.text
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            print(f'  MTEXT: "{text}", pos=({x:.1f}, {y:.1f}), layer={e.dxf.layer}')
        except Exception as ex:
            print(f'  MTEXT error: {ex}')

print("\n=== Entity summary ===")
types = {}
for e in msp:
    t = e.dxftype()
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items()):
    print(f'  {t}: {c}')
