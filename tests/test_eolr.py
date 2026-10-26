import json
import random

from src import server
from src.scrambler import Cube, generate
from tools.importers.eolr import goal
from test_security import LocalApp


class EOLRTests(LocalApp):
    def test_source_diagrams_setups_and_practice(self):
        cases = json.loads((server.ROOT / 'src/data/eolr_algorithms.json').read_text())['cases']
        self.assertEqual(len(cases), 46)
        self.assertEqual(len({c['name'] for c in cases}), 46)
        for case in cases:
            with self.subTest(case=case['name']):
                state = ''.join(Cube().apply(case['setup']).facelets)
                self.assertEqual(state, case['facelets'])
                for index, color in case['source_stickers'].items():
                    self.assertEqual(state[int(index)], color)
                self.assertTrue(goal(Cube(state).apply(case['algorithm']).facelets))
                scramble = generate(case['algorithm'], rng=random.Random(5), facelets=state)
                reached = ''.join(Cube().apply(scramble).facelets)
                family = [''.join(Cube(state).apply(auf).facelets) for auf in ('', 'U', "U'", 'U2')]
                self.assertIn(reached, family)
                self.assertEqual(len(case['stickers']), 54)

    def test_api_uses_case_setup_and_preserves_edits(self):
        _, _, library = self.request('/api/library')
        case = next(c for c in library['cases'] if c['image'] == '/cases/lse/eolr/1.svg')
        self.assertEqual(len([c for c in library['cases'] if c['alg_set'] == 'EOLR']), 46)
        code, _, response = self.request('/api/inverse', {'id': case['id'], 'algorithm': case['algorithm']})
        self.assertEqual(code, 200)
        self.assertTrue(goal(Cube().apply(response['setup']).apply(case['algorithm']).facelets))
        code, _, response = self.request('/api/practice-scramble', {'id': case['id'], 'algorithm': case['algorithm']})
        self.assertEqual(code, 200)
        self.assertTrue(response['setup'])
        _, _, edited = self.request('/api/inverse', {'id': case['id'], 'algorithm': 'R3'})
        self.assertEqual(edited['setup'], 'R')
        with server.connect() as db:
            db.execute('UPDATE cases SET algorithm=?, recognition=?, learned=1 WHERE id=?', ('R3', 'My notes', case['id']))
        server.initialize()
        with server.connect() as db:
            self.assertEqual(tuple(db.execute('SELECT algorithm, recognition, learned FROM cases WHERE id=?', (case['id'],)).fetchone()), ('R3', 'My notes', 1))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM cases WHERE alg_set='EOLR'").fetchone()[0], 46)

    def test_move_to_advanced_set_preserves_custom_case_data(self):
        with server.connect() as db:
            db.execute("DELETE FROM migrations WHERE name='method-advanced-subsets-v1'")
            db.execute("UPDATE cases SET alg_set='LSE', category='My grouping', recognition='My notes', learned=1, algorithm='M' WHERE image='/cases/lse/eolr/1.svg'")
            before = dict(db.execute("SELECT * FROM cases WHERE image='/cases/lse/eolr/1.svg'").fetchone())
        server.initialize()
        server.initialize()
        with server.connect() as db:
            after = dict(db.execute('SELECT * FROM cases WHERE id=?', (before['id'],)).fetchone())
            self.assertEqual(db.execute("SELECT COUNT(*) FROM cases WHERE alg_set='EOLR'").fetchone()[0], 46)
        before['alg_set'] = 'EOLR'
        self.assertEqual(after, before)
