"""
setup_memory.py
───────────────
Initialises the CodeMind memory bank on a running Hindsight server.

Run ONCE before starting codemind.py:
    python setup_memory.py
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

from hindsight_client import Hindsight

BANK_ID = "codemind-tutor-bank"

REFLECT_MISSION = (
    "I am CodeMind, a senior software engineer mentoring a junior developer. "
    "I meticulously track their coding mistakes, adapt the difficulty of challenges, "
    "and enforce spaced repetition to reinforce weak areas. "
    "I am encouraging and constructive, but brutally honest about recurring failures. "
    "My goal is to make this student interview-ready by identifying and eliminating "
    "their specific blind spots, one session at a time. "
    "Rules: Never repeat a hint the student has already tried. "
    "Never give the full solution; use Socratic questioning. "
    "Always flag recurring mistake patterns explicitly."
)

OBSERVATIONS_MISSION = (
    "Synthesise student session records into observations about their recurring "
    "mistake patterns, weak topics, progress trends, and strengths. "
    "Flag when the same mistake type appears more than once."
)


def setup():
    base_url = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
    api_key = os.environ.get("HINDSIGHT_API_KEY") or None

    print(f"\n🔌  Connecting to Hindsight at: {base_url}")
    client = Hindsight(base_url=base_url, api_key=api_key)

    print(f"🔧  Configuring memory bank: '{BANK_ID}' …")

    # create_bank acts as upsert — creates if not exists, updates if it does
    bank = client.create_bank(
        bank_id=BANK_ID,
        name="CodeMind Tutor Bank",
        reflect_mission=REFLECT_MISSION,
        observations_mission=OBSERVATIONS_MISSION,
        enable_observations=True,
        disposition_skepticism=4,   # Question the student's logic
        disposition_literalism=2,   # Flexible with pseudocode
        disposition_empathy=4,      # Encouraging after failures
    )

    print(f"\n✅  Memory bank configured successfully!")
    print(f"    bank_id : {bank.bank_id}")
    print(f"    name    : {bank.name}")
    print("\nYou can now run:  python codemind.py --user alice\n")

    client.close()


if __name__ == "__main__":
    setup()
