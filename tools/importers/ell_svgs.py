"""Regenerate ELL diagrams from the preserved original sticker-color samples."""
import json
from tools.importers.common import ROOT, render_diagram


def generate():
    cases = json.loads((ROOT / 'src/data/ell_stickers.json').read_text())
    directory = ROOT / 'src/static/cases/ell'
    directory.mkdir(parents=True, exist_ok=True)
    for filename, stickers in cases.items():
        (directory / filename).write_text(render_diagram(stickers, data_keys=True))
    print(f'Generated {len(cases)} ELL SVGs.')


if __name__ == '__main__':
    generate()
