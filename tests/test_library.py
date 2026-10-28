import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from http.server import HTTPServer
from src import server


class LibraryTests(unittest.TestCase):
    def test_y_to_u(self):
        self.assertEqual(server.y_to_u("y R y' M y2 U y2'"), "U R U' M U2 U U2")
        self.assertEqual(server.y_to_u("(y') R U R'"), "U' R U R'")
        self.assertEqual(server.y_to_u("Rw x z M2"), "Rw x z M2")

    def test_ell_import_and_preserve_edits(self):
        bundled = json.loads((server.ROOT / 'src' / 'data' / 'ell_algorithms.json').read_text())['cases']
        defaults = {case['image'].split('/')[-1]: case['alternatives'][0] for case in
                    json.loads((server.ROOT / 'src/data/ell_alternatives.json').read_text())['cases']}
        self.assertEqual(set(bundled), {p.name for p in (server.ROOT / 'src/static/cases/ell').glob('*.svg')})
        self.assertEqual(len(bundled), 30)
        self.assertEqual(bundled['ell-A3.svg']['algorithm'], "U M' U' M U2 M' U' M")
        self.assertEqual(bundled['ell-epll0.svg']['algorithm'], '')
        for case in bundled.values():
            server.inverse(case['algorithm'])
        original = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    rows = db.execute('SELECT image, algorithm FROM cases WHERE alg_set="ELL"').fetchall()
                    for row in rows:
                        filename = row['image'].split('/')[-1]
                        self.assertEqual(row['algorithm'], defaults.get(filename, bundled[filename]['algorithm']))
                    # Simulate an existing library before this migration.
                    db.execute('DELETE FROM migrations')
                    db.execute("UPDATE cases SET algorithm='' WHERE image='/cases/ell/ell-A1.svg'")
                    db.execute("UPDATE cases SET algorithm='R U' WHERE image='/cases/ell/ell-A2.svg'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT algorithm FROM cases WHERE image='/cases/ell/ell-A1.svg'").fetchone()[0], defaults['ell-A1.svg'])
                    self.assertEqual(db.execute("SELECT algorithm FROM cases WHERE image='/cases/ell/ell-A2.svg'").fetchone()[0], 'R U')
                    db.execute("UPDATE cases SET algorithm='' WHERE image='/cases/ell/ell-A1.svg'")
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT algorithm FROM cases WHERE image='/cases/ell/ell-A1.svg'").fetchone()[0], '')
            finally:
                server.DB = original

    def test_inverse(self):
        self.assertEqual(server.inverse("R U R' U'"), "U R U' R'")
        self.assertEqual(server.inverse("y Rw2 M' r U2'"), "U2 r' M Rw2 y'")
        self.assertEqual(server.inverse(''), '')
        self.assertEqual(server.inverse("R3 U3' Rw3"), "Rw U' R")
        for invalid in ['(R U)3', '[R,U]', 'R4', 'RUR', 'hello']:
            with self.assertRaises(ValueError):
                server.inverse(invalid)

    def test_library_roundtrip(self):
        original = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                server.initialize()
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM cases WHERE alg_set='ELL'").fetchone()[0], 30)
                    self.assertEqual(db.execute('SELECT sum(learned) FROM cases').fetchone()[0], 0)
                http = HTTPServer(('127.0.0.1', 0), server.Handler)
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{http.server_port}'
                def post(path, data):
                    request = Request(base + '/api/' + path, json.dumps(data).encode(), {'Content-Type': 'application/json'})
                    with urlopen(request) as response:
                        return json.load(response)
                try:
                    post('sets', {'name': 'PLL'})
                    case = {'name': 'Practice', 'alg_set': 'PLL', 'category': 'Test / Bars / Opposite', 'algorithm': "R U R'", 'recognition': 'Look for a bar', 'drawing': json.dumps({'useDrawing': True, 'stickers': {'U0': {'color': '#fafafa', 'highlight': True}}})}
                    case['id'] = post('case', case)['id']
                    case['description'] = 'Updated description'
                    case['learned'] = True
                    post('case', case)
                    with urlopen(base + '/api/library') as response:
                        library = json.load(response)
                    self.assertIn('learning', library['progress_states'])
                    stored = next(c for c in library['cases'] if c['id'] == case['id'])
                    self.assertEqual(stored['description'], 'Updated description')
                    self.assertEqual(stored['recognition'], case['recognition'])
                    self.assertEqual(stored['category'], 'Test / Bars / Opposite')
                    self.assertEqual(stored['drawing'], case['drawing'])
                    self.assertEqual(stored['learned'], 1)
                    post('progress', {'id': case['id'], 'learned': True})
                    other = {**case, 'name': 'Another case', 'learned': False}
                    del other['id']
                    other['id'] = post('case', other)['id']
                    other['description'] = 'Edit another case'
                    post('case', other)
                    # Clients omitting progress must preserve it on detail saves.
                    without_progress = dict(case)
                    del without_progress['learned']
                    post('case', without_progress)
                    with urlopen(base + '/api/library') as response:
                        reloaded = json.load(response)
                    self.assertEqual(next(c for c in reloaded['cases'] if c['id'] == case['id'])['learned'], 1)
                    server.initialize()
                    with server.connect() as db:
                        self.assertEqual(db.execute('SELECT learned FROM cases WHERE id=?', (case['id'],)).fetchone()[0], 1)
                    post('progress', {'id': case['id'], 'learned': False})
                    with urlopen(base + '/api/export') as response:
                        exported = json.load(response)
                    exported_case = next(c for c in exported['cases'] if c['id'] == case['id'])
                    self.assertEqual(exported_case['learned'], 0)
                    self.assertEqual(exported_case['description'], 'Updated description')
                    self.assertEqual(exported_case['algorithm'], case['algorithm'])
                    post('progress', {'id': case['id'], 'state': 'learning'})
                    self.assertFalse(post('practice-result', {'id': case['id'], 'elapsed_ms': 3000})['promoted'])
                    with server.connect() as db:
                        learning = db.execute('SELECT learned, learning FROM cases WHERE id=?', (case['id'],)).fetchone()
                        self.assertEqual(tuple(learning), (0, 1))
                    self.assertTrue(post('practice-result', {'id': case['id'], 'elapsed_ms': 2999})['promoted'])
                    server.initialize()
                    with server.connect() as db:
                        promoted = db.execute('SELECT learned, learning FROM cases WHERE id=?', (case['id'],)).fetchone()
                        self.assertEqual(tuple(promoted), (1, 0))
                    # DNF overrides even a freshly auto-promoted solve.
                    post('progress', {'id': case['id'], 'state': 'learning'})
                    server.initialize()
                    with server.connect() as db:
                        self.assertEqual(tuple(db.execute('SELECT learned, learning FROM cases WHERE id=?', (case['id'],)).fetchone()), (0, 1))
                        self.assertEqual(tuple(db.execute('SELECT learned, learning FROM cases WHERE id=?', (other['id'],)).fetchone()), (0, 0))
                    post('progress', {'id': case['id'], 'state': 'not-learned'})
                    self.assertFalse(post('practice-result', {'id': case['id'], 'elapsed_ms': 1000})['promoted'])
                    self.assertIn('PLL', library['sets'])
                    self.assertEqual(post('inverse', {'algorithm': case['algorithm']})['setup'], "R U' R'")
                    for path in ['/', '/app.js', '/style.css', '/cases/ell/ell-A1.svg', '/ELL/ell-A1.svg', '/api/export']:
                        with urlopen(base + path) as response:
                            self.assertEqual(response.status, 200)
                finally:
                    http.shutdown()
                    http.server_close()
                    thread.join()
            finally:
                server.DB = original


if __name__ == '__main__':
    unittest.main()
