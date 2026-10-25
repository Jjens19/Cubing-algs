"""Bundle SV from a downloaded SpeedCubeDB Summer Variation HTML page."""
import argparse
import html
import json
from pathlib import Path
import re

from scripts.import_jperm import ROOT, diagram, normalize

SOURCE = 'https://speedcubedb.com/a/3x3/SV'


def build(page):
    parts = re.split(r'<div class="row singlealgorithm[^>]*data-alg="SV (\d+)"[^>]*>', page)
    cases = []
    directory = ROOT / 'src/static/cases/sv'
    directory.mkdir(parents=True, exist_ok=True)
    for number, body in zip(parts[1::2], parts[2::2]):
        algorithms = [html.unescape(re.sub('<[^>]*>', '', text)).strip()
                      for text in re.findall(r'<div class="formatted-alg">(.*?)</div>', body, re.S)]
        setup = html.unescape(re.search(r'<div class="setup-case[^>]*><div>setup:</div>(.*?)</div>', body, re.S).group(1)).strip()
        selected = 1 if number == '7' else 0
        algorithm = normalize(algorithms[selected])
        svg, target, stickers = diagram(algorithm, 'WV')
        (directory / (number+'.svg')).write_text(svg)
        corners = sum(target[index] == 'U' for index in [0, 2, 6, 8])
        cases.append({'name': 'SV'+number, 'alg_set': 'SV', 'source_number': int(number),
                      'category': str(corners)+(' Corner' if corners == 1 else ' Corners'),
                      'algorithm': algorithm, 'source_algorithms': algorithms,
                      'selected_algorithm': selected+1,
                      'alternatives': [alg for i, alg in enumerate(algorithms) if i != selected],
                      'source_setup': setup, 'source': SOURCE,
                      'facelets': target, 'stickers': stickers, 'image': '/cases/sv/'+number+'.svg'})
    assert len(cases) == 27
    assert {case['source_number'] for case in cases} == set(range(1, 28))
    (ROOT / 'src/sv_algorithms.json').write_text(json.dumps({'source': SOURCE, 'cases': cases}, indent=2)+'\n')
    print('Bundled 27 SV cases. SV7:', next(c['algorithm'] for c in cases if c['name'] == 'SV7'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, required=True)
    build(parser.parse_args().page.read_text())
