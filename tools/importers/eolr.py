"""Import EOLR source diagrams and complete their masked edges to legal setups."""
import argparse
import html
import json
from pathlib import Path
import re

import kociemba
from tools.importers.common import ROOT, COLORS, LAYOUT, normalize, render_diagram, gray_misoriented_edges, full_cube_stickers, render_full_cube
from src.scrambler import Cube, GEOMETRY, FACES, SOLVED, invert

SOURCE = 'https://cubingapp.com/algorithms/LSE-EOLR'
POSITIONS = {}
for index, (position, _) in enumerate(GEOMETRY):
    POSITIONS.setdefault(position, []).append(index)
EDGES = [indices for position, indices in POSITIONS.items() if len(indices) == 2]


def goal(state):
    # EO is relative to the fixed Roux blocks, not the free M-slice centers.
    return ({frozenset(state[i] for i in POSITIONS[p]) for p in ((0, -1, 1), (0, -1, -1))}
            == {frozenset('UL'), frozenset('UR')})


def complete(known, algorithm):
    for auf in ('', 'U', "U'", 'U2'):
        for middle in ('', 'M', "M'", 'M2'):
            base = Cube().apply(auf).apply(middle).facelets
            nonedges = [i for indices in POSITIONS.values() if len(indices) != 2 for i in indices]
            if any(base[i] != color for i, color in known.items() if i in nonedges):
                continue
            choices = []
            for indices in EDGES:
                fixed = any(abs(GEOMETRY[i][0][0]) == 1 and GEOMETRY[i][0][1] <= 0 for i in indices)
                options = []
                for identity, original in enumerate(EDGES):
                    pair = [SOLVED[i] for i in original]
                    for colors in (pair, pair[::-1]):
                        if fixed and colors != [base[i] for i in indices]:
                            continue
                        if all(i not in known or known[i] == color for i, color in zip(indices, colors)):
                            options.append((identity, colors))
                choices.append((indices, options))
            choices.sort(key=lambda item: len(item[1]))
            def search(offset, used):
                if offset == len(choices):
                    state = ''.join(base)
                    if not goal(Cube(state).apply(algorithm).facelets):
                        return None
                    try:
                        rotation = next(r for r in ('', 'x', "x'", 'x2') if all(Cube(state).apply(r).facelets[i*9+4] == face for i, face in enumerate(FACES)))
                        oriented = ''.join(Cube(state).apply(rotation).facelets)
                        solution = kociemba.solve(oriented)
                    except ValueError:
                        return None
                    return state, (invert(solution)+' '+invert(rotation)).strip()
                indices, options = choices[offset]
                for identity, colors in options:
                    if identity in used:
                        continue
                    for i, color in zip(indices, colors):
                        base[i] = color
                    found = search(offset+1, used | {identity})
                    if found:
                        return found
                return None
            found = search(0, set())
            if found:
                return found
    raise ValueError('No legal EOLR completion for '+algorithm)


def build(page):
    chunks = re.findall(r'<div class="viz-3x3">(.*?)<div class="prose"><h3>(.*?)</h3>(.*?)</div>', page)
    directory = ROOT / 'src/static/cases/lse/eolr'
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for number, (viz, title, body) in enumerate(chunks, 1):
        title = html.unescape(title)
        algorithms = [normalize(html.unescape(re.sub('<[^>]*>', '', text)).replace('•', '').strip())
                      for text in re.findall(r'<p>(.*?)</p>', body)]
        cells = re.findall(r'<x-([udlrfb])></x-\1>|<div></div>', viz)
        assert len(cells) == 27
        known = {FACES.index(face)*9+row*3+col: cells[f*9+col*3+row].upper()
                 for f, face in enumerate('UFR') for row in range(3) for col in range(3)
                 if cells[f*9+col*3+row]}
        state, setup = complete(known, algorithms[0])
        assert ''.join(Cube().apply(setup).facelets) == state
        # Native top-view geometry; complete masked stickers for playable setups.
        stickers = {key: {'color': COLORS[state[FACES.index(key[0])*9+int(key[1])]], 'highlight': False}
                    for key, _, _ in LAYOUT}
        gray_misoriented_edges(stickers)
        stickers = full_cube_stickers(state, 'EOLR', stickers)
        filename = str(number)+'.svg'
        (directory / filename).write_text(render_full_cube(stickers))
        cases.append({'name': title, 'alg_set': 'LSE', 'category': 'EOLR / '+title.split(' (')[0].replace(' / ', '–'),
                      'algorithm': algorithms[0], 'alternatives': algorithms[1:], 'source': SOURCE,
                      'source_stickers': {str(i): c for i, c in known.items()},
                      'facelets': state, 'setup': setup, 'stickers': stickers, 'image': '/cases/lse/eolr/'+filename})
    assert len(cases) == 46
    (ROOT / 'src/data/eolr_algorithms.json').write_text(json.dumps({'source': SOURCE, 'cases': cases}, indent=2)+'\n')
    print('Bundled 46 EOLR cases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, required=True)
    build(parser.parse_args().page.read_text())
