import sys
sys.stdout.reconfigure(encoding='utf-8')
import ezdxf
import re

doc = ezdxf.readfile('test_pro.dxf')
msp = doc.modelspace()

# 统计所有文字实体
texts = []
for e in msp:
    if e.dxftype() == 'TEXT':
        try:
            text = e.dxf.text.strip()
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            texts.append((text, x, y))
        except:
            pass
    elif e.dxftype() == 'MTEXT':
        try:
            text = e.text.strip()
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            texts.append((text, x, y))
        except:
            pass

print(f'总文字实体: {len(texts)}')

# 筛选可能的厚度标注
thickness_pattern = re.compile(r'^(\d+\.?\d*)$')
thickness_texts = []
for text, x, y in texts:
    match = thickness_pattern.match(text)
    if match:
        value = float(match.group(1))
        if 0.1 <= value <= 10.0:
            thickness_texts.append((text, x, y, value))

print(f'\n厚度标注: {len(thickness_texts)}')
for text, x, y, value in sorted(thickness_texts, key=lambda t: t[3]):
    print(f'  {value}mm: ({x:.1f}, {y:.1f})')

# 显示所有文字
print(f'\n所有文字 (前30个):')
for text, x, y in texts[:30]:
    print(f'  "{text}": ({x:.1f}, {y:.1f})')
