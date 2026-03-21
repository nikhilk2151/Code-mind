"""
codemind.py
───────────
CodeMind — AI Coding Practice Mentor
Built with Hindsight (persistent memory) + Pydantic AI (Socratic agent)

Pre-requisites:
  1. A running Hindsight server (Cloud or Docker):
       docker run --rm -p 8888:8888 \\
         -e HINDSIGHT_API_LLM_PROVIDER=groq \\
         -e HINDSIGHT_API_LLM_MODEL=llama-3.3-70b-versatile \\
         -e HINDSIGHT_API_LLM_API_KEY=$GROQ_API_KEY \\
         ghcr.io/vectorize-io/hindsight:latest
  2. HINDSIGHT_BASE_URL set in .env (default: http://localhost:8888)
  3. python setup_memory.py  (run once to configure the bank)

Usage:
    python codemind.py [--user USER_ID] [--radar-only] [--challenge-only]
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ─── Rich console ───────────────────────────────────────────────────────────────
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.rule import Rule

console = Console()

# ─── Hindsight + Pydantic AI ────────────────────────────────────────────────────
from hindsight_client import Hindsight
from hindsight_pydantic_ai import create_hindsight_tools, memory_instructions
from pydantic_ai import Agent

# ─── Constants ──────────────────────────────────────────────────────────────────
BANK_ID = "codemind-tutor-bank"

SYSTEM_PROMPT = """
You are CodeMind, a senior software engineer acting as a strict but empathetic
coding interview mentor. Your rules:

• NEVER give the final answer directly — ask Socratic guiding questions only.
• If the student is repeating a mistake from a past session, call it out explicitly.
• Adjust complexity: ease into a topic if they've recently failed it.
• Celebrate genuine progress briefly, then push harder.
• Keep responses concise and interview-appropriate.

