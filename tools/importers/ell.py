"""Match SpeedCubeDB ELL alternatives by full cube state, including AUF."""
import argparse
import json
from pathlib import Path

from tools.importers.common import parse
from tools.importers.common import ROOT, normalize
from src.scrambler import Cube, SOLVED, invert

SOURCE = 'https://speedcubedb.com/a/3x3/ELL'
AUFS = ('', 'U', "U'", 'U2')


def align(facelets, algorithm):
    for before in AUFS:
        state = Cube(facelets).apply(before).apply(algorithm)
        for after in AUFS:
            if Cube(''.join(state.facelets)).apply(after).normalized() == SOLVED:
                return ' '.join(part for part in (before, algorithm, after) if part)
    return None


def build(page):
    source = parse(page)
    original = json.loads((ROOT / 'src/data/ell_algorithms.json').read_text())['cases']
    assert len(source) == 25
    cases, used = [], set()
    for filename, case in original.items():
        if filename.startswith('ell-epll'):
            continue
        state = Cube().apply(invert(normalize(case['source_algorithm']))).normalized()
        matches = [entry for entry in source if align(state, entry['algorithm']) is not None]
        assert len(matches) == 1, (filename, matches)
        entry = matches[0]
        assert entry['source_name'] not in used
        used.add(entry['source_name'])
        alternatives = []
        for raw in entry['source_algorithms']:
            algorithm = normalize(raw)
            # Verify the website's own setup independently of the case match.
            assert align(Cube().apply(entry['source_setup']).normalized(), algorithm) is not None, (filename, raw)
            aligned = align(state, algorithm)
            assert aligned is not None, (filename, raw)
            if aligned not in alternatives:
                alternatives.append(aligned)
        cases.append({'image': '/cases/ell/'+filename, 'name': Path(filename).stem.removeprefix('ell-').upper(),
                      'source_name': entry['source_name'].strip(), 'source': SOURCE,
                      'source_setup': entry['source_setup'], 'source_algorithms': entry['source_algorithms'],
                      'facelets': state, 'alternatives': alternatives})
    assert len(used) == 25
    (ROOT / 'src/data/ell_alternatives.json').write_text(json.dumps({'source': SOURCE, 'cases': cases}, indent=2)+'\n')
    print('Matched 25 ELL cases;', sum(len(c['alternatives']) for c in cases), 'alternatives.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', type=Path, required=True)
    build(parser.parse_args().page.read_text())
