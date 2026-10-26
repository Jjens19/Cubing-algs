import json
from pathlib import Path
import tempfile
import unittest

from src import server
from src.scrambler import Cube, FACES, generate


class COLLTests(unittest.TestCase):
    def test_cases_preserve_edges_and_solve_corners(self):
        cases = json.loads((server.ROOT / 'src/data/coll_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 40)
        self.assertEqual(len({c['name'] for c in cases}), 40)
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['algorithm'], case['source_algorithms'][0])
                state = Cube().apply(case['source_setup']).apply(case['algorithm'])
                candidates = [Cube(''.join(state.facelets)).apply(auf).normalized()
                              for auf in ('', 'U', 'U2', "U'")]
                def solved_corners_and_f2l(s):
                    return all(s[i*9+j] == face for i, face in enumerate(FACES)
                               for j in ((0, 2, 6, 8) if face == 'U' else range(9) if face == 'D' else (0, 2, 3, 4, 5, 6, 7, 8))) and all(s[j] == 'U' for j in (1, 3, 5, 7))
                self.assertTrue(any(map(solved_corners_and_f2l, candidates)))
                self.assertEqual(len(case['stickers']), 21)
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
        # Exercise the same scramble generator used by practice on a COLL case.
        self.assertTrue(generate(cases[0]['algorithm']))

    def test_import_preserves_user_edits(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("UPDATE cases SET algorithm='R', learned=1, recognition='My notes' WHERE alg_set='COLL' AND name='AS 1'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM cases WHERE alg_set='COLL'").fetchone()[0], 40)
                    self.assertEqual(tuple(db.execute("SELECT algorithm, learned, recognition FROM cases WHERE alg_set='COLL' AND name='AS 1'").fetchone()), ('R', 1, 'My notes'))
            finally:
                server.DB = previous
