"""
mock_hindsight_server.py
─────────────────────────
Windows-native mock of the Hindsight HTTP API for local development.
No Docker, no uvloop, no Linux required.

Endpoints match the actual hindsight-client URL patterns:
  PUT  /v1/default/banks/{bank_id}               → create_bank
  POST /v1/default/banks/{bank_id}/memories/retain  → retain
  POST /v1/default/banks/{bank_id}/memories/recall  → recall
  POST /v1/default/banks/{bank_id}/memories/reflect → reflect

Usage (Terminal 1):
    python mock_hindsight_server.py

Usage (Terminal 2):
    python setup_memory.py
    python codemind.py --user alice
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from groq import Groq as GroqClient

app = FastAPI(title="Hindsight Mock Server", version="0.4.19")

# ── In-memory storage ─────────────────────────────────────────────────────────
BANKS: dict[str, dict] = {}
MEMORIES: dict[str, list[dict]] = {}


# ── Helper: call Groq for reflect ─────────────────────────────────────────────
def groq_reflect(bank: dict, memories: list[dict], query: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or "Configuration" in api_key or len(api_key) < 20:
        return (
            f"[Mock reflect — no valid GROQ_API_KEY] "
            f"Based on {len(memories)} memories, answering: {query[:80]}"
        )
    client = GroqClient(api_key=api_key)
    mem_text = "\n".join(
        f"- [{', '.join(m.get('tags', []))}] {m['content']}"
        for m in memories[-30:]
    ) or "No memories recorded yet."

    mission = bank.get("reflect_mission", bank.get("mission", ""))
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": f"You are a Hindsight memory assistant. {mission}"},
            {"role": "user", "content": f"Memories:\n{mem_text}\n\nQuery: {query}"},
        ],
        temperature=0.7,
        max_tokens=600,
    )
    return resp.choices[0].message.content


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "server": "hindsight-mock", "version": "0.4.19"}


@app.put("/v1/default/banks/{bank_id}")
async def create_bank(bank_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    BANKS[bank_id] = {
        "bank_id": bank_id,
        "name": body.get("name", bank_id),
        "reflect_mission": body.get("reflect_mission", body.get("mission", "")),
        "observations_mission": body.get("observations_mission", ""),
        "enable_observations": body.get("enable_observations", True),
        "disposition_skepticism": body.get("disposition_skepticism"),
        "disposition_literalism": body.get("disposition_literalism"),
        "disposition_empathy": body.get("disposition_empathy"),
    }
    if bank_id not in MEMORIES:
        MEMORIES[bank_id] = []
    # Return exactly the fields BankProfileResponse requires:
    # bank_id (StrictStr), name (StrictStr), mission (StrictStr),
    # disposition (object with skepticism/literalism/empathy), background (optional)
    return {
        "bank_id": bank_id,
        "name": BANKS[bank_id]["name"],
        "mission": BANKS[bank_id].get("reflect_mission", ""),
        "background": None,
        "disposition": {
            "skepticism": BANKS[bank_id].get("disposition_skepticism") or 3,
            "literalism": BANKS[bank_id].get("disposition_literalism") or 3,
            "empathy": BANKS[bank_id].get("disposition_empathy") or 3,
        },
    }


@app.get("/v1/default/banks/{bank_id}")
def get_bank(bank_id: str):
    if bank_id not in BANKS:
        raise HTTPException(status_code=404, detail=f"Bank '{bank_id}' not found. Run setup_memory.py first.")
    return BANKS[bank_id]


@app.post("/v1/default/banks/{bank_id}/memories/retain")
async def retain(bank_id: str, request: Request):
    body = await request.json()
    if bank_id not in BANKS:
        BANKS[bank_id] = {"bank_id": bank_id, "name": bank_id}
        MEMORIES[bank_id] = []

    items = body.get("items", [])
    retained_ids = []
    for item in items:
        mem = {
            "id": str(uuid.uuid4()),
            "content": item.get("content", ""),
            "tags": item.get("tags") or [],
            "context": item.get("context", ""),
            "timestamp": str(item.get("timestamp", datetime.now(timezone.utc).isoformat())),
        }
        MEMORIES[bank_id].append(mem)
        retained_ids.append(mem["id"])

    return {"success": True, "count": len(items), "ids": retained_ids}


@app.post("/v1/default/banks/{bank_id}/memories/recall")
async def recall(bank_id: str, request: Request):
    body = await request.json()
    tags_filter = body.get("tags") or []
    tags_match = body.get("tags_match", "any")
    query = body.get("query", "")

    all_mem = MEMORIES.get(bank_id, [])
    results = []
    for item in all_mem:
        item_tags = item.get("tags", [])
        if tags_filter:
            if tags_match == "all_strict":
                if not all(t in item_tags for t in tags_filter):
                    continue
            elif tags_match == "any_strict":
                if not any(t in item_tags for t in tags_filter):
                    continue
            elif tags_match == "all":
                if item_tags and not all(t in item_tags for t in tags_filter):
                    continue
            else:  # any
                if item_tags and not any(t in item_tags for t in tags_filter):
                    continue
        results.append(item)

    # Simple query-score
    q_words = query.lower().split()
    scored = sorted(results, key=lambda x: -sum(1 for w in q_words if w in x["content"].lower()))
    top = scored[:body.get("max_tokens", 50)]

    # Format results to match RecallResult structure
    formatted = [{"text": m["content"], "tags": m.get("tags", []), "id": m["id"]} for m in top]
    return {"results": formatted, "total": len(formatted)}


@app.post("/v1/default/banks/{bank_id}/memories/reflect")
async def reflect(bank_id: str, request: Request):
    body = await request.json()
    query = body.get("query", "")
    tags_filter = body.get("tags") or []

    bank = BANKS.get(bank_id, {"reflect_mission": ""})
    all_mem = MEMORIES.get(bank_id, [])

    # Filter by tags if provided
    if tags_filter:
        filtered = [m for m in all_mem if any(t in m.get("tags", []) for t in tags_filter)]
    else:
        filtered = all_mem

    answer = groq_reflect(bank, filtered, query)
    return {"answer": answer, "memories_used": len(filtered)}


# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("MOCK_PORT", "8888"))
    print(f"\n🎭  Hindsight Mock Server  →  http://localhost:{port}")
    print("   Routes: PUT/GET /v1/default/banks, retain, recall, reflect")
    print("   Reflect: uses Groq LLaMA-3.3-70b (needs valid GROQ_API_KEY in .env)")
    print("   Memory:  in-process (resets on restart)\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
