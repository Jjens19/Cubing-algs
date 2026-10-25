"""Match downloaded SpeedCubeDB WV/OLL/PLL pages to existing J Perm cases.

python -m scripts.cross_reference_speedcubedb --input /tmp/scdb
"""
import argparse
import html
import json
from pathlib import Path
import re

from scripts.import_jperm import ROOT, diagram, normalize
from src.scrambler import Cube, FACES, SOLVED


def stage_solved(state, subset):
    if subset == 'PLL':
        return any(Cube(state).apply(auf).normalized() == SOLVED for auf in ['', 'U', "U'", 'U2'])
    return state[:9] == 'U'*9 and all(
        state[i*9+(0 if face == 'D' else 3):(i+1)*9] == face*(9-(0 if face == 'D' else 3))
        for i, face in enumerate(FACES) if face != 'U')


def parse(page):
    parts = re.split(r'<div class="row singlealgorithm[^>]*data-alg="([^"]+)"[^>]*>', page)
    cases = []
    for name, body in zip(parts[1::2], parts[2::2]):
        algorithms = [html.unescape(re.sub('<[^>]*>', '', text)).strip()
                      for text in re.findall(r'<div class="formatted-alg">(.*?)</div>', body, re.S)]
        setup = html.unescape(re.search(r'<div class="setup-case[^>]*><div>setup:</div>(.*?)</div>', body, re.S).group(1)).strip()
        cases.append({'source_name': name, 'source_algorithms': algorithms, 'source_setup': setup,
                      'algorithm': normalize(algorithms[0])})
    return cases


def match_pose(facelets, algorithm, subset):
    for rotation in ['', 'y', "y'", 'y2']:
        for auf in ['', 'U', "U'", 'U2']:
            state = Cube(Cube(facelets).apply(rotation).normalized()).apply(auf).apply(algorithm).normalized()
            if stage_solved(state, subset):
                return {'rotation': rotation, 'auf': auf}
    return None


def build(directory):
    original = json.loads((ROOT / 'src/jperm_algorithms.json').read_text())['cases']
    records = []
    for subset, count in [('WV', 27), ('OLL', 57), ('PLL', 21)]:
        source = parse((directory / (subset+'.html')).read_text())
        assert len(source) == count
        used = set()
        for case in [c for c in original if c['alg_set'] == subset]:
            candidates = source if subset == 'WV' else [c for c in source if c['source_name'] == case['name']]
            matches = [(entry, match_pose(case['facelets'], entry['algorithm'], subset)) for entry in candidates]
            matches = [(entry, pose) for entry, pose in matches if pose is not None]
            assert len(matches) == 1, (subset, case['name'], matches)
            entry, pose = matches[0]
            assert entry['source_name'] not in used
            used.add(entry['source_name'])
            assert stage_solved(Cube().apply(entry['source_setup']).apply(entry['algorithm']).normalized(), subset)
            svg, target, stickers = diagram(entry['algorithm'], subset)
            image = ROOT / 'src/static' / case['image'].lstrip('/')
            image.write_text(svg)
            records.append({**entry, 'alg_set': subset, 'name': case['name'], 'image': case['image'],
                'previous_algorithm': case['algorithm'], 'previous_facelets': case['facelets'],
                'match': pose, 'source': 'https://speedcubedb.com/a/3x3/'+subset,
                'facelets': target, 'stickers': stickers})
        assert len(used) == count
    (ROOT / 'src/speedcubedb_overrides.json').write_text(json.dumps({'cases': records}, indent=2)+'\n')
    print('Cross-referenced', len(records), 'cases.')
    for subset in ['WV', 'OLL', 'PLL']:
        changed = sum(c['alg_set'] == subset and c['algorithm'] != c['previous_algorithm'] for c in records)
        print(subset, changed, 'different main algorithms')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    build(parser.parse_args().input)
