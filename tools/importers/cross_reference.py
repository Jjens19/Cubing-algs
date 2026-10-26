"""Cross-reference bundled J Perm cases with downloaded SpeedCubeDB pages."""
import argparse
import json
from pathlib import Path
from tools.importers.common import ROOT, diagram, normalize, parse, match_pose, stage_solved
from src.scrambler import Cube

def build(directory):
    original = json.loads((ROOT / 'src/data/jperm_algorithms.json').read_text())['cases']
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
    (ROOT / 'src/data/speedcubedb_overrides.json').write_text(json.dumps({'cases': records}, indent=2)+'\n')
    print('Cross-referenced', len(records), 'cases.')
    for subset in ['WV', 'OLL', 'PLL']:
        changed = sum(c['alg_set'] == subset and c['algorithm'] != c['previous_algorithm'] for c in records)
        print(subset, changed, 'different main algorithms')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    build(parser.parse_args().input)
