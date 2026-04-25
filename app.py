from flask import Flask, jsonify, request
from flask_cors import CORS
import random
import itertools

app = Flask(__name__)
CORS(app)

game_state = {}

def init_game(rows, cols):
    grid = [[{'pit': False, 'wumpus': False} for _ in range(cols)] for _ in range(rows)]
    total_cells = rows * cols
    num_pits = max(1, total_cells // 6)
    positions = [(r, c) for r in range(rows) for c in range(cols) if not (r == 0 and c == 0)]
    random.shuffle(positions)
    pit_positions = positions[:num_pits]
    wumpus_pos = positions[num_pits] if len(positions) > num_pits else None
    for r, c in pit_positions:
        grid[r][c]['pit'] = True
    if wumpus_pos:
        grid[wumpus_pos[0]][wumpus_pos[1]]['wumpus'] = True
    return {
        'grid': grid,
        'rows': rows,
        'cols': cols,
        'agent': (0, 0),
        'visited': {(0, 0)},
        'kb': [],
        'inference_steps': 0,
        'alive': True,
        'won': False,
        'safe_cells': {(0, 0)},
        'confirmed_danger': set(),
        'wumpus_alive': True,
        'gold_pos': positions[num_pits + 1] if len(positions) > num_pits + 1 else (rows-1, cols-1),
        'has_gold': False,
        'percept_log': []
    }

def get_neighbors(r, c, rows, cols):
    neighbors = []
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbors.append((nr, nc))
    return neighbors

def get_percepts(state, r, c):
    percepts = []
    grid = state['grid']
    rows, cols = state['rows'], state['cols']
    for nr, nc in get_neighbors(r, c, rows, cols):
        if grid[nr][nc]['pit']:
            percepts.append('Breeze')
            break
    for nr, nc in get_neighbors(r, c, rows, cols):
        if grid[nr][nc]['wumpus'] and state['wumpus_alive']:
            percepts.append('Stench')
            break
    if (r, c) == tuple(state['gold_pos']) and not state['has_gold']:
        percepts.append('Glitter')
    return list(set(percepts))

def tell_kb(state, r, c, percepts):
    rows, cols = state['rows'], state['cols']
    neighbors = get_neighbors(r, c, rows, cols)
    kb = state['kb']
    if 'Breeze' not in percepts:
        for nr, nc in neighbors:
            kb.append(('safe_pit', nr, nc))
    else:
        clause = [('pit', nr, nc) for nr, nc in neighbors]
        kb.append(('or_pit', clause))
    if 'Stench' not in percepts:
        for nr, nc in neighbors:
            kb.append(('safe_wumpus', nr, nc))
    else:
        clause = [('wumpus', nr, nc) for nr, nc in neighbors]
        kb.append(('or_wumpus', clause))
    kb.append(('visited', r, c))

def to_cnf_clauses(kb, query_literal, rows, cols):
    clauses = []
    for item in kb:
        if item[0] == 'safe_pit':
            _, r, c = item
            clauses.append([('not_pit', r, c)])
        elif item[0] == 'safe_wumpus':
            _, r, c = item
            clauses.append([('not_wumpus', r, c)])
        elif item[0] == 'or_pit':
            clauses.append(list(item[1]))
        elif item[0] == 'or_wumpus':
            clauses.append(list(item[1]))
        elif item[0] == 'visited':
            _, r, c = item
            clauses.append([('visited', r, c)])
    neg_type, qr, qc = query_literal
    if neg_type == 'not_pit':
        clauses.append([('pit', qr, qc)])
    elif neg_type == 'not_wumpus':
        clauses.append([('wumpus', qr, qc)])
    return clauses

def resolve(c1, c2):
    resolvents = []
    for lit in c1:
        complement = None
        if lit[0] == 'pit':
            complement = ('not_pit', lit[1], lit[2])
        elif lit[0] == 'not_pit':
            complement = ('pit', lit[1], lit[2])
        elif lit[0] == 'wumpus':
            complement = ('not_wumpus', lit[1], lit[2])
        elif lit[0] == 'not_wumpus':
            complement = ('wumpus', lit[1], lit[2])
        if complement and complement in c2:
            new_clause = [l for l in c1 if l != lit] + [l for l in c2 if l != complement]
            new_clause = list({tuple(l) for l in new_clause})
            new_clause = [list(l) for l in new_clause]
            resolvents.append(new_clause)
    return resolvents

def resolution_refutation(state, query_literal):
    rows, cols = state['rows'], state['cols']
    clauses = to_cnf_clauses(state['kb'], query_literal, rows, cols)
    clauses = [tuple(tuple(l) for l in c) for c in clauses]
    clauses = list(set(clauses))
    steps = 0
    max_steps = 500
    new_clauses = set()
    while steps < max_steps:
        pairs = list(itertools.combinations(clauses, 2))
        found_new = False
        for c1, c2 in pairs:
            resolvents = resolve(list(c1), list(c2))
            steps += 1
            for r in resolvents:
                r_tuple = tuple(tuple(l) for l in r)
                if len(r_tuple) == 0:
                    state['inference_steps'] += steps
                    return True, steps
                if r_tuple not in clauses and r_tuple not in new_clauses:
                    new_clauses.add(r_tuple)
                    found_new = True
        if not found_new:
            break
        clauses = list(set(clauses) | new_clauses)
    state['inference_steps'] += steps
    return False, steps

def ask_safe(state, r, c):
    safe_pit, steps1 = resolution_refutation(state, ('not_pit', r, c))
    safe_wumpus, steps2 = resolution_refutation(state, ('not_wumpus', r, c))
    return safe_pit and safe_wumpus

def agent_move(state, r, c):
    grid = state['grid']
    if grid[r][c]['pit']:
        state['alive'] = False
        return 'fell_in_pit'
    if grid[r][c]['wumpus'] and state['wumpus_alive']:
        state['alive'] = False
        return 'eaten_by_wumpus'
    state['agent'] = (r, c)
    state['visited'].add((r, c))
    percepts = get_percepts(state, r, c)
    tell_kb(state, r, c, percepts)
    rows, cols = state['rows'], state['cols']
    for nr, nc in get_neighbors(r, c, rows, cols):
        if (nr, nc) not in state['visited']:
            if ask_safe(state, nr, nc):
                state['safe_cells'].add((nr, nc))
    if (r, c) == tuple(state['gold_pos']):
        state['has_gold'] = True
        state['won'] = True
    return percepts

def serialize_state(state):
    return {
        'rows': state['rows'],
        'cols': state['cols'],
        'agent': list(state['agent']),
        'visited': [list(c) for c in state['visited']],
        'safe_cells': [list(c) for c in state['safe_cells']],
        'confirmed_danger': [list(c) for c in state['confirmed_danger']],
        'inference_steps': state['inference_steps'],
        'alive': state['alive'],
        'won': state['won'],
        'has_gold': state['has_gold'],
        'gold_pos': list(state['gold_pos']),
        'wumpus_alive': state['wumpus_alive'],
        'grid_truth': [
            [{'pit': state['grid'][r][c]['pit'], 'wumpus': state['grid'][r][c]['wumpus']}
             for c in range(state['cols'])]
            for r in range(state['rows'])
        ],
        'percepts': get_percepts(state, state['agent'][0], state['agent'][1])
    }

@app.route('/api/new_game', methods=['POST'])
def new_game():
    data = request.json
    rows = max(2, min(10, int(data.get('rows', 4))))
    cols = max(2, min(10, int(data.get('cols', 4))))
    state = init_game(rows, cols)
    percepts = get_percepts(state, 0, 0)
    tell_kb(state, 0, 0, percepts)
    for nr, nc in get_neighbors(0, 0, rows, cols):
        if ask_safe(state, nr, nc):
            state['safe_cells'].add((nr, nc))
    game_state.update(state)
    return jsonify(serialize_state(game_state))

@app.route('/api/move', methods=['POST'])
def move():
    if not game_state:
        return jsonify({'error': 'No game started'}), 400
    if not game_state['alive'] or game_state['won']:
        return jsonify({'error': 'Game over'}), 400
    data = request.json
    r, c = int(data['row']), int(data['col'])
    ar, ac = game_state['agent']
    rows, cols = game_state['rows'], game_state['cols']
    if (r, c) not in get_neighbors(ar, ac, rows, cols):
        return jsonify({'error': 'Invalid move: not adjacent'}), 400
    result = agent_move(game_state, r, c)
    return jsonify({**serialize_state(game_state), 'move_result': result if isinstance(result, str) else 'ok'})

@app.route('/api/auto_move', methods=['POST'])
def auto_move():
    if not game_state:
        return jsonify({'error': 'No game started'}), 400
    if not game_state['alive'] or game_state['won']:
        return jsonify({'error': 'Game over'}), 400
    ar, ac = game_state['agent']
    rows, cols = game_state['rows'], game_state['cols']
    neighbors = get_neighbors(ar, ac, rows, cols)
    safe_unvisited = [(r, c) for r, c in neighbors
                      if (r, c) in game_state['safe_cells'] and (r, c) not in game_state['visited']]
    if safe_unvisited:
        nr, nc = safe_unvisited[0]
        result = agent_move(game_state, nr, nc)
        return jsonify({**serialize_state(game_state), 'move_result': result if isinstance(result, str) else 'ok', 'auto': True})
    return jsonify({**serialize_state(game_state), 'move_result': 'no_safe_move', 'auto': True})

@app.route('/api/state', methods=['GET'])
def get_state():
    if not game_state:
        return jsonify({'error': 'No game started'}), 400
    return jsonify(serialize_state(game_state))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
