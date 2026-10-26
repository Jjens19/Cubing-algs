import json
from pathlib import Path
import tempfile
import unittest

from src import server
from src.scrambler import Cube, FACES


class SVTests(unittest.TestCase):
    def test_selection_and_solutions_match_source_setups(self):
        cases = json.loads((server.ROOT / 'src/data/sv_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 27)
        self.assertEqual({c['source_number'] for c in cases}, set(range(1, 28)))
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['selected_algorithm'], 2 if case['name'] == 'SV7' else 1)
                solved = Cube().apply(case['source_setup']).apply(case['algorithm']).normalized()
                self.assertEqual(solved[:9], 'U'*9)
                for i, face in enumerate(FACES):
                    if face == 'U':
                        continue
                    start = 0 if face == 'D' else 3
                    self.assertEqual(solved[i*9+start:(i+1)*9], face*(9-start))
                self.assertEqual(len(case['stickers']), 21)
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
        sv7 = next(c for c in cases if c['name'] == 'SV7')
        self.assertEqual(sv7['algorithm'], "R U R'")
        self.assertEqual(sv7['source_algorithms'][1], sv7['algorithm'])

    def test_import_preserves_edits_on_restart(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT algorithm FROM cases WHERE alg_set='SV' AND name='SV7'").fetchone()[0], "R U R'")
                    db.execute("UPDATE cases SET recognition='My notes', learning=1 WHERE alg_set='SV' AND name='SV7'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM cases WHERE alg_set='SV'").fetchone()[0], 27)
                    self.assertEqual(tuple(db.execute("SELECT recognition, learning FROM cases WHERE alg_set='SV' AND name='SV7'").fetchone()), ('My notes', 1))
            finally:
                server.DB = previous
