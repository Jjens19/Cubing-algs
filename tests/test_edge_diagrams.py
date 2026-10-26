import json
import unittest
import xml.etree.ElementTree as ET

from src import server
from tools.importers.common import COLORS, LAYOUT
from src.scrambler import FACES


class EdgeDiagramTests(unittest.TestCase):
    def test_only_non_white_yellow_edge_stickers_are_gray(self):
        count = 0
        for filename in ('lse_algorithms.json', 'eolr_algorithms.json'):
            cases = json.loads((server.ROOT / 'src/data' / filename).read_text())['cases']
            for case in cases:
                with self.subTest(case=case['name']):
                    svg = ET.parse(server.ROOT / 'src/static' / case['image'].lstrip('/')).getroot()
                    for key, _, _ in LAYOUT:
                        if key not in ('U1', 'U3', 'U5', 'U7', 'F1', 'B1', 'L1', 'R1'):
                            continue
                        face = case['facelets'][FACES.index(key[0])*9+int(key[1])]
                        expected = COLORS[face] if face in 'UD' else COLORS['X']
                        self.assertEqual(case['stickers'][key]['color'], expected)
                    polygons = [r for r in svg if r.get('data-key')]
                    if polygons:
                        self.assertEqual({r.get('data-key'):r.get('fill') for r in polygons}, {r.get('data-key'):case['stickers'][r.get('data-key')]['color'] for r in polygons})
                    else:
                        self.assertEqual([r.get('fill') for r in svg], [case['stickers'][key]['color'] for key, _, _ in LAYOUT])
                    count += 1
        self.assertEqual(count, 55)
