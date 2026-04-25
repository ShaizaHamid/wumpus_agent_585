const API = 'https://wumpus-agent-585.onrender.com/api';

let state = null;
let autoRunInterval = null;
let eventLog = [];

const $ = id => document.getElementById(id);

$('btn-new').addEventListener('click', startGame);
$('btn-auto').addEventListener('click', autoStep);
$('btn-auto-run').addEventListener('click', toggleAutoRun);
$('btn-restart').addEventListener('click', () => { stopAutoRun(); $('game-panel').classList.add('hidden'); $('setup-panel').classList.remove('hidden'); });
$('btn-overlay-restart').addEventListener('click', () => { $('overlay').classList.add('hidden'); stopAutoRun(); $('game-panel').classList.add('hidden'); $('setup-panel').classList.remove('hidden'); });

async function startGame() {
  const rows = parseInt($('inp-rows').value);
  const cols = parseInt($('inp-cols').value);
  eventLog = [];
  stopAutoRun();
  const res = await fetch(`${API}/new_game`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, cols })
  });
  state = await res.json();
  $('setup-panel').classList.add('hidden');
  $('game-panel').classList.remove('hidden');
  $('overlay').classList.add('hidden');
  addLog(`Game started: ${rows}×${cols} grid`, 'info');
  render();
}

