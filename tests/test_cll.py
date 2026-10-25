from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src import server
from src.scrambler import Cube, FACES, invert


class CLLTests(unittest.TestCase):
    def test_case_algorithms_match_source_diagram_corners(self):
        cases = json.loads((server.ROOT / 'src/cll_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 42)
        self.assertEqual(Counter(c['category'] for c in cases),
                         {'PLL': 2, 'U': 6, 'T': 6, 'L': 6, 'S': 6, 'AS': 6, 'P': 6, 'H': 4})
        self.assertEqual(len({c['name'] for c in cases}), 42)
        for case in cases:
            with self.subTest(case=case['name']):
                state = Cube().apply(invert(case['algorithm'])).normalized()
                for key, expected in case['corner_facelets'].items():
                    self.assertEqual(state[FACES.index(key[0])*9+int(key[1])], expected)
                # Every alternate must solve the same corners, even if edges differ.
                for algorithm in [case['algorithm'], *case['alternatives']]:
                    server.inverse(algorithm)
                    solved = Cube(state).apply(algorithm).normalized()
                    for face in FACES:
                        for index in (0, 2, 6, 8):
                            self.assertEqual(solved[FACES.index(face)*9+index], face)
                image = server.ROOT / 'src/static' / case['image'].lstrip('/')
                svg = ET.parse(image).getroot()
                self.assertEqual(svg.get('viewBox'), '0 0 420 420')
                self.assertEqual((svg.get('width'), svg.get('height')), ('420', '420'))
                self.assertTrue(all(e.tag.split('}')[-1] in ('svg', 'path') for e in svg.iter()))

    def test_import_is_idempotent_and_preserves_edits(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM cases WHERE alg_set='CLL'").fetchone()[0], 42)
                    db.execute("UPDATE cases SET algorithm='R U', learned=1 WHERE alg_set='CLL' AND name='U1'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM cases').fetchone()[0], 204)
                    self.assertEqual(tuple(db.execute("SELECT algorithm, learned FROM cases WHERE alg_set='CLL' AND name='U1'").fetchone()), ('R U', 1))
            finally:
                server.DB = previous
