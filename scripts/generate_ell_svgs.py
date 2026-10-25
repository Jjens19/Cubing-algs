"""Regenerate vector ELL diagrams from the original PNG sticker-color samples."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def generate():
    layouts = [(f'U{i}', i % 3 + 2, i // 3 + 2) for i in range(9)]
    layouts += [(f'B{2-i}', i+2, 1) for i in range(3)]
    layouts += [(f'F{i}', i+2, 5) for i in range(3)]
    layouts += [(f'L{i}', 1, i+2) for i in range(3)]
    layouts += [(f'R{2-i}', 5, i+2) for i in range(3)]
    cases = json.loads((ROOT / 'src/ell_stickers.json').read_text())
    for filename, stickers in cases.items():
        svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg', viewBox='0 0 100 100', width='100', height='100')
        for key, x, y in layouts:
            ET.SubElement(svg, 'rect', {
                'data-key': key,
                'x': str(3 if x == 1 else 85 if x == 5 else 16+(x-2)*23),
                'y': str(3 if y == 1 else 85 if y == 5 else 16+(y-2)*23),
                'width': str(13 if x in (1, 5) else 23), 'height': str(13 if y in (1, 5) else 23),
                'fill': stickers[key]['color'], 'stroke': '#000000', 'stroke-width': '3'})
        (ROOT / 'ELL' / filename).write_text(ET.tostring(svg, encoding='unicode')+'\n')
    print(f'Generated {len(cases)} SVGs with the original case colors and orientations.')


if __name__ == '__main__':
    generate()