When the student gives a wrong answer: explain WHY in one sentence, then ask
one guiding question to nudge them toward the correct thinking.
""".strip()


# ──────────────────────────────────────────────────────────────────────────────
# Helper: create client
# ──────────────────────────────────────────────────────────────────────────────

def get_client() -> Hindsight:
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
    api_key = os.environ.get("HINDSIGHT_API_KEY") or None
    return Hindsight(base_url=base_url, api_key=api_key)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 1: Retain session outcome
# ──────────────────────────────────────────────────────────────────────────────

def end_session_evaluation(
    client: Hindsight,
    user_id: str,
    problem_data: dict[str, Any],
    performance_data: dict[str, Any],
) -> str:
    """
    Retain the session outcome into Hindsight memory using strict tags.

    Hindsight autonomously:
    - Extracts entities/relationships from the natural language content
    - Consolidates patterns into Observations (e.g., recurring base-case errors)
    - Makes those patterns available in future reflect() calls
    """
    outcome = "pass" if performance_data.get("passed") else "fail"
    topic = problem_data.get("topic", "general").replace(" ", "_").lower()
    problem_name = problem_data.get("name", "Unknown Problem")
    time_taken_mins = performance_data.get("time_taken_mins", "N/A")
    mistake_description = performance_data.get("mistake", "")
    notes = performance_data.get("notes", "")

    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = (
        f"Session date: {timestamp_str}. "
        f"Student '{user_id}' {'passed' if outcome == 'pass' else 'failed'} "
        f"the problem '{problem_name}' (topic: {topic.replace('_', ' ')}) "
        f"in {time_taken_mins} minutes."
    )
    if mistake_description:
        content += f" Primary mistake: {mistake_description}."
    if notes:
        content += f" Additional notes: {notes}."

    # Strict tags for per-user filtering in recall()
    tags = [
        f"user:{user_id}",
        "type:session_record",
        f"outcome:{outcome}",
        f"topic:{topic}",
    ]

    client.retain(
        bank_id=BANK_ID,
        content=content,
        tags=tags,
        context=f"coding_session_{user_id}_{timestamp_str}",
    )

    return content


# ──────────────────────────────────────────────────────────────────────────────
# Feature 2: Session briefing via reflect()
# ──────────────────────────────────────────────────────────────────────────────

def generate_session_briefing(client: Hindsight, user_id: str) -> str:
    """
    Use reflect() with Hindsight's Observation Consolidation to surface
    recurring weaknesses and generate a personalised welcome-back message.

    The bank's Mission + Directives + Disposition trait configuration shapes
    how the reflect response is framed.
    """
    query = (
        f"Review all sessions for student '{user_id}'. "
        "What are their top 2-3 recurring weaknesses and most common mistake types? "
        "Generate a concise welcome-back message (3-4 sentences) that: "
        "1) Acknowledges their last session outcome, "
        "2) Names one specific recurring mistake explicitly, "
        "3) Sets the focus goal for today's session."
    )

    response = client.reflect(
        bank_id=BANK_ID,
        query=query,
        tags=[f"user:{user_id}"],
    )

    return response.text if hasattr(response, "text") else str(response)


# ──────────────────────────────────────────────────────────────────────────────
# Feature 3: Personalised challenge via reflect()
# ──────────────────────────────────────────────────────────────────────────────

def generate_personalized_challenge(client: Hindsight, user_id: str) -> dict[str, Any]:
    """
    Use reflect() to create a spaced-repetition coding challenge based on
    the student's historical failures and current knowledge state.
    """
    query = (
        f"Based on student '{user_id}' historical failures and recently learned topics, "
        "generate ONE new coding interview problem. Rules: "
        "1) If the student has no history, start with an 'easy' beginner problem. Once they start solving 'easy' problems securely, progressively increase difficulty to 'medium' and 'hard'. "
        "2) If they failed a topic recently, make an EASIER variant of that topic. "
        "3) Do not repeat a problem they have attempted before. "
        "4) Return a JSON object with keys: "
        "'name' (string), 'topic' (string), 'difficulty' (easy/medium/hard), "
        "'description' (full problem statement), 'hint' (first Socratic hint). "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    response = client.reflect(
        bank_id=BANK_ID,
        query=query,
        tags=[f"user:{user_id}"],
    )

    raw = response.text if hasattr(response, "text") else str(response)

    try:
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Sensible fallback so the session can still run
        return {
            "name": "Two Sum",
            "topic": "arrays",
            "difficulty": "easy",
            "description": (
                "Given an array of integers `nums` and an integer `target`, "
                "return indices of the two numbers that add up to `target`. "
                "Assume exactly one solution exists and you may not use the same element twice."
            ),
            "hint": "What data structure lets you check membership in O(1)?",
            "_raw": raw,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Feature 4: Weakness radar via recall()
# ──────────────────────────────────────────────────────────────────────────────

def generate_weakness_radar(client: Hindsight, user_id: str) -> dict[str, Any]:
    """
    Use recall() with strict tag filtering to retrieve all session records for
    this user and aggregate pass/fail rates per topic into a radar JSON payload.
    """
    memories = client.recall(
        bank_id=BANK_ID,
        query=f"all session records for student {user_id}",
        tags=[f"user:{user_id}", "type:session_record"],
        tags_match="all_strict",
        max_tokens=8192,
    )

    topic_stats: dict[str, dict[str, int]] = {}
    items = memories.results if hasattr(memories, "results") else (memories or [])

    for item in items:
        tags_list = getattr(item, "tags", []) or []
        topic = "general"
        outcome = "unknown"
        for tag in tags_list:
            if tag.startswith("topic:"):
                topic = tag.split(":", 1)[1].replace("_", " ")
            if tag.startswith("outcome:"):
                outcome = tag.split(":", 1)[1]

        if topic not in topic_stats:
            topic_stats[topic] = {"pass": 0, "fail": 0, "total": 0}
        topic_stats[topic]["total"] += 1
        if outcome == "pass":
            topic_stats[topic]["pass"] += 1
        elif outcome == "fail":
            topic_stats[topic]["fail"] += 1

    radar = []
    for topic, stats in topic_stats.items():
        total = stats["total"] or 1
        pass_rate = round(stats["pass"] / total * 100, 1)
        radar.append({
            "topic": topic,
            "pass_rate": pass_rate,
            "fail_rate": round(100 - pass_rate, 1),
            "total_attempts": stats["total"],
            "skill_score": pass_rate,
        })

    radar.sort(key=lambda x: x["skill_score"])  # weakest first

    return {
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weakness_radar": radar,
        "total_sessions_tracked": sum(s["total"] for s in topic_stats.values()),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Interactive terminal loop
# ──────────────────────────────────────────────────────────────────────────────

async def run_session(
    agent: Agent,
    client: Hindsight,
    user_id: str,
    challenge: dict[str, Any],
) -> dict[str, Any]:
    """Socratic Q&A loop for a coding challenge."""

    console.print(Rule("[bold cyan]💻  Coding Challenge[/bold cyan]"))
    console.print(Panel(
        f"[bold yellow]{challenge['name']}[/bold yellow]  "
        f"[dim]({challenge.get('difficulty', 'medium').upper()} · {challenge.get('topic', 'general')})[/dim]\n\n"
        + challenge.get("description", ""),
        title="📋 Problem",
        border_style="cyan",
    ))
    console.print(
        f"\n[dim]💡 First hint: {challenge.get('hint', 'Think step by step.')}[/dim]\n"
    )
    console.print(
        "[italic dim]Type your thoughts or code. "
        "Type [bold]solved[/bold] if you got it, [bold]quit[/bold] to end the session.[/italic dim]\n"
    )

    message_history: list = []
    session_start = datetime.now(timezone.utc)
    mistake_description = ""
    passed = False
    turns = 0

    # Prime the agent with the problem context
    initial_context = (
        f"The student is working on: '{challenge['name']}' "
        f"(topic: {challenge.get('topic', 'general')}, "
        f"difficulty: {challenge.get('difficulty', 'medium')}). "
        f"Problem statement: {challenge.get('description', '')}"
    )

    while True:
        try:
            user_input = console.input("[bold green]You ▶[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Session interrupted.[/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "done"):
            console.print("\n[bold cyan]Wrapping up your session…[/bold cyan]")
            break

        if user_input.lower() in ("solved", "pass", "correct", "got it"):
            passed = True
            console.print("\n[bold green]✅  Marked as solved. Well done![/bold green]\n")
            break

        turns += 1
        full_prompt = f"{initial_context}\n\nStudent says: {user_input}"

        with console.status("[dim]CodeMind is thinking…[/dim]", spinner="dots"):
            result = await agent.run(full_prompt, message_history=message_history)

        response_text = result.output
        message_history = result.all_messages()

        console.print(f"\n[bold magenta]CodeMind ▶[/bold magenta]")
        console.print(Markdown(response_text))
        console.print()

        if turns == 1 and not passed:
            mistake_description = f"Initial approach unclear on '{challenge['name']}'"

    elapsed = datetime.now(timezone.utc) - session_start
    time_taken_mins = round(elapsed.total_seconds() / 60, 1)

    return {
        "passed": passed,
        "time_taken_mins": time_taken_mins,
        "turns": turns,
        "mistake": mistake_description,
        "notes": f"Student completed {turns} exchange(s) with the mentor.",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

async def main(user_id: str, show_radar_only: bool = False, show_challenge_only: bool = False):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")

    if not groq_api_key:
        console.print("[bold red]ERROR:[/bold red] GROQ_API_KEY not set in .env")
        sys.exit(1)

    # ── Banner ────────────────────────────────────────────────────────────────
    console.print(Panel(
        "[bold cyan]CodeMind[/bold cyan] [dim]— AI Coding Practice Mentor[/dim]\n"
        "[dim]Powered by Hindsight Memory + Pydantic AI[/dim]",
        border_style="bright_blue",
        padding=(1, 4),
    ))
    console.print(f"\n[dim]👤 Student:[/dim] [bold]{user_id}[/bold]")
    console.print(f"[dim]🧠 Memory:[/dim] [dim]{base_url}[/dim]\n")

    # ── Create Hindsight client ───────────────────────────────────────────────
    client = get_client()

    # ── Build Pydantic AI agent with Hindsight memory tools ───────────────────
    # create_hindsight_tools() injects retain / recall / reflect as agent tools
    # so the agent can autonomously store and retrieve knowledge at any turn.
    tools = create_hindsight_tools(client=client, bank_id=BANK_ID)

    # memory_instructions() auto-recalls relevant memories before every LLM call
    # and injects them into the system prompt — eliminating agent amnesia.
    instructions_fn = memory_instructions(
        client=client,
        bank_id=BANK_ID,
        query=(
            f"student {user_id} recent mistakes, weak topics, "
            "recurring errors, strengths, completed problems"
        ),
        max_results=10,
    )

    agent = Agent(
        "groq:llama-3.3-70b-versatile",
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        instructions=[instructions_fn],
    )

    # ── Radar-only mode ───────────────────────────────────────────────────────
    if show_radar_only:
        console.print(Rule("[bold cyan]📊  Weakness Radar[/bold cyan]"))
        radar = generate_weakness_radar(client, user_id)
        console.print_json(json.dumps(radar, indent=2))
        return

    # ── Session briefing ──────────────────────────────────────────────────────
    with console.status("[dim]Loading your learning history…[/dim]", spinner="dots"):
        briefing = generate_session_briefing(client, user_id)

    if briefing and len(briefing) > 20 and "no memories" not in briefing.lower():
        console.print(Rule("[bold cyan]📖  Welcome Back[/bold cyan]"))
        console.print(Panel(
            Markdown(briefing),
            border_style="green",
            title="[green]Session Briefing[/green]",
        ))
    else:
        console.print(Panel(
            f"[bold]Hey {user_id}![/bold] Welcome! Let's start with a tailored challenge.",
            border_style="green",
        ))

    # ── Personalised challenge ────────────────────────────────────────────────
    with console.status("[dim]Generating your challenge…[/dim]", spinner="dots"):
        challenge = generate_personalized_challenge(client, user_id)

    if show_challenge_only:
        console.print(Rule("[bold cyan]📋  Generated Challenge[/bold cyan]"))
        console.print_json(json.dumps(challenge, indent=2))
        return

    # ── Socratic session loop ─────────────────────────────────────────────────
    performance_data = await run_session(agent, client, user_id, challenge)

    # ── Retain session outcome ────────────────────────────────────────────────
    console.print(Rule("[bold cyan]💾  Saving Session[/bold cyan]"))
    with console.status("[dim]Saving to memory…[/dim]", spinner="dots"):
        retained = end_session_evaluation(
            client=client,
            user_id=user_id,
            problem_data=challenge,
            performance_data=performance_data,
        )
    console.print(f"[green]✅  Retained:[/green] [dim]{retained[:100]}…[/dim]")

    # ── Weakness radar ────────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]📊  Your Weakness Radar[/bold cyan]"))
    radar = generate_weakness_radar(client, user_id)

    if radar["weakness_radar"]:
        console.print_json(json.dumps(radar, indent=2))
    else:
        console.print(
            "[dim]No historical data yet — complete more sessions to see your radar.[/dim]"
        )

    console.print(Rule())
    console.print(
        f"[bold green]Session complete![/bold green] "
        f"[dim]{performance_data['turns']} exchange(s) · "
        f"{performance_data['time_taken_mins']} min[/dim]"
    )
    console.print("[dim]Your progress is saved. Run again to continue where you left off.[/dim]\n")


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeMind — AI Coding Practice Mentor")
    parser.add_argument("--user", default="student_001", help="Student user ID")
    parser.add_argument("--radar-only", action="store_true",
                        help="Show weakness radar and exit")
    parser.add_argument("--challenge-only", action="store_true",
                        help="Generate a challenge and exit without starting a session")
    args = parser.parse_args()

    asyncio.run(main(
        user_id=args.user,
        show_radar_only=args.radar_only,
        show_challenge_only=args.challenge_only,
    ))
