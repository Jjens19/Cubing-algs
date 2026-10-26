import json
from pathlib import Path
import tempfile
import unittest

from src import server
from src.scrambler import Cube, GEOMETRY, SOLVED, generate, invert


class LSETests(unittest.TestCase):
    def test_eo4a_solutions_and_practice(self):
        cases = json.loads((server.ROOT / 'src/data/lse_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 9)
        self.assertEqual(len({c['name'] for c in cases}), 9)
        fixed = [i for i, (p, _) in enumerate(GEOMETRY)
                 if sum(abs(a) for a in p) == 3 or (abs(p[0]) == 1 and p[1] <= 0)]
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['algorithm'], case['source_algorithms'][0])
                self.assertEqual(case['category'], 'EO4A')
                state = Cube().apply(case['source_setup']).apply(case['algorithm'])
                candidates = [Cube(''.join(state.facelets)).apply(m).apply(u).normalized()
                              for m in ('', 'M', "M'", 'M2') for u in ('', 'U', "U'", 'U2')]
                self.assertTrue(any(all(s[i] == SOLVED[i] for i in fixed) and
                                    all(s[i] in 'UD' for i in (1, 3, 5, 7, 28, 34))
                                    for s in candidates))
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
                self.assertEqual(case['facelets'], Cube().apply(invert(case['algorithm'])).normalized())
                self.assertEqual(len(case['stickers']), 54)
                self.assertTrue(generate(case['algorithm']))

    def test_import_preserves_edits_and_does_not_duplicate(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("UPDATE cases SET algorithm='M', recognition='My notes', learned=1 WHERE alg_set='LSE' AND name='All 6'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM cases WHERE alg_set='LSE'").fetchone()[0], 9)
                    self.assertEqual(tuple(db.execute("SELECT algorithm, recognition, learned FROM cases WHERE alg_set='LSE' AND name='All 6'").fetchone()), ('M', 'My notes', 1))
            finally:
                server.DB = previous
