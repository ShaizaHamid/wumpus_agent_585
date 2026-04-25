# Wumpus World – Dynamic Logic Agent

A Knowledge-Based Agent that navigates a Wumpus World grid using **Propositional Logic** and **Resolution Refutation**.

## Stack
- **Backend:** Python 3 + Flask (inference engine, KB, CNF conversion)
- **Frontend:** Vanilla HTML/CSS/JS (no framework needed)

## Project Structure

```
wumpus/
├── backend/
│   ├── app.py            # Flask API + KB + Resolution engine
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## How to Run

### Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Server runs at `http://localhost:5000`

### Frontend
Open `frontend/index.html` in your browser, or serve it:
```bash
cd frontend
python -m http.server 8080
```
Then open `http://localhost:8080`

## Logic Engine

### Knowledge Base (KB)
When the agent visits a cell and receives percepts:
- **No Breeze** → all neighbors are safe from pits → `¬P(r,c)` for each neighbor
- **Breeze** → at least one neighbor has a pit → `P(n1) ∨ P(n2) ∨ ...`
- Same logic applies for **Stench** and Wumpus

### CNF Conversion
All KB facts are stored directly in Conjunctive Normal Form:
- `safe_pit(r,c)` → `[¬Pit(r,c)]` (unit clause)
- `or_pit(neighbors)` → `[Pit(n1) ∨ Pit(n2) ∨ ...]`

### Resolution Refutation
To prove a cell `(r,c)` is safe:
1. Negate the query: add `[Pit(r,c)]` to KB
2. Repeatedly resolve pairs of clauses
3. If the empty clause `[]` is derived → contradiction → cell IS safe
4. If no new clauses can be derived → cannot prove safety

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/new_game` | Start game with `{rows, cols}` |
| POST | `/api/move` | Move agent to `{row, col}` |
| POST | `/api/auto_move` | Agent picks best safe move |
| GET  | `/api/state` | Get current game state |

## Deployment
- **Backend:** Deploy to [Railway](https://railway.app) or [Render](https://render.com)
- **Frontend:** Deploy to [Vercel](https://vercel.com) or [Netlify](https://netlify.com)

Update the `API` constant in `frontend/app.js` to point to your deployed backend URL.
