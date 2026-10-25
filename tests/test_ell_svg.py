import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src import server


class ELLVectorTests(unittest.TestCase):
    def test_vector_images_match_original_sticker_samples(self):
        cases = json.loads((server.ROOT / 'src/ell_stickers.json').read_text())
        self.assertEqual(len(cases), 30)
        self.assertFalse(list((server.ROOT / 'ELL').glob('*.png')))
        for filename, stickers in cases.items():
            with self.subTest(case=filename):
                svg = ET.parse(server.ROOT / 'ELL' / filename).getroot()
                self.assertEqual(svg.get('viewBox'), '0 0 100 100')
                self.assertEqual(len(svg), 21)
                self.assertEqual({r.get('data-key'): r.get('fill') for r in svg},
                                 {key: value['color'] for key, value in stickers.items()})

    def test_old_image_migration_preserves_all_other_fields(self):
        previous = server.DB
        with tempfile.TemporaryDirectory() as directory:
            server.DB = Path(directory) / 'library.sqlite3'
            try:
                server.initialize()
                with server.connect() as db:
                    db.execute("UPDATE cases SET image='/ELL/ell-A1.png', name='My case', recognition='My notes', learned=1, drawing=? WHERE image='/ELL/ell-A1.svg'",
                               (json.dumps({'useDrawing': True, 'stickers': {'U0': {'color': '#123456', 'highlight': True}}}),))
                    before = dict(db.execute("SELECT * FROM cases WHERE image='/ELL/ell-A1.png'").fetchone())
                    db.execute("DELETE FROM migrations WHERE name='ell-vector-images-v1'")
                server.initialize()
                server.initialize()
                with server.connect() as db:
                    after = dict(db.execute('SELECT * FROM cases WHERE id=?', (before['id'],)).fetchone())
                self.assertEqual(after, {**before, 'image': '/ELL/ell-A1.svg'})
            finally:
                server.DB = previous
