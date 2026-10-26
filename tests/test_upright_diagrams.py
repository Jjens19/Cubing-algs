import json
import unittest
import xml.etree.ElementTree as ET

from src import server
from src.scrambler import FACES, GEOMETRY
from tools.importers.common import COLORS


class UprightDiagramTests(unittest.TestCase):
    def test_u_is_up_and_roux_blocks_keep_their_colors(self):
        for filename in ('cmll_algorithms.json', 'lse_algorithms.json', 'eolr_algorithms.json'):
            for case in json.loads((server.ROOT / 'src/data' / filename).read_text())['cases']:
                with self.subTest(case=case['name']):
                    svg = ET.parse(server.ROOT / 'src/static' / case['image'].lstrip('/')).getroot()
                    keys = [node.get('data-key') for node in svg if node.tag.endswith('polygon')]
                    self.assertEqual(len(keys), 54)
                    self.assertEqual(sum(key.startswith('U') for key in keys), 18)
                    self.assertFalse(any(key.startswith('D') for key in keys))
                    for index, (position, _) in enumerate(GEOMETRY):
                        if abs(position[0]) == 1 and position[1] <= 0:
                            key = FACES[index//9]+str(index%9)
                            self.assertEqual(case['stickers'][key]['color'], COLORS[case['facelets'][index]])
                            self.assertNotEqual(case['stickers'][key]['color'], COLORS['X'])
