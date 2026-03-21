"""
test_codemind.py
────────────────
Integration tests for CodeMind's 4 core Hindsight feature functions.
Seeds mock session data and validates all features against a live Hindsight server.

Usage:
    python test_codemind.py
"""

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.rule import Rule

console = Console()

from hindsight_client import Hindsight
from codemind import (
    end_session_evaluation,
    generate_session_briefing,
    generate_personalized_challenge,
    generate_weakness_radar,
    BANK_ID,
)

TEST_USER = "test_student_001"

MOCK_SESSIONS = [
    {
        "problem": {"name": "Coin Change", "topic": "dynamic_programming"},
        "performance": {
            "passed": False, "time_taken_mins": 25,
            "mistake": "Off-by-one error in the base case (dp[0] initialised wrong)",
            "notes": "Student jumped to solution without DP table.",
        },
    },
    {
        "problem": {"name": "Fibonacci (Memoisation)", "topic": "dynamic_programming"},
        "performance": {
            "passed": False, "time_taken_mins": 18,
            "mistake": "Failed to handle the base case for n=0",
            "notes": "Same base-case error as Coin Change.",
        },
    },
    {
        "problem": {"name": "Two Sum", "topic": "arrays"},
        "performance": {
            "passed": True, "time_taken_mins": 8,
            "mistake": "", "notes": "Correct hash-map approach.",
        },
    },
    {
        "problem": {"name": "Valid Parentheses", "topic": "stacks"},
        "performance": {
            "passed": True, "time_taken_mins": 10,
            "mistake": "", "notes": "Clean solution on first attempt.",
        },
    },
    {
        "problem": {"name": "Binary Search", "topic": "binary_search"},
        "performance": {
            "passed": False, "time_taken_mins": 20,
            "mistake": "Incorrect mid-point calculation causing infinite loop",
            "notes": "Did not account for integer overflow.",
        },
    },
]


def run_tests():
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
    api_key = os.environ.get("HINDSIGHT_API_KEY") or None

    console.print(Rule("[bold cyan]🧪  CodeMind Integration Tests[/bold cyan]"))
    console.print(f"[dim]Hindsight:[/dim] {base_url}")
    console.print(f"[dim]User ID:   [/dim] {TEST_USER}\n")

    client = Hindsight(base_url=base_url, api_key=api_key)
    passed_tests = 0
    total_tests = 4

    # ── Test 1: end_session_evaluation (retain) ───────────────────────────────
    console.print("[bold]Test 1:[/bold] end_session_evaluation() → retain()")
    try:
        last = ""
        for session in MOCK_SESSIONS:
            last = end_session_evaluation(
                client=client,
                user_id=TEST_USER,
                problem_data=session["problem"],
                performance_data=session["performance"],
            )
            assert isinstance(last, str) and len(last) > 10
        console.print(
            f"  [green]✅ PASS[/green] — {len(MOCK_SESSIONS)} records retained.\n"
            f"     Last: [dim]{last[:80]}…[/dim]"
        )
        passed_tests += 1
    except Exception as e:
        console.print(f"  [red]❌ FAIL[/red] — {e}")

    # ── Test 2: generate_session_briefing (reflect) ───────────────────────────
    console.print("\n[bold]Test 2:[/bold] generate_session_briefing() → reflect()")
    try:
        briefing = generate_session_briefing(client=client, user_id=TEST_USER)
        assert isinstance(briefing, str) and len(briefing) > 20
        console.print(
            f"  [green]✅ PASS[/green] — {len(briefing)} chars.\n"
            f"     Preview: [dim]{briefing[:120]}…[/dim]"
        )
        passed_tests += 1
    except Exception as e:
        console.print(f"  [red]❌ FAIL[/red] — {e}")

    # ── Test 3: generate_personalized_challenge (reflect) ─────────────────────
    console.print("\n[bold]Test 3:[/bold] generate_personalized_challenge() → reflect()")
    challenge = {}
    try:
        challenge = generate_personalized_challenge(client=client, user_id=TEST_USER)
        required = {"name", "topic", "difficulty", "description"}
        assert isinstance(challenge, dict), "Should be dict"
        assert required.issubset(challenge.keys()), f"Missing: {required - challenge.keys()}"
        console.print(
            f"  [green]✅ PASS[/green] — "
            f"[bold]{challenge['name']}[/bold] ({challenge['difficulty']} · {challenge['topic']})"
        )
        passed_tests += 1
    except Exception as e:
        console.print(f"  [red]❌ FAIL[/red] — {e}")
        if challenge:
            console.print(f"     Raw: {json.dumps(challenge, indent=2)[:200]}")

    # ── Test 4: generate_weakness_radar (recall) ──────────────────────────────
    console.print("\n[bold]Test 4:[/bold] generate_weakness_radar() → recall()")
    try:
        radar = generate_weakness_radar(client=client, user_id=TEST_USER)
        assert isinstance(radar, dict) and "weakness_radar" in radar
        assert "total_sessions_tracked" in radar
        if radar["weakness_radar"]:
            s = radar["weakness_radar"][0]
            assert "topic" in s and "pass_rate" in s
        console.print(
            f"  [green]✅ PASS[/green] — "
            f"{len(radar['weakness_radar'])} topic(s), {radar['total_sessions_tracked']} session(s)."
        )
        console.print_json(json.dumps(radar, indent=2))
        passed_tests += 1
    except Exception as e:
        console.print(f"  [red]❌ FAIL[/red] — {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule())
    color = "green" if passed_tests == total_tests else "yellow"
    console.print(f"[bold {color}]Results: {passed_tests}/{total_tests} passed[/bold {color}]")
    if passed_tests < total_tests:
        console.print("[dim]Tip: ensure Hindsight server is running and setup_memory.py was run first.[/dim]")
    sys.exit(0 if passed_tests == total_tests else 1)


if __name__ == "__main__":
    run_tests()
