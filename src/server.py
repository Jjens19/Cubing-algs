import argparse
import json
import math
import re
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from src.scrambler import generate as generate_practice_scramble
from src.tnoodle import generate as generate_timer_scramble

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'data' / 'library.sqlite3'
MOVE = re.compile(r"(?:[URFDLB]w?|[urfdlbMESxyz])(?:[23]'?|')?")


def y_to_u(algorithm):
    replacements = {'y': 'U', "y'": "U'", 'y2': 'U2', "y2'": 'U2'}
    return re.sub(r"\((y(?:2'?|')?)\)|(?<!\w)(y(?:2'?|')?)(?![\w'])",
                  lambda match: replacements[match[1] or match[2]], algorithm)


def inverse(algorithm):
    """Invert ordinary move notation; reject ambiguous shorthand."""
    text = algorithm.replace('’', "'").strip()
    tokens = text.split()
    if any(not MOVE.fullmatch(token) for token in tokens):
        raise ValueError("Use space-separated moves such as R U R' U', M2, R3, Rw or y. Expand parentheses, commutators and repetitions first.")
    def inverted_move(token):
        if token.endswith("3'"):
            return token[:-2] + "'"
        if token.endswith('3'):
            return token[:-1]
        return token[:-1] if token.endswith("2'") else token if token.endswith('2') else token[:-1] if token.endswith("'") else token + "'"
    return ' '.join(inverted_move(token) for token in reversed(tokens))


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def eolr_reference(data):
    if not data.get('id'):
        return None
    with connect() as db:
        row = db.execute('SELECT image FROM cases WHERE id=?', (data['id'],)).fetchone()
    if not row or not row['image'].startswith('/cases/lse/eolr/'):
        return None
    cases = json.loads((ROOT / 'src/data/eolr_algorithms.json').read_text())['cases']
    return next((case for case in cases if case['image'] == row['image'] and case['algorithm'] == data.get('algorithm')), None)


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS sets (name TEXT PRIMARY KEY)')
        db.execute('CREATE TABLE IF NOT EXISTS cases (id INTEGER PRIMARY KEY, name TEXT NOT NULL, alg_set TEXT NOT NULL, category TEXT NOT NULL DEFAULT "", algorithm TEXT NOT NULL DEFAULT "", description TEXT NOT NULL DEFAULT "", recognition TEXT NOT NULL DEFAULT "", image TEXT NOT NULL DEFAULT "", drawing TEXT NOT NULL DEFAULT "{}")')
        db.executemany('INSERT OR IGNORE INTO sets VALUES (?)', [(name,) for name in ('ELL', 'OLL', 'PLL', 'WV', 'SV')])
        if 'learned' not in {row['name'] for row in db.execute('PRAGMA table_info(cases)')}:
            db.execute('ALTER TABLE cases ADD COLUMN learned INTEGER NOT NULL DEFAULT 0 CHECK (learned IN (0, 1))')
        if 'learning' not in {row['name'] for row in db.execute('PRAGMA table_info(cases)')}:
            db.execute('ALTER TABLE cases ADD COLUMN learning INTEGER NOT NULL DEFAULT 0 CHECK (learning IN (0, 1))')
        # Only seed once; later startup must not overwrite the user’s library.
        if not db.execute('SELECT 1 FROM cases LIMIT 1').fetchone():
            for path in sorted((ROOT / 'src/static/cases/ell').glob('*.svg')):
                name = path.stem.removeprefix('ell-')
                category = 'EPLL' if name.startswith('epll') else name[0]
                db.execute('INSERT INTO cases(name, alg_set, category, image) VALUES (?, ?, ?, ?)', (name.upper(), 'ELL', category, '/cases/ell/' + path.name))
        # Apply the bundled website import once to both existing and new libraries.
        # Tracking the migration also lets users clear an algorithm afterwards.
        db.execute('CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)')
        migration = 'ell-vector-images-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            for filename in json.loads((ROOT / 'src/data/ell_stickers.json').read_text()):
                old_image = '/ELL/' + Path(filename).with_suffix('.png').name
                db.execute('UPDATE cases SET image=? WHERE image=?', ('/cases/ell/' + filename, old_image))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))
        migration = 'ell-static-directory-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            for filename in json.loads((ROOT / 'src/data/ell_stickers.json').read_text()):
                for legacy in (filename, Path(filename).with_suffix('.png').name):
                    db.execute('UPDATE cases SET image=? WHERE image=?', ('/cases/ell/' + filename, '/ELL/' + legacy))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))
        migration = 'sarah-ell-algorithms-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src' / 'data' / 'ell_algorithms.json').read_text())
            for filename, case in bundled['cases'].items():
                db.execute("UPDATE cases SET algorithm=? WHERE alg_set='ELL' AND image=? AND trim(algorithm)=''",
                           (case['algorithm'], '/cases/ell/' + filename))
                if not case['algorithm']:
                    db.execute("UPDATE cases SET description=? WHERE alg_set='ELL' AND image=? AND trim(description)=''",
                               ('Solved / ELL skip: no moves are needed.', '/cases/ell/' + filename))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'cubepal-cll-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/cll_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('CLL',))
            for case in bundled['cases']:
                # Never replace an existing user's case with the same identity.
                if db.execute("SELECT 1 FROM cases WHERE alg_set='CLL' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source']
                if case['alternatives']:
                    description += '\n\nAlternative solutions from CubePal:\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'CLL', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))
        migration = 'algorithm-y-to-u-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            for row in db.execute('SELECT id, algorithm FROM cases').fetchall():
                converted = y_to_u(row['algorithm'])
                if converted != row['algorithm']:
                    db.execute('UPDATE cases SET algorithm=? WHERE id=?', (converted, row['id']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'jperm-wv-oll-pll-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/jperm_algorithms.json').read_text())
            for case in bundled['cases']:
                db.execute('INSERT OR IGNORE INTO sets VALUES (?)', (case['alg_set'],))
                if db.execute('SELECT 1 FROM cases WHERE alg_set=? AND (name=? OR image=?)',
                              (case['alg_set'], case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source']
                if case['alg_set'] == 'WV':
                    description += "\nWinter Variation: start with the top cross oriented and the final F2L pair ready for R U' R' insertion."
                if case['alternatives']:
                    description += '\n\nAlternative solutions from J Perm (as listed; may need a different setup or orientation):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], case['alg_set'], case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-sv-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/sv_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('SV',))
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='SV' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source']
                if case['name'] == 'SV7':
                    description += '\nUses the second listed algorithm, as requested.'
                if case['alternatives']:
                    description += '\n\nAlternative solutions from SpeedCubeDB (as listed):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'SV', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-ell-alternatives-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/ell_alternatives.json').read_text())
            for case in bundled['cases']:
                # Match by image so renamed or recategorized cases retain their alternatives.
                for row in db.execute('SELECT id, algorithm, description FROM cases WHERE image=?', (case['image'],)).fetchall():
                    alternatives = [alg for alg in case['alternatives'] if alg != row['algorithm']]
                    if not alternatives:
                        continue
                    note = '\n\nAlternative algorithms: SpeedCubeDB ' + case['source_name'] + '\n' + case['source']
                    note += '\nU adjustments are included for this case orientation; keep any cube rotations as written.\n'
                    note += '\n'.join(alternatives)
                    db.execute('UPDATE cases SET description=? WHERE id=?', (row['description'] + note, row['id']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-ell-defaults-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/ell_alternatives.json').read_text())
            previous = json.loads((ROOT / 'src/data/ell_algorithms.json').read_text())['cases']
            for case in bundled['cases']:
                old_algorithm = previous[Path(case['image']).name]['algorithm']
                note = f"\n\nDefault algorithm: SpeedCubeDB {case['source_name']}\n{case['source']}"
                db.execute('UPDATE cases SET algorithm=?, description=description || ? '
                           'WHERE image=? AND algorithm=?',
                           (case['alternatives'][0], note, case['image'], old_algorithm))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'cubingapp-lse-eolr-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/eolr_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('LSE',))
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='LSE' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source'] + '\nEOLR combines edge orientation and UL/UR placement. Finish the listed algorithm with UL and UR on the bottom, then insert them using M2. It is a stage solution, not a full-cube solution.'
                description += '\nThe positions in parentheses identify the starting positions of UL and UR. Inspect the bottom edges as well as the top-view diagram. Masked source stickers have been completed to a legal cube for setups and practice.'
                if case['alternatives']:
                    description += '\n\nAlternative algorithms from CubingApp (as listed):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'LSE', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-lse-eo4a-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/lse_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('LSE',))
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='LSE' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source'] + '\nEO4A is the edge-orientation stage of Roux LSE. Orient the last six edges while preserving both blocks and the solved corners. Edge placement and final centers may still need solving.'
                description += '\nRecognition: the case name describes the misoriented-edge pattern, including bottom edges. The thumbnail shows the upper layer; inspect DF and DB on the cube as well.'
                if case['alternatives']:
                    description += '\n\nAlternative solutions from SpeedCubeDB (as listed; may use another setup or orientation):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'LSE', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-cmll-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/cmll_algorithms.json').read_text())
            db.executemany('INSERT OR IGNORE INTO sets VALUES (?)', [('CMLL',), ('LSE',)])
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='CMLL' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source'] + '\nCMLL solves the four upper corners while preserving both Roux blocks. The M slice and remaining edges are free to change.'
                if case['alternatives']:
                    description += '\n\nAlternative solutions from SpeedCubeDB (as listed):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'CMLL', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-coll-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/coll_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('COLL',))
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='COLL' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source'] + '\nCOLL solves the last-layer corners while preserving edge orientation; edge permutation remains.'
                if case['alternatives']:
                    description += '\n\nAlternative solutions from SpeedCubeDB (as listed):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'COLL', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'speedcubedb-primary-algorithms-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/speedcubedb_overrides.json').read_text())
            for case in bundled['cases']:
                rows = db.execute('SELECT id, algorithm, description FROM cases WHERE alg_set=? AND (image=? OR name=?)',
                                  (case['alg_set'], case['image'], case['name'])).fetchall()
                for row in rows:
                    note = f"\n\nMain algorithm: SpeedCubeDB {case['source_name']}\n{case['source']}"
                    if row['algorithm'] != case['algorithm']:
                        note += '\nPrevious main algorithm: ' + row['algorithm']
                    if case['source_algorithms'][1:]:
                        note += '\nOther SpeedCubeDB solutions (as listed):\n' + '\n'.join(case['source_algorithms'][1:])
                    db.execute('UPDATE cases SET algorithm=?, description=? WHERE id=?',
                               (case['algorithm'], row['description']+note, row['id']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))


        migration = 'speedcubedb-antipll-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            bundled = json.loads((ROOT / 'src/data/antipll_algorithms.json').read_text())
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('Anti PLL',))
            for case in bundled['cases']:
                if db.execute("SELECT 1 FROM cases WHERE alg_set='Anti PLL' AND (name=? OR image=?)",
                              (case['name'], case['image'])).fetchone():
                    continue
                description = 'Source: ' + case['source'] + '\nAnti PLL solves last-layer permutation with all four last-layer edges flipped. This shared set is available under both CFCE and CFOP; edits and progress apply to both.'
                if case['alternatives']:
                    description += '\n\nAlternative solutions from SpeedCubeDB (as listed; may use another orientation):\n' + '\n'.join(case['alternatives'])
                db.execute('INSERT INTO cases(name, alg_set, category, algorithm, description, image) VALUES (?, ?, ?, ?, ?, ?)',
                           (case['name'], 'Anti PLL', case['category'], case['algorithm'], description, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))

        migration = 'method-advanced-subsets-v1'
        if not db.execute('SELECT 1 FROM migrations WHERE name=?', (migration,)).fetchone():
            db.execute('INSERT OR IGNORE INTO sets VALUES (?)', ('EOLR',))
            for case in json.loads((ROOT / 'src/data/eolr_algorithms.json').read_text())['cases']:
                category = case['category'].removeprefix('EOLR / ')
                db.execute("UPDATE cases SET alg_set='EOLR', category=CASE WHEN category=? THEN ? ELSE category END WHERE alg_set='LSE' AND image=?",
                           (case['category'], category, case['image']))
            db.execute('INSERT INTO migrations VALUES (?)', (migration,))


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/api/timer-scramble':
            try:
                return self.send(200, {'scramble': generate_timer_scramble()})
            except ValueError as exc:
                return self.send(503, {'error': str(exc)})
        if path == '/api/library':
            with connect() as db:
                return self.send(200, {'progress_states': ['not-learned', 'learning', 'learned'], 'sets': [r[0] for r in db.execute('SELECT name FROM sets ORDER BY name')], 'cases': [dict(r) for r in db.execute('SELECT * FROM cases ORDER BY id')]})
        if path == '/api/export':
            with connect() as db:
                return self.send(200, {'sets': [r[0] for r in db.execute('SELECT name FROM sets')], 'cases': [dict(r) for r in db.execute('SELECT * FROM cases')]})
        base = ROOT / 'src/static/cases/ell' if path.startswith('/ELL/') else ROOT / 'src' / 'static'
        relative = path[5:] if path.startswith('/ELL/') else ('index.html' if path == '/' else path.lstrip('/'))
        file = (base / relative).resolve()
        if not file.is_relative_to(base.resolve()) or not file.is_file():
            return self.send(404, {'error': 'Not found'})
        mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml'}.get(file.suffix, 'application/octet-stream')
        self.send(200, file.read_bytes(), mime)

    def do_POST(self):
        # A local browser app: reject cross-origin mutation requests.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.send(403, {'error': 'Origin rejected'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 1_000_000:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            path = urlparse(self.path).path
            if path.startswith('/api/bluetooth/'):
                # Local hardware access must come from this app, not cross-origin forms.
                if (origin != 'http://' + self.headers.get('Host', '')
                        or urlparse('http://' + self.headers.get('Host', '')).hostname not in ('localhost', '127.0.0.1', '::1')):
                    return self.send(403, {'error': 'Bluetooth requires a same-origin localhost request'})
                from src.bluetooth_bridge import bridge
                try:
                    return self.send(200, bridge.call(path.rsplit('/', 1)[-1], data))
                except Exception as exc:
                    return self.send(400, {'error': str(exc) or 'Local Bluetooth operation failed'})
            if path == '/api/inverse':
                reference = eolr_reference(data)
                return self.send(200, {'setup': reference['setup'] if reference else inverse(data['algorithm'])})
            if path == '/api/practice-scramble':
                # Validate the same notation accepted by the case editor.
                inverse(data['algorithm'])
                reference = eolr_reference(data)
                return self.send(200, {'setup': generate_practice_scramble(data['algorithm'], facelets=reference['facelets'] if reference else None)})
            if path == '/api/reset-progress':
                scope = data.get('scope')
                if scope not in ('all', 'subset') or data.get('confirmed') is not True:
                    raise ValueError('Choose a reset scope and confirm the reset')
                with connect() as db:
                    if scope == 'subset':
                        subset = data.get('alg_set')
                        if not isinstance(subset, str) or not db.execute('SELECT 1 FROM sets WHERE name=?', (subset,)).fetchone():
                            raise ValueError('Choose an existing algorithm set')
                        result = db.execute('UPDATE cases SET learned=0, learning=0 WHERE alg_set=? AND (learned=1 OR learning=1)', (subset,))
                    else:
                        result = db.execute('UPDATE cases SET learned=0, learning=0 WHERE learned=1 OR learning=1')
                    reset = result.rowcount
                return self.send(200, {'reset': reset})
            if path == '/api/progress':
                state = data.get('state')
                if state is not None and state not in ('not-learned', 'learning', 'learned'):
                    raise ValueError('Unknown progress state')
                learned = int(state == 'learned') if state else data.get('learned')
                if type(learned) not in (bool, int) or learned not in (0, 1):
                    raise ValueError('Learned must be true or false')
                with connect() as db:
                    learning = int(state == 'learning')
                    result = db.execute('UPDATE cases SET learned=?, learning=? WHERE id=?', (int(learned), learning, data['id']))
                    if not result.rowcount:
                        return self.send(404, {'error': 'Case not found'})
                return self.send(200, {'learned': int(learned), 'learning': learning})
            if path == '/api/practice-result':
                elapsed = data.get('elapsed_ms')
                if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
                    raise ValueError('Invalid solve time')
                with connect() as db:
                    if not db.execute('SELECT 1 FROM cases WHERE id=?', (data['id'],)).fetchone():
                        return self.send(404, {'error': 'Case not found'})
                    result = db.execute('UPDATE cases SET learned=1, learning=0 WHERE id=? AND learning=1 AND ? < 3000', (data['id'], elapsed))
                    promoted = bool(result.rowcount)
                return self.send(200, {'promoted': promoted})
            if path == '/api/sets':
                name = data['name'].strip()
                if not name:
                    raise ValueError('Enter a set name')
                with connect() as db:
                    db.execute('INSERT OR IGNORE INTO sets VALUES (?)', (name,))
                return self.send(200, {'ok': True})
            if path == '/api/case':
                fields = ['name', 'alg_set', 'category', 'algorithm', 'description', 'recognition', 'image', 'drawing']
                values = [data.get(k, '') for k in fields]
                if not all(isinstance(v, str) for v in values):
                    raise ValueError('Case fields must be text')
                learned = data.get('learned', 0)
                if type(learned) not in (bool, int) or learned not in (0, 1):
                    raise ValueError('Learned must be true or false')
                # An older client editing other details must not clear progress.
                if 'learned' in data or not data.get('id'):
                    fields.append('learned')
                    values.append(int(learned))
                if 'learning' in data or 'learned' in data or not data.get('id'):
                    learning = data.get('learning', 0)
                    if type(learning) not in (bool, int) or learning not in (0, 1) or (learning and learned):
                        raise ValueError('Invalid learning state')
                    fields.append('learning')
                    values.append(int(learning))
                if not values[0].strip() or not values[1].strip():
                    raise ValueError('Name and set are required')
                json.loads(data.get('drawing') or '{}')
                with connect() as db:
                    if not db.execute('SELECT 1 FROM sets WHERE name=?', (data['alg_set'],)).fetchone():
                        raise ValueError('Unknown algorithm set')
                    if data.get('id'):
                        db.execute('UPDATE cases SET ' + ','.join(f'{f}=?' for f in fields) + ' WHERE id=?', values + [data['id']])
                        case_id = data['id']
                    else:
                        cur = db.execute('INSERT INTO cases (' + ','.join(fields) + ') VALUES (' + ','.join('?' for _ in fields) + ')', values)
                        case_id = cur.lastrowid
                return self.send(200, {'id': case_id})
            return self.send(404, {'error': 'Not found'})
        except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            self.send(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description='Your local Rubik’s cube algorithm library')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    initialize()
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Cube Library running at {url}. Press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        from src.bluetooth_bridge import bridge
        bridge.close()
        server.server_close()
