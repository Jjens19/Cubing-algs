"""Shared parsing, diagram generation, and cube-state matching for offline imports."""
import html
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from src.scrambler import Cube, FACES, SOLVED, invert, TOKEN

ROOT = Path(__file__).resolve().parents[2]
COLORS = {'U': '#ffff00', 'R': '#ff9900', 'F': '#00ff00', 'D': '#ffffff',
          'L': '#ff0000', 'B': '#0000ff', 'X': '#aab2a7'}
LAYOUT = [(f'U{i}', i % 3 + 2, i // 3 + 2) for i in range(9)]
LAYOUT += [(f'B{2-i}', i+2, 1) for i in range(3)]
LAYOUT += [(f'F{i}', i+2, 5) for i in range(3)]
LAYOUT += [(f'L{i}', 1, i+2) for i in range(3)]
LAYOUT += [(f'R{2-i}', 5, i+2) for i in range(3)]


def normalize(algorithm):
    # J Perm uses parentheses for finger-trick groups, not repetitions.
    result = ' '.join(algorithm.replace('(', ' ').replace(')', ' ').split())
    if any(not TOKEN.fullmatch(token) for token in result.split()):
        raise ValueError('Use space-separated cube moves without repetitions.')
    return result


def diagram(algorithm, subset):
    state = Cube().apply(invert(algorithm))
    target = state.normalized()
    # Apply the orientation/WV mask before the scramble, as J Perm does:
    # hide last-layer side colors, retain F2L colors carried up by a WV pair.
    masked = list(SOLVED)
    if subset in ('WV', 'OLL'):
        for face in 'RFLB':
            start = FACES.index(face)*9
            masked[start:start+3] = ['X']*3
    if subset == 'COLL':
        for index in (1, 3, 5, 7):
            masked[index] = 'X'
        for face in 'RFLB':
            masked[FACES.index(face)*9+1] = 'X'
    if subset == 'CMLL':
        for face in FACES:
            for index in (1, 3, 5, 7):
                masked[FACES.index(face)*9+index] = 'X'
        for face in 'UDFB':
            masked[FACES.index(face)*9+4] = 'X'
    colored = Cube(''.join(masked)).apply(invert(algorithm)).facelets
    centers = {state.facelets[i*9+4]: face for i, face in enumerate(FACES)}
    colored = [centers.get(color, color) for color in colored]
    stickers = {key: {'color': COLORS[colored[FACES.index(key[0])*9+int(key[1])]], 'highlight': False}
                for key, _, _ in LAYOUT}
    if subset == 'LSE':
        gray_misoriented_edges(stickers)
    if subset in ('CMLL', 'LSE'):
        stickers = full_cube_stickers(target, subset, stickers)
        return render_full_cube(stickers), target, stickers
    return render_diagram(stickers), target, stickers


def gray_misoriented_edges(stickers):
    """Mask non-U/D colors on both visible stickers of last-layer edges."""
    for key in ('U1', 'U3', 'U5', 'U7', 'F1', 'B1', 'L1', 'R1'):
        if stickers[key]['color'] not in (COLORS['U'], COLORS['D']):
            stickers[key]['color'] = COLORS['X']
    return stickers


def render_diagram(stickers, data_keys=False):
    svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg', viewBox='0 0 100 100', width='100', height='100')
    for key, x, y in LAYOUT:
        attributes = {'data-key': key} if data_keys else {}
        attributes.update({
            'x': str(3 if x == 1 else 85 if x == 5 else 16+(x-2)*23),
            'y': str(3 if y == 1 else 85 if y == 5 else 16+(y-2)*23),
            'width': str(13 if x in (1, 5) else 23), 'height': str(13 if y in (1, 5) else 23),
            'fill': stickers[key]['color'], 'stroke': '#000000', 'stroke-width': '3'})
        ET.SubElement(svg, 'rect', attributes)
    return ET.tostring(svg, encoding='unicode')+'\n'


def parse(page):
    parts = re.split(r'<div class="row singlealgorithm[^>]*data-alg="([^"]+)"[^>]*>', page)
    cases = []
    for name, body in zip(parts[1::2], parts[2::2]):
        algorithms = [html.unescape(re.sub('<[^>]*>', '', text)).strip()
                      for text in re.findall(r'<div class="formatted-alg">(.*?)</div>', body, re.S)]
        setup = html.unescape(re.search(r'<div class="setup-case[^>]*><div>setup:</div>(.*?)</div>', body, re.S).group(1)).strip()
        cases.append({'source_name': name, 'source_algorithms': algorithms, 'source_setup': setup,
                      'algorithm': normalize(algorithms[0])})
    return cases


def stage_solved(state, subset):
    if subset == 'PLL':
        return any(Cube(state).apply(auf).normalized() == SOLVED for auf in ['', 'U', "U'", 'U2'])
    return state[:9] == 'U'*9 and all(
        state[i*9+(0 if face == 'D' else 3):(i+1)*9] == face*(9-(0 if face == 'D' else 3))
        for i, face in enumerate(FACES) if face != 'U')


def match_pose(facelets, algorithm, subset):
    for rotation in ['', 'y', "y'", 'y2']:
        for auf in ['', 'U', "U'", 'U2']:
            state = Cube(Cube(facelets).apply(rotation).normalized()).apply(auf).apply(algorithm).normalized()
            if stage_solved(state, subset):
                return {'rotation': rotation, 'auf': auf}
    return None



def full_cube_stickers(facelets, subset, existing=None):
    """Keep display masks separate from the real, playable cube state."""
    stickers = {face+str(index): {'color': COLORS[facelets[f*9+index]], 'highlight': False}
                for f, face in enumerate(FACES) for index in range(9)}
    if subset == 'CMLL':
        for face in FACES:
            for index in (1, 3, 5, 7):
                stickers[face+str(index)]['color'] = COLORS['X']
        for face in 'UDFB':
            stickers[face+'4']['color'] = COLORS['X']
    stickers.update(existing or {})
    from src.scrambler import GEOMETRY
    for i, (position, _) in enumerate(GEOMETRY):
        if abs(position[0]) == 1 and position[1] <= 0:
            key = FACES[i//9]+str(i%9)
            stickers[key]['color'] = COLORS[facelets[i]]
    return stickers


def render_full_cube(stickers):
    """Two upright views expose the side layers while keeping U on top."""
    from src.scrambler import GEOMETRY
    svg = ET.Element('svg', xmlns='http://www.w3.org/2000/svg', viewBox='0 0 250 140', width='250', height='140')
    ET.SubElement(svg, 'metadata', id='cube-stickers').text = json.dumps(stickers)
    for direction, origin, label in ((1, 65, 'U · F · R'), (-1, 185, 'U · B · L')):
        for f, face in enumerate(FACES):
            for index in range(9):
                position, normal = GEOMETRY[f*9+index]
                if direction*(normal[0]+normal[2])+normal[1] <= 0:
                    continue
                axis = next(i for i, n in enumerate(normal) if n)
                plane = [i for i in range(3) if i != axis]
                center = [normal[i]*1.5 if i == axis else position[i] for i in range(3)]
                def project(p):
                    x, y, z = p
                    return origin+direction*(x-z)*18, 62+direction*(x+z)*8-y*20
                points = []
                for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    point = [v+(a*.47 if i == plane[0] else b*.47 if i == plane[1] else 0) for i, v in enumerate(center)]
                    points.append(','.join(f'{v:.2f}' for v in project(point)))
                key = face+str(index)
                ET.SubElement(svg, 'polygon', points=' '.join(points), fill=stickers[key]['color'], stroke='#000000', **{'stroke-width': '1', 'data-key': key})
        ET.SubElement(svg, 'text', x=str(origin), y='134', fill='#172e26', **{'text-anchor': 'middle', 'font-size': '10', 'font-family': 'sans-serif'}).text = label
    return ET.tostring(svg, encoding='unicode')+'\n'
