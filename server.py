"""
server.py  —  CodeMind Web Server
──────────────────────────────────
FastAPI backend exposing the CodeMind AI Coding Mentor via HTTP/SSE.

Endpoints:
  GET  /                          → serves index.html
  POST /api/session/start         → returns session briefing + challenge
  POST /api/chat                  → streams mentor response (SSE)
  POST /api/session/end           → retains session outcome
  GET  /api/radar/{user_id}       → returns weakness radar JSON

Run:
    python server.py
Then open: http://localhost:3000
"""

import asyncio
import json
import os
import sys
import time
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hindsight_client import Hindsight
from pydantic_ai import Agent
from codemind import (
    BANK_ID, SYSTEM_PROMPT,
    end_session_evaluation,
    generate_session_briefing,
    generate_personalized_challenge,
    generate_weakness_radar,
    get_client,
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="CodeMind API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Per-session agent cache ───────────────────────────────────────────────────
_sessions: dict[str, dict] = {}  # user_id → {agent, client, history}


def get_or_create_session(user_id: str) -> dict:
    if user_id not in _sessions:
        client = get_client()
        agent = Agent(
            "groq:llama-3.3-70b-versatile",
            system_prompt=SYSTEM_PROMPT,
        )
        _sessions[user_id] = {
            "client": client,
            "agent": agent,
            "history": [],
        }
    return _sessions[user_id]


# ── Request / Response models ─────────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    user_id: str

class ChatRequest(BaseModel):
    user_id: str
    message: str
    challenge: dict

class EndSessionRequest(BaseModel):
    user_id: str
    problem: dict
    performance: dict


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/api/session/start")
def session_start(req: StartSessionRequest):
    sess = get_or_create_session(req.user_id)
    client: Hindsight = sess["client"]

    briefing = generate_session_briefing(client, req.user_id)
    challenge = generate_personalized_challenge(client, req.user_id)

    return {
        "briefing": briefing,
        "challenge": challenge,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    sess = get_or_create_session(req.user_id)
    agent: Agent = sess["agent"]
    history = sess["history"]

    challenge = req.challenge
    context = (
        f"Student is working on: '{challenge.get('name', 'Unknown')}' "
        f"(topic: {challenge.get('topic', 'general')}, "
        f"difficulty: {challenge.get('difficulty', 'medium')}). "
        f"Problem: {challenge.get('description', '')} "
        f"Student says: {req.message}"
    )

    # SSE streaming response
    async def stream_tokens() -> AsyncGenerator[str, None]:
        accumulated = ""
        async with agent.run_stream(context, message_history=history) as result:
            async for token in result.stream_text(delta=True):
                accumulated += token
                data = json.dumps({"token": token, "done": False})
                yield f"data: {data}\n\n"

            # Update history after stream completes
            sess["history"] = result.all_messages()

        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    return StreamingResponse(
        stream_tokens(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/session/end")
def session_end(req: EndSessionRequest):
    sess = get_or_create_session(req.user_id)
    client: Hindsight = sess["client"]

    retained = end_session_evaluation(
        client=client,
        user_id=req.user_id,
        problem_data=req.problem,
        performance_data=req.performance,
    )

    # Reset history for next session
    sess["history"] = []

    return {"retained": retained, "status": "ok"}


@app.get("/api/radar/{user_id}")
def radar(user_id: str):
    sess = get_or_create_session(user_id)
    client: Hindsight = sess["client"]
    return generate_weakness_radar(client, user_id)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    print(f"\n🚀  CodeMind Web Server  →  http://localhost:{port}")
    print(f"   Hindsight: {os.environ.get('HINDSIGHT_BASE_URL', 'http://localhost:8888')}")
    print(f"   Open your browser at: http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
