"""Facelet simulation and verified alternative scrambles for a target case."""
import random
import re

FACES = 'URFDLB'
SOLVED = ''.join(face * 9 for face in FACES)
TOKEN = re.compile(r"([URFDLB]w?|[urfdlbMESxyz])([23]'?|')?")


def geometry():
    stickers = []
    for face in FACES:
        for row in range(3):
            for col in range(3):
                a, b = col - 1, 1 - row
                position, normal = {
                    'U': ((a, 1, -b), (0, 1, 0)),
                    'R': ((1, b, -a), (1, 0, 0)),
                    'F': ((a, b, 1), (0, 0, 1)),
                    'D': ((a, -1, b), (0, -1, 0)),
                    'L': ((-1, b, a), (-1, 0, 0)),
                    'B': ((-a, b, -1), (0, 0, -1)),
                }[face]
                stickers.append((position, normal))
    return stickers


GEOMETRY = geometry()
INDEX = {value: i for i, value in enumerate(GEOMETRY)}


def rotate(vector, axis):
    x, y, z = vector
    return ((x, -z, y), (z, y, -x), (-y, x, z))[axis]


class Cube:
    def __init__(self, facelets=SOLVED):
        self.facelets = list(facelets)

    def apply(self, algorithm):
        for token in algorithm.replace('’', "'").split():
            match = TOKEN.fullmatch(token)
            if not match:
                raise ValueError('Practice needs space-separated cube moves without brackets or repetitions.')
            move, suffix = match.groups()
            face = move[0].upper()
            wide = move.endswith('w') or move in 'urfdlb'
            if face in 'RL':
                axis, layer, sign = 0, (1 if face == 'R' else -1), (-1 if face == 'R' else 1)
            elif face in 'UD':
                axis, layer, sign = 1, (1 if face == 'U' else -1), (-1 if face == 'U' else 1)
            elif face in 'FB':
                axis, layer, sign = 2, (1 if face == 'F' else -1), (-1 if face == 'F' else 1)
            elif move in 'MES':
                axis, layer, sign = {'M': (0, 0, 1), 'E': (1, 0, 1), 'S': (2, 0, -1)}[move]
            else:
                axis, layer, sign = 'xyz'.index(move), None, -1
            turns = int(suffix[0]) if suffix and suffix[0].isdigit() else 1
            if suffix and suffix.endswith("'"):
                turns = -turns
            for _ in range((sign * turns) % 4):
                result = self.facelets.copy()
                for index, (position, normal) in enumerate(GEOMETRY):
                    if layer is None or position[axis] == layer or (wide and position[axis] == 0):
                        destination = INDEX[(rotate(position, axis), rotate(normal, axis))]
                        result[destination] = self.facelets[index]
                self.facelets = result
        return self

    def normalized(self):
        # Kociemba labels colors relative to the six current centers.
        colors = {self.facelets[i * 9 + 4]: face for i, face in enumerate(FACES)}
        return ''.join(colors[color] for color in self.facelets)


def invert(algorithm):
    return ' '.join(move[:-1] if move.endswith("2'") else move if move.endswith('2') else move[:-1] if move.endswith("'") else move + "'" for move in reversed(algorithm.split()))


def generate(algorithm, rng=None, facelets=None):
    try:
        import kociemba
    except ImportError:
        raise ValueError('Install the practice solver with: python -m pip install -r requirements.txt, then restart the app.') from None
    rng = rng or random.SystemRandom()
    target = Cube(facelets) if facelets else Cube().apply(invert(algorithm.replace('’', "'")))
    target.apply(rng.choice(['', 'U', "U'", 'U2']))
    restore = ''
    raw_target = ''.join(target.facelets)
    if facelets:
        rotation = next(r for r in ('', 'x', "x'", 'x2') if all(Cube(raw_target).apply(r).facelets[i*9+4] == face for i, face in enumerate(FACES)))
        restore = invert(rotation)
        target = ''.join(Cube(raw_target).apply(rotation).facelets)
    else:
        target = target.normalized()
    # Solve a perturbed target, then undo that perturbation at the end. This
    # yields a different route to the case rather than its saved alg backwards.
    suffix = []
    for _ in range(3):
        face = rng.choice([face for face in FACES if not suffix or face != suffix[-1][0]])
        suffix.append(face + rng.choice(['', "'", '2']))
    suffix = ' '.join(suffix)
    intermediate = Cube(target).apply(invert(suffix)).normalized()
    solution = '' if intermediate == SOLVED else kociemba.solve(intermediate)
    scramble = (invert(solution) + ' ' + suffix).strip()
    if Cube().apply(scramble).normalized() != target:
        raise ValueError('Could not verify the generated practice scramble.')
    if facelets:
        scramble = (scramble+' '+restore).strip()
        if ''.join(Cube().apply(scramble).facelets) != raw_target:
            raise ValueError('Could not verify the case-specific practice scramble.')
    return scramble