async function moveAgent(r, c) {
  if (!state || !state.alive || state.won) return;
  const res = await fetch(`${API}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ row: r, col: c })
  });
  if (!res.ok) {
    const err = await res.json();
    addLog(err.error || 'Invalid move', 'bad');
    return;
  }
  const data = await res.json();
  handleMoveResult(data);
}

async function autoStep() {
  if (!state || !state.alive || state.won) return;
  const res = await fetch(`${API}/auto_move`, { method: 'POST' });
  const data = await res.json();
  handleMoveResult(data);
}

function toggleAutoRun() {
  if (autoRunInterval) {
    stopAutoRun();
  } else {
    $('btn-auto-run').textContent = '⏹ Stop';
    autoRunInterval = setInterval(async () => {
      if (!state || !state.alive || state.won) { stopAutoRun(); return; }
      await autoStep();
    }, 700);
  }
}

function stopAutoRun() {
  clearInterval(autoRunInterval);
  autoRunInterval = null;
  $('btn-auto-run').textContent = '⏩ Auto Run';
}

function handleMoveResult(data) {
  state = data;
  const result = data.move_result;
  if (result === 'fell_in_pit') {
    addLog('💀 Agent fell into a pit!', 'bad');
    stopAutoRun();
    showOverlay('💀', 'Game Over', 'The agent fell into a pit. Better logic next time!');
  } else if (result === 'eaten_by_wumpus') {
    addLog('🐉 Agent was eaten by the Wumpus!', 'bad');
    stopAutoRun();
    showOverlay('🐉', 'Game Over', 'The Wumpus got the agent. Use more caution!');
  } else if (result === 'no_safe_move') {
    addLog('🤔 No safe moves available from current position.', 'info');
    stopAutoRun();
  } else {
    const pos = data.agent;
    addLog(`Moved to (${pos[0]}, ${pos[1]}) — Percepts: ${data.percepts.length ? data.percepts.join(', ') : 'None'}`, 'good');
  }
  if (data.won) {
    stopAutoRun();
    showOverlay('🏆', 'Victory!', `Agent found the gold! Total inference steps: ${data.inference_steps}`);
  }
  render();
}

function render() {
  if (!state) return;
  renderGrid();
  renderPercepts();
  renderMetrics();
  renderKB();
  renderLog();
}

function renderGrid() {
  const { rows, cols, agent, visited, safe_cells, grid_truth, gold_pos, has_gold, alive } = state;
  const visitedSet = new Set(visited.map(v => `${v[0]},${v[1]}`));
  const safeSet = new Set(safe_cells.map(v => `${v[0]},${v[1]}`));

  let html = '<table>';
  for (let r = 0; r < rows; r++) {
    html += '<tr>';
    for (let c = 0; c < cols; c++) {
      const key = `${r},${c}`;
      const isAgent = agent[0] === r && agent[1] === c;
      const isVisited = visitedSet.has(key);
      const isSafeUnvisited = safeSet.has(key) && !isVisited;
      const isGold = gold_pos[0] === r && gold_pos[1] === c && !has_gold;
      const truth = grid_truth[r][c];
      const isDanger = !alive && (truth.pit || truth.wumpus);
      let cls = 'cell unvisited';
      if (isDanger) cls = 'cell danger';
      else if (isAgent) cls = 'cell agent';
      else if (isVisited) cls = 'cell visited';
      else if (isSafeUnvisited) cls = 'cell safe-unvisited';
      let icon = '';
      if (isAgent) icon = '🤖';
      else if (!alive && truth.pit) icon = '🕳️';
      else if (!alive && truth.wumpus) icon = '👾';
      else if (isGold) icon = '💰';
      else if (isVisited) icon = '✓';
      else if (isSafeUnvisited) icon = '?';
      else icon = '■';
      const percepts = isVisited ? getCellPercepts(r, c) : '';
      html += `<td><div class="${cls}" onclick="onCellClick(${r},${c})">
        <span class="cell-coord">${r},${c}</span>
        <span class="cell-icon">${icon}</span>
        ${percepts ? `<span class="cell-percept">${percepts}</span>` : ''}
      </div></td>`;
    }
    html += '</tr>';
  }
  html += '</table>';
  $('grid-container').innerHTML = html;
}

function getCellPercepts(r, c) {
  const { agent, percepts } = state;
  if (agent[0] === r && agent[1] === c) {
    return percepts.map(p => p === 'Breeze' ? '💨' : p === 'Stench' ? '💀' : '✨').join('');
  }
  return '';
}

function onCellClick(r, c) {
  const { agent, visited } = state;
  const visitedSet = new Set(visited.map(v => `${v[0]},${v[1]}`));
  if (!visitedSet.has(`${r},${c}`)) {
    moveAgent(r, c);
  }
}

function renderPercepts() {
  const { percepts } = state;
  if (!percepts || percepts.length === 0) {
    $('percept-list').innerHTML = '<span class="percept-badge none">None – all clear</span>';
  } else {
    $('percept-list').innerHTML = percepts.map(p => `<span class="percept-badge ${p}">${p === 'Breeze' ? '💨 ' : p === 'Stench' ? '💀 ' : '✨ '}${p}</span>`).join('');
  }
}

function renderMetrics() {
  $('m-steps').textContent = state.inference_steps;
  $('m-visited').textContent = state.visited.length;
  $('m-safe').textContent = state.safe_cells.length;
  $('m-pos').textContent = `(${state.agent[0]}, ${state.agent[1]})`;
  $('m-gold').textContent = state.has_gold ? '✅ Collected!' : '❌ Not found';
}

function renderKB() {
  const { visited, safe_cells, inference_steps } = state;
  $('kb-status').innerHTML = `
    <div>KB contains rules for <strong>${visited.length}</strong> visited cells</div>
    <div>Proved <strong>${safe_cells.length}</strong> cells safe via Resolution</div>
    <div>Total resolution iterations: <strong>${inference_steps}</strong></div>
    <div style="margin-top:0.5rem;color:#6c63ff">CNF clauses generated per move: ~${Math.max(1, Math.floor(inference_steps / Math.max(1, visited.length)))} avg</div>
  `;
}

function addLog(msg, type = '') {
  eventLog.unshift({ msg, type });
  if (eventLog.length > 50) eventLog.pop();
}

function renderLog() {
  $('event-log').innerHTML = eventLog.map(e => `<div class="log-entry ${e.type}">${e.msg}</div>`).join('');
}

function showOverlay(icon, title, msg) {
  $('overlay-icon').textContent = icon;
  $('overlay-title').textContent = title;
  $('overlay-msg').textContent = msg;
  $('overlay').classList.remove('hidden');
}
