import json

from src import server
from src.scrambler import Cube, SOLVED, generate
from tools.importers.common import stage_solved
from test_security import LocalApp


class AntiPLLTests(LocalApp):
    def test_source_cases_diagrams_and_practice(self):
        cases = json.loads((server.ROOT / 'src/data/antipll_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 22)
        self.assertEqual(len({c['name'] for c in cases}), 22)
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['algorithm'], case['source_algorithms'][0])
                self.assertTrue(stage_solved(Cube().apply(case['source_setup']).apply(case['algorithm']).normalized(), 'PLL'))
                self.assertEqual(Cube(case['facelets']).apply(case['algorithm']).normalized(), SOLVED)
                self.assertTrue(all(case['facelets'][i] in 'RFLB' for i in (1, 3, 5, 7)))
                self.assertEqual(len(case['stickers']), 21)
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
                self.assertTrue(generate(case['algorithm']))

    def test_one_shared_set_preserves_edits_on_restart(self):
        _, _, library = self.request('/api/library')
        cases = [c for c in library['cases'] if c['alg_set'] == 'Anti PLL']
        self.assertEqual(len(cases), 22)
        case = cases[0]
        case.update(algorithm='R3', recognition='Shared notes', description='My description', learned=1)
        self.assertEqual(self.request('/api/case', case)[0], 200)
        server.initialize()
        _, _, library = self.request('/api/library')
        self.assertEqual(library['sets'].count('Anti PLL'), 1)
        cases = [c for c in library['cases'] if c['alg_set'] == 'Anti PLL']
        self.assertEqual(len(cases), 22)
        saved = next(c for c in cases if c['id'] == case['id'])
        self.assertEqual((saved['algorithm'], saved['recognition'], saved['description'], saved['learned']), ('R3', 'Shared notes', 'My description', 1))
