from collections import Counter
import json
from pathlib import Path
import random
import tempfile
import unittest

from src import server
from src.scrambler import Cube, FACES, SOLVED, generate, invert
from tools.importers.common import normalize


class JPermTests(unittest.TestCase):
    def test_normalization_preserves_ergonomic_triple_turns(self):
        self.assertEqual(normalize("(R3 U3') Rw3"), "R3 U3' Rw3")
        cases = json.loads((server.ROOT / 'src/data/jperm_algorithms.json').read_text())['cases']
        ub = next(c for c in cases if c['alg_set']=='PLL' and c['name']=='Ub')
        self.assertTrue(any('R3' in alternative for alternative in ub['alternatives']))

    def test_all_cases_and_stage_solutions(self):
        cases = json.loads((server.ROOT / 'src/data/jperm_algorithms.json').read_text())['cases']
        self.assertEqual(Counter(c['alg_set'] for c in cases), {'WV': 27, 'OLL': 57, 'PLL': 21})
        self.assertEqual(len({(c['alg_set'], c['name']) for c in cases}), 105)
        for case in cases:
            with self.subTest(subset=case['alg_set'], case=case['name']):
                state = case['facelets']
                self.assertEqual(Cube().apply(invert(case['algorithm'])).normalized(), state)
                self.assertEqual(len(case['stickers']), 21)
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).is_file())
                for solution in [case['algorithm']]:
                    solved = Cube(state).apply(normalize(solution)).normalized()
                    if case['alg_set'] == 'PLL':
                        # PLL may leave an AUF; a whole-layer U turn finishes it.
                        self.assertTrue(any(Cube(solved).apply(auf).normalized() == SOLVED for auf in ['', 'U', "U'", 'U2']))
                    else:
                        self.assertEqual(solved[:9], 'U'*9)
                        for i, face in enumerate(FACES):
                            if face == 'U':
                                continue
                            start = 0 if face == 'D' else 3
                            self.assertEqual(solved[i*9+start:(i+1)*9], face*(9-start))

    def test_import_preserves_existing_cases_and_is_idempotent(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("UPDATE cases SET algorithm='R U', learned=1 WHERE alg_set='OLL' AND name='OLL 1'")
                    db.execute("DELETE FROM migrations WHERE name='jperm-wv-oll-pll-v1'")
                server.initialize()
                server.initialize()
                with server.connect() as db:
                    for subset, count in [('WV', 27), ('OLL', 57), ('PLL', 21)]:
                        self.assertEqual(db.execute('SELECT count(*) FROM cases WHERE alg_set=?', (subset,)).fetchone()[0], count)
                    self.assertEqual(tuple(db.execute("SELECT algorithm, learned FROM cases WHERE alg_set='OLL' AND name='OLL 1'").fetchone()), ('R U', 1))
            finally:
                server.DB = previous

    def test_practice_scrambles_reach_the_imported_cases(self):
        cases = json.loads((server.ROOT / 'src/data/jperm_algorithms.json').read_text())['cases']
        for case in cases:
            with self.subTest(subset=case['alg_set'], case=case['name']):
                expected = {Cube(case['facelets']).apply(auf).normalized() for auf in ['', 'U', "U'", 'U2']}
                scramble = generate(case['algorithm'], random.Random(case['source_index']))
                self.assertIn(Cube().apply(scramble).normalized(), expected)
