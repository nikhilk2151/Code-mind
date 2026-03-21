# CodeMind 🧠 — AI Coding Practice Mentor

> **Vectorize Hindsight Hackathon submission** — an AI mentor that tracks your weak topics, recurring mistakes, and learning patterns across sessions using [Hindsight](https://hindsight.vectorize.io) persistent memory + [Pydantic AI](https://ai.pydantic.dev).

---

## Architecture

```
Student ──► codemind.py ──► Pydantic AI Agent (Groq LLaMA-3.3-70b)
                               │
                               ├── create_hindsight_tools()   →  retain / recall / reflect tools
                               └── memory_instructions()       →  auto-injects student history
                                          │
                               Hindsight Server (codemind-tutor-bank)
                               ├── Mission + Directives + Disposition
                               └── Observation Consolidation (auto-patterns)
```

---

## Quickstart

### 1. Start the Hindsight Server

Because `hindsight-all` (embedded Python server) requires Linux, use **one** of:

**Option A — Hindsight Cloud (recommended)**
1. Sign up at [ui.hindsight.vectorize.io](https://ui.hindsight.vectorize.io/signup)
2. Copy your instance URL into `.env` → `HINDSIGHT_BASE_URL=<your-url>`

**Option B — Docker (Linux/macOS/Windows with Docker Desktop)**
```bash
docker run --rm -p 8888:8888 \
  -e HINDSIGHT_API_LLM_PROVIDER=groq \
  -e HINDSIGHT_API_LLM_MODEL=llama-3.3-70b-versatile \
  -e HINDSIGHT_API_LLM_API_KEY=<your-groq-key> \
  ghcr.io/vectorize-io/hindsight:latest
```

### 2. Configure `.env`
```ini
HINDSIGHT_BASE_URL=http://localhost:8888   # or your Cloud URL
HINDSIGHT_API_KEY=                         # leave blank for local Docker
GROQ_API_KEY=your-groq-key
```

### 3. Install & Setup
```bash
python -m pip install -r requirements.txt
python setup_memory.py        # initialises the memory bank (run once)
```

### 4. Run Web UI (Recommended)
```bash
python server.py
```
Then open your browser to `http://localhost:3000`

### 5. Run Terminal App (Optional)
```bash
# Start a full interactive session
python codemind.py --user alice

# Just see the weakness radar
python codemind.py --user alice --radar-only

# Just generate a personalised challenge
python codemind.py --user alice --challenge-only

# Run integration tests
python test_codemind.py
```

---

## How It Works (Hindsight Primitives)

| Feature | Hindsight Call | Purpose |
|---|---|---|
| `end_session_evaluation()` | `client.retain()` | Save session outcome with strict tags |
| `generate_session_briefing()` | `client.reflect()` | Surface recurring patterns for welcome-back |
| `generate_personalized_challenge()` | `client.reflect()` | Spaced-repetition challenge generation |
| `generate_weakness_radar()` | `client.recall(tags_match="all_strict")` | Per-topic pass/fail aggregation |

### Memory Bank Psychology (`codemind-tutor-bank`)

| Setting | Value |
|---|---|
| **Mission** | Senior engineer mentoring for interviews; tracks mistakes, enforces spaced repetition |
| **Directive 1** | Never repeat a hint the student has already tried |
| **Directive 2** | Never give the full answer; use Socratic questioning |
| **Directive 3** | Always flag recurring mistake patterns explicitly |
| **Disposition: skepticism** | 4 — questions student logic |
| **Disposition: literalism** | 2 — flexible with pseudocode |
| **Disposition: empathy** | 4 — encouraging after failures |

---

## Project Structure

```
codemind/
├── .env                  # API keys + Hindsight URL (not committed)
├── requirements.txt      # Python dependencies
├── setup_memory.py       # One-time memory bank initialisation
├── codemind.py           # Main app (agent + 4 core features + terminal loop)
└── test_codemind.py      # Integration tests
```
