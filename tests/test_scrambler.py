import importlib.util
import json
from pathlib import Path
import random
import unittest

from src.scrambler import Cube, SOLVED, generate, invert


class CubeTests(unittest.TestCase):
    def test_triple_turns_preserve_notation_and_simulate_correctly(self):
        for move in ['R', 'U', 'F', 'D', 'L', 'B', 'M', 'E', 'S', 'r', 'Rw', 'x', 'y', 'z']:
            with self.subTest(move=move):
                self.assertEqual(Cube().apply(move+'3').facelets, Cube().apply(move+"'").facelets)
                self.assertEqual(Cube().apply(move+"3'").facelets, Cube().apply(move).facelets)
                self.assertEqual(invert(move+'3'), move+"3'")
                self.assertEqual(invert(move+"3'"), move+'3')

    @unittest.skipUnless(importlib.util.find_spec('kociemba'), 'Install requirements.txt for scrambler tests')
    def test_practice_output_has_no_triple_turns(self):
        algorithm = "R U R3 U3"
        scramble = generate(algorithm, random.Random(3))
        self.assertNotIn('3', scramble)
        target = Cube().apply(invert(algorithm))
        expected = {Cube(''.join(target.facelets)).apply(auf).normalized() for auf in ['', 'U', "U'", 'U2']}
        self.assertIn(Cube().apply(scramble).normalized(), expected)

    def test_turns_and_notation(self):
        for move in ['U', 'R', 'F', 'D', 'L', 'B', 'M', 'E', 'S', 'r', 'u', 'f', 'x', 'y', 'z']:
            with self.subTest(move=move):
                self.assertEqual(Cube().apply(' '.join([move] * 4)).normalized(), SOLVED)
                self.assertEqual(Cube().apply(move + ' ' + invert(move)).normalized(), SOLVED)
        # Standard wide/slice/rotation identities, including center movement.
        for a, b in [('r', "R M'"), ('u', "U E'"), ('f', 'F S'), ('x', "R L' M'"), ('y', "U D' E'"), ('z', "F B' S")]:
            self.assertEqual(Cube().apply(a).facelets, Cube().apply(b).facelets)

    @unittest.skipUnless(importlib.util.find_spec('kociemba'), 'Install requirements.txt for scrambler tests')
    def test_all_ell_scrambles_reach_the_case_with_random_auf(self):
        cases = json.loads((Path(__file__).resolve().parents[1] / 'src' / 'ell_algorithms.json').read_text())['cases']
        for name, case in cases.items():
            algorithm = case['algorithm']
            if not algorithm:
                continue
            target = Cube().apply(invert(algorithm))
            allowed = {Cube(''.join(target.facelets)).apply(auf).normalized() for auf in ['', 'U', "U'", 'U2']}
            scrambles = []
            for seed in range(4):
                with self.subTest(case=name, seed=seed):
                    scramble = generate(algorithm, random.Random(seed))
                    self.assertIn(Cube().apply(scramble).normalized(), allowed)
                    self.assertNotEqual(scramble, invert(algorithm))
                    self.assertTrue(all(move[0] in 'URFDLB' for move in scramble.split()))
                    scrambles.append(scramble)
            self.assertGreater(len(set(scrambles)), 1)
