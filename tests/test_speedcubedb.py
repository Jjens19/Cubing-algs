import json
from pathlib import Path
import tempfile
import unittest

from tools.importers.common import match_pose, stage_solved
from src import server
from src.scrambler import Cube


class SpeedCubeDBTests(unittest.TestCase):
    def test_source_case_matches_and_solutions(self):
        cases = json.loads((server.ROOT / 'src/data/speedcubedb_overrides.json').read_text())['cases']
        self.assertEqual(len(cases), 105)
        self.assertEqual(len({(c['alg_set'], c['source_name']) for c in cases}), 105)
        for case in cases:
            with self.subTest(subset=case['alg_set'], case=case['name']):
                self.assertIsNotNone(match_pose(case['previous_facelets'], case['algorithm'], case['alg_set']))
                result = Cube().apply(case['source_setup']).apply(case['algorithm']).normalized()
                self.assertTrue(stage_solved(result, case['alg_set']))
        wv = {c['name']: c['source_name'] for c in cases if c['alg_set'] == 'WV'}
        self.assertEqual(wv['WV 17 — Adjacent'], 'WV 18')
        self.assertEqual(wv['WV 21 — Sune'], 'WV 27')

    def test_migration_updates_main_only_and_runs_once(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("DELETE FROM migrations WHERE name='speedcubedb-primary-algorithms-v1'")
                    db.execute("UPDATE cases SET algorithm='R3 U', name='My renamed case', category='Custom / Notes', description='My description', recognition='My recognition', drawing='{}', learned=1 WHERE image='/cases/wv/21.svg'")
                    before = {r['id']: dict(r) for r in db.execute('SELECT * FROM cases')}
                server.initialize()
                source = json.loads((server.ROOT / 'src/data/speedcubedb_overrides.json').read_text())['cases']
                expected = {c['image']: c for c in source}
                with server.connect() as db:
                    rows = db.execute('SELECT * FROM cases').fetchall()
                    for row in rows:
                        old = before[row['id']]
                        if row['image'] in expected:
                            self.assertEqual(row['algorithm'], expected[row['image']]['algorithm'])
                            self.assertTrue(row['description'].startswith(old['description']))
                            for field in ['name', 'category', 'recognition', 'drawing', 'learned', 'learning']:
                                self.assertEqual(row[field], old[field])
                        else:
                            self.assertEqual(dict(row), old)
                    wv21 = db.execute("SELECT * FROM cases WHERE image='/cases/wv/21.svg'").fetchone()
                    self.assertIn('SpeedCubeDB WV 27', wv21['description'])
                    self.assertIn('Previous main algorithm: R3 U', wv21['description'])
                    db.execute("UPDATE cases SET algorithm='R3 U' WHERE id=?", (wv21['id'],))
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute('SELECT algorithm FROM cases WHERE id=?', (wv21['id'],)).fetchone()[0], 'R3 U')
            finally:
                server.DB = previous
