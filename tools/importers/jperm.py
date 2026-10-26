"""Bundle downloaded J Perm WV, OLL, and PLL lists."""
import argparse
import json
from pathlib import Path
import re
from tools.importers.common import ROOT, diagram, normalize

def parse(source):
    pattern = r'\{name:("(?:\\.|[^"\\])*"|\d+),alg:(\[.*?\]),group:("(?:\\.|[^"\\])*")'
    return [{'name': json.loads(name), 'algorithms': json.loads(algorithms), 'group': json.loads(group)}
            for name, algorithms, group in re.findall(pattern, source)]


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
    (ROOT / 'src/data/jperm_algorithms.json').write_text(json.dumps(bundled, indent=2)+'\n')
    print('Bundled', len(bundled['cases']), 'J Perm cases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    build(parser.parse_args().input)
