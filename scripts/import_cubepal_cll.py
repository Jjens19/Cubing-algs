"""Build the bundled CLL data from downloaded CubePal HTML and diagram SVG.

Usage: python scripts/import_cubepal_cll.py --page page.html --sprite c3cll.svg
"""
import argparse
import copy
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://www.cubepal.app/cubes/3x3x3/stages/cll'
SVG = 'http://www.w3.org/2000/svg'
# CubePal's default diagram colors; unimportant edges remain gray.
COLORS = {'core': '#111111', 'grayd': '#51565d', 'fill': '#ffdd00',
          'u': '#ffdd00', 'f': '#007bff', 'r': '#ff0f0f', 'l': '#fc6d00', 'b': '#00b306'}
CORNER_IDS = {'1': 'U0', '5': 'U2', '21': 'U6', '25': 'U8',
              '45': 'L0', '41': 'L2', '40': 'F0', '36': 'F2',
              '35': 'R0', '31': 'R2', '30': 'B0', '26': 'B2'}


def build(page, sprite):
    root = ET.fromstring(sprite)
    elements = {e.get('id'): e for e in root.iter() if e.get('id')}

    def expand(element, fill='#000000', opacity=1, paths=None, colors=None):
        paths = [] if paths is None else paths
        colors = {} if colors is None else colors
        fill = element.get('fill', fill)
        opacity *= float(element.get('fill-opacity', 1))
        tag = element.tag.split('}')[-1]
        if tag == 'use':
            expand(elements[element.get('href')[1:]], fill, opacity, paths, colors)
        elif tag == 'path':
            path = ET.Element(f'{{{SVG}}}path', {'d': element.get('d'), 'fill': fill, 'fill-opacity': str(opacity)})
            paths.append(path)
            colors[element.get('id')] = fill
        else:
            for child in element:
                expand(child, fill, opacity, paths, colors)
        return paths, colors

    directory = ROOT / 'src/static/cases/cll'
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for name, body in re.findall(r'<h5 id="([^"]+)">.*?</h5>(.*?)(?=<h5|<h[24]|$)', page, re.S):
        algorithms = [html.unescape(re.sub('<[^>]+>', '', text)).strip()
                      for text in re.findall(r'<div class="alg"><a[^>]*>(.*?)</a>', body, re.S)]
        symbol = re.search(r'c3cll.svg#([^"]+)', body).group(1)
        assert symbol in (name, 'cll_' + name)
        assert algorithms
        paths, source_colors = expand(elements[symbol])
        image = ET.Element(f'{{{SVG}}}svg', {'viewBox': '0 0 420 420', 'width': '420', 'height': '420'})
        for path in paths:
            path = copy.deepcopy(path)
            for key, value in COLORS.items():
                if path.get('fill') == f'var(--color-{key})':
                    path.set('fill', value)
            assert 'var(' not in path.get('fill')
            image.append(path)
        ET.register_namespace('', SVG)
        (directory / f'{name}.svg').write_text('<!-- License: MIT. Diagram by CubePal: https://www.cubepal.app -->\n' + ET.tostring(image, encoding='unicode') + '\n')
        cases.append({'name': name.upper(), 'category': re.sub(r'\d+$', '', name).upper(),
                      'algorithm': algorithms[0], 'alternatives': algorithms[1:],
                      'image': f'/cases/cll/{name}.svg', 'source': SOURCE + '#' + name,
                      'corner_facelets': {key: source_colors[id].removeprefix('var(--color-').removesuffix(')').upper()
                                          for id, key in CORNER_IDS.items()}})
    assert len(cases) == 42
    (ROOT / 'src/cll_algorithms.json').write_text(json.dumps({'source': SOURCE, 'cases': cases}, indent=2) + '\n')
    print(f'Imported {len(cases)} CLL cases with {sum(1 + len(c["alternatives"]) for c in cases)} algorithms.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, required=True)
    parser.add_argument('--sprite', type=Path, required=True)
    args = parser.parse_args()
    build(args.page.read_text(), args.sprite.read_text())
