"""Run several scenarios back to back, unattended.

    python tools/run_batch.py                 # every scenario
    python tools/run_batch.py 07 08 09        # only these ids

Calls run sequentially: the free ngrok tier allows one tunnel at a time, and
serial calls also keep us from hammering the system under test.
"""
import subprocess
import sys
import time
from pathlib import Path

wanted = sys.argv[1:]
scenarios = sorted(Path("scenarios").glob("*.yaml"))
if wanted:
    scenarios = [s for s in scenarios if s.name.split("_")[0] in wanted]

print(f"running {len(scenarios)} scenario(s)\n")
for i, path in enumerate(scenarios, 1):
    print(f"\n{'=' * 70}\n[{i}/{len(scenarios)}] {path.name}\n{'=' * 70}")
    try:
        subprocess.run([sys.executable, "-m", "src.run", "--scenario", str(path)], check=False)
    except KeyboardInterrupt:
        print("\ninterrupted - stopping batch")
        break
    if i < len(scenarios):
        print("\ncooling down 20s before next call...")
        time.sleep(20)

print("\nbatch complete. transcripts/ and recordings/ are populated.")
