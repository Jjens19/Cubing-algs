import json
from pathlib import Path
import tempfile
import unittest

from src import server
from src.scrambler import Cube, SOLVED, invert
from tools.importers.common import normalize
from tools.importers.ell import align


class ELLAlternativeTests(unittest.TestCase):
    def test_defaults_upgrade_once_and_preserve_custom_algorithms(self):
        previous = server.DB
        bundled = json.loads((server.ROOT / 'src/data/ell_alternatives.json').read_text())['cases']
        original = json.loads((server.ROOT / 'src/data/ell_algorithms.json').read_text())['cases']
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("DELETE FROM migrations WHERE name='speedcubedb-ell-defaults-v1'")
                    for case in bundled:
                        db.execute('UPDATE cases SET algorithm=? WHERE image=?',
                                   (original[Path(case['image']).name]['algorithm'], case['image']))
                    db.execute("UPDATE cases SET algorithm='R U', description='My notes' WHERE image='/cases/ell/ell-A2.svg'")
                server.initialize()
                with server.connect() as db:
                    for case in bundled:
                        row = db.execute('SELECT algorithm, description FROM cases WHERE image=?', (case['image'],)).fetchone()
                        if case['name'] == 'A2':
                            self.assertEqual(tuple(row), ('R U', 'My notes'))
                        else:
                            self.assertEqual(row['algorithm'], align(case['facelets'], normalize(case['source_algorithms'][0])))
                            self.assertIn('Default algorithm: SpeedCubeDB', row['description'])
                    db.execute("UPDATE cases SET algorithm='' WHERE image='/cases/ell/ell-A1.svg'")
                    before = [dict(row) for row in db.execute('SELECT * FROM cases')]
                server.initialize()
                with server.connect() as db:
                    self.assertEqual([dict(row) for row in db.execute('SELECT * FROM cases')], before)
            finally:
                server.DB = previous

    def test_every_alternative_solves_the_matched_case(self):
        bundled = json.loads((server.ROOT / 'src/data/ell_alternatives.json').read_text())['cases']
        original = json.loads((server.ROOT / 'src/data/ell_algorithms.json').read_text())['cases']
        self.assertEqual(len(bundled), 25)
        self.assertEqual(len({c['source_name'] for c in bundled}), 25)
        self.assertEqual(len({c['image'] for c in bundled}), 25)
        self.assertEqual(sum(len(c['alternatives']) for c in bundled), 99)
        for case in bundled:
            with self.subTest(case=case['name']):
                expected = Cube().apply(invert(normalize(original[Path(case['image']).name]['source_algorithm']))).normalized()
                self.assertEqual(case['facelets'], expected)
                self.assertTrue((server.ROOT / 'src/static' / case['image'].lstrip('/')).exists())
                for algorithm in case['alternatives']:
                    self.assertEqual(Cube(expected).apply(algorithm).normalized(), SOLVED)
                for algorithm in case['source_algorithms']:
                    self.assertIsNotNone(align(Cube().apply(case['source_setup']).normalized(), normalize(algorithm)))

    def test_migration_preserves_main_and_edits_and_runs_once(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("DELETE FROM migrations WHERE name='speedcubedb-ell-alternatives-v1'")
                    db.execute("UPDATE cases SET name='Renamed', alg_set='Custom', category='My category', algorithm='R3', description='My notes', recognition='My recognition', drawing='{}', learned=1 WHERE image='/cases/ell/ell-A1.svg'")
                    before = dict(db.execute("SELECT * FROM cases WHERE image='/cases/ell/ell-A1.svg'").fetchone())
                    untouched = [dict(r) for r in db.execute("SELECT * FROM cases WHERE image LIKE '/cases/ell/ell-epll%'")]
                server.initialize()
                with server.connect() as db:
                    after = dict(db.execute('SELECT * FROM cases WHERE id=?', (before['id'],)).fetchone())
                    self.assertTrue(after['description'].startswith('My notes\n\nAlternative algorithms: SpeedCubeDB'))
                    self.assertIn('Pure Adj', after['description'])
                    description = after['description']
                    after['description'] = before['description']
                    self.assertEqual(after, before)
                    self.assertEqual([dict(r) for r in db.execute("SELECT * FROM cases WHERE image LIKE '/cases/ell/ell-epll%'")], untouched)
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute('SELECT description FROM cases WHERE id=?', (before['id'],)).fetchone()[0], description)
            finally:
                server.DB = previous
