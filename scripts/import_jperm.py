"""Bundle J Perm lists downloaded as wv.js, oll.js and pll.js.

Run from the repository root: python -m scripts.import_jperm --input /tmp/jperm
The input directory should contain the three original JavaScript lists.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from src.scrambler import Cube, FACES, SOLVED, invert
from src.server import inverse

ROOT = Path(__file__).resolve().parents[1]
COLORS = {'U': '#ffff00', 'R': '#ff9900', 'F': '#00ff00', 'D': '#ffffff',
          'L': '#ff0000', 'B': '#0000ff', 'X': '#aab2a7'}
LAYOUT = [(f'U{i}', i % 3 + 2, i // 3 + 2) for i in range(9)]
LAYOUT += [(f'B{2-i}', i+2, 1) for i in range(3)]
LAYOUT += [(f'F{i}', i+2, 5) for i in range(3)]
LAYOUT += [(f'L{i}', 1, i+2) for i in range(3)]
LAYOUT += [(f'R{2-i}', 5, i+2) for i in range(3)]


def normalize(algorithm):
    # J Perm uses parentheses for finger-trick groups, not repetitions.
    result = ' '.join(algorithm.replace('(', ' ').replace(')', ' ').split())
    inverse(result)
    return result


def parse(source):
    pattern = r'\{name:("(?:\\.|[^"\\])*"|\d+),alg:(\[.*?\]),group:("(?:\\.|[^"\\])*")'
    return [{'name': json.loads(name), 'algorithms': json.loads(algorithms), 'group': json.loads(group)}
            for name, algorithms, group in re.findall(pattern, source)]


def diagram(algorithm, subset):
    state = Cube().apply(invert(algorithm))
    target = state.normalized()
    # Apply the orientation/WV mask before the scramble, as J Perm does:
    # hide last-layer side colors, retain F2L colors carried up by a WV pair.
    masked = list(SOLVED)
    if subset in ('WV', 'OLL'):
        for face in 'RFLB':
            start = FACES.index(face)*9
            masked[start:start+3] = ['X']*3
    colored = Cube(''.join(masked)).apply(invert(algorithm)).facelets
    centers = {state.facelets[i*9+4]: face for i, face in enumerate(FACES)}
    colored = [centers.get(color, color) for color in colored]
    stickers = {key: {'color': COLORS[colored[FACES.index(key[0])*9+int(key[1])]], 'highlight': False}
                for key, _, _ in LAYOUT}
    svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg', viewBox='0 0 100 100', width='100', height='100')
    for key, x, y in LAYOUT:
        ET.SubElement(svg, 'rect', {
            'x': str(3 if x == 1 else 85 if x == 5 else 16+(x-2)*23),
            'y': str(3 if y == 1 else 85 if y == 5 else 16+(y-2)*23),
            'width': str(13 if x in (1, 5) else 23), 'height': str(13 if y in (1, 5) else 23),
            'fill': stickers[key]['color'], 'stroke': '#000000', 'stroke-width': '3'})
    return ET.tostring(svg, encoding='unicode')+'\n', target, stickers


def build(directory):
    bundled = {'sources': {name.upper(): 'https://jperm.net/algs/'+name for name in ['wv', 'oll', 'pll']}, 'cases': []}
    for subset, expected in [('WV', 27), ('OLL', 57), ('PLL', 21)]:
        entries = parse((directory / (subset.lower()+'.js')).read_text())
        assert len(entries) == expected, (subset, len(entries))
        output = ROOT / 'src/static/cases' / subset.lower()
        output.mkdir(exist_ok=True, parents=True)
        for index, entry in enumerate(entries, 1):
            original = entry['algorithms'][0]
            algorithm = normalize(original)
            slug = str(entry['name']).lower() if subset != 'WV' else str(index)
            name = f'WV {index} — {entry["name"]}' if subset == 'WV' else f'OLL {entry["name"]}' if subset == 'OLL' else str(entry['name'])
            svg, target, stickers = diagram(algorithm, subset)
            (output / (slug+'.svg')).write_text(svg)
            bundled['cases'].append({'alg_set': subset, 'name': name, 'category': entry['group'],
                'algorithm': algorithm, 'source_algorithm': original, 'source_index': index,
                'alternatives': entry['algorithms'][1:], 'image': f'/cases/{subset.lower()}/{slug}.svg',
                'source': bundled['sources'][subset], 'facelets': target, 'stickers': stickers})
    (ROOT / 'src/jperm_algorithms.json').write_text(json.dumps(bundled, indent=2)+'\n')
    print('Bundled', len(bundled['cases']), 'J Perm cases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    build(parser.parse_args().input)
