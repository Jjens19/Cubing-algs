"""Bundle a SpeedCubeDB subset using the shared parser and diagram renderer.

Example: python -m tools.importers.speedcubedb COLL --page /tmp/coll.html
"""
import argparse
import html
import json
from pathlib import Path
import re

from tools.importers.common import ROOT, diagram, normalize, parse

# Page name, case count, output stem, diagram mask.
SUBSETS = {
    'COLL': ('COLL', 40, 'coll', 'COLL'),
    'CMLL': ('CMLL', 42, 'cmll', 'CMLL'),
    'SV': ('SV', 27, 'sv', 'WV'),
    'LSE': ('EO4A', 9, 'lse', 'LSE'),
    'Anti PLL': ('AntiPLL', 22, 'antipll', 'Anti PLL'),
}


def build(subset, page):
    source_page, expected, stem, mask = SUBSETS[subset]
    source = 'https://speedcubedb.com/a/3x3/' + source_page
    entries = parse(page)
    bodies = re.split(r'<div class="row singlealgorithm[^>]*data-alg="[^"]+"[^>]*>', page)[1:]
    assert len(entries) == expected, (subset, len(entries))
    directory = ROOT / 'src/static/cases' / stem
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for entry, body in zip(entries, bodies):
        name = entry['source_name'].strip()
        algorithms = entry['source_algorithms']
        selected = 1 if subset == 'SV' and name == 'SV 7' else 0
        algorithm = normalize(algorithms[selected])
        svg, target, stickers = diagram(algorithm, mask)
        slug = name.lower().replace(' ', '-')
        extra = {}
        if subset == 'SV':
            number = int(name.removeprefix('SV '))
            slug, name = str(number), 'SV'+str(number)
            corners = sum(target[index] == 'U' for index in (0, 2, 6, 8))
            category = str(corners)+(' Corner' if corners == 1 else ' Corners')
            extra = {'source_number': number, 'selected_algorithm': selected+1}
        elif subset in ('COLL', 'CMLL'):
            category = html.unescape(re.search(r'data-filter="([^"]+)"', body).group(1))
        elif subset == 'LSE':
            category = 'EO4A'
        else:
            category = name[0] if name != 'Pure' else 'Pure'
        (directory / (slug+'.svg')).write_text(svg)
        cases.append({'name': name, 'alg_set': subset, 'category': category,
                      'algorithm': algorithm, 'source_algorithms': algorithms,
                      'alternatives': [alg for i, alg in enumerate(algorithms) if i != selected],
                      'source_setup': entry['source_setup'], 'source': source,
                      'facelets': target, 'stickers': stickers,
                      'image': '/cases/'+stem+'/'+slug+'.svg', **extra})
    assert len({case['name'] for case in cases}) == expected
    (ROOT / 'src/data' / (stem+'_algorithms.json')).write_text(
        json.dumps({'source': source, 'cases': cases}, indent=2)+'\n')
    print(f'Bundled {len(cases)} {subset} cases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('subset', choices=SUBSETS)
    parser.add_argument('--page', type=Path, required=True)
    args = parser.parse_args()
    build(args.subset, args.page.read_text())
