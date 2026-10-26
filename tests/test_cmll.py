import json
from pathlib import Path
import tempfile
import unittest

from src import server
from src.scrambler import Cube, GEOMETRY, SOLVED, generate


class CMLLTests(unittest.TestCase):
    def test_source_cases_solve_corners_and_preserve_blocks(self):
        cases = json.loads((server.ROOT / 'src/data/cmll_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 42)
        self.assertEqual(len({c['name'] for c in cases}), 42)
        indices = [i for i, (p, _) in enumerate(GEOMETRY)
                   if sum(abs(a) for a in p) == 3 or (abs(p[0]) == 1 and p[1] <= 0)]
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['algorithm'], case['source_algorithms'][0])
                state = Cube().apply(case['source_setup']).apply(case['algorithm'])
                # Align the free M slice centers and final U face before comparison.
                candidates = [Cube(''.join(state.facelets)).apply(m).apply(u).normalized()
                              for m in ('', 'M', "M'", 'M2') for u in ('', 'U', "U'", 'U2')]
                self.assertTrue(any(all(s[i] == SOLVED[i] for i in indices) for s in candidates))
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
                self.assertEqual(len(case['stickers']), 54)
                for key in ('U1', 'U3', 'U5', 'U7'):
                    self.assertEqual(case['stickers'][key]['color'], '#aab2a7')
        self.assertTrue(generate(cases[0]['algorithm']))

    def test_import_preserves_edits(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    self.assertIsNotNone(db.execute("SELECT name FROM sets WHERE name='LSE'").fetchone())
                    db.execute("UPDATE cases SET recognition='My notes', algorithm='R3', learning=1 WHERE alg_set='CMLL' AND name='O Adjacent'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM cases WHERE alg_set='CMLL'").fetchone()[0], 42)
                    self.assertEqual(tuple(db.execute("SELECT recognition, algorithm, learning FROM cases WHERE alg_set='CMLL' AND name='O Adjacent'").fetchone()), ('My notes', 'R3', 1))
            finally:
                server.DB = previous
