"""Print the prompt a scenario generates, without placing a call.

    python tools/show_persona.py 05
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import persona

wanted = sys.argv[1] if len(sys.argv) > 1 else "01"
matches = sorted(Path("scenarios").glob(f"{wanted}_*.yaml"))
if not matches:
    sys.exit(f"no scenario starting with {wanted!r} in scenarios/")

print(persona.load(matches[0]).instructions)
