#!/usr/bin/env python
"""HUMAN-OWNED. Run mutmut (v3), compute the kill rate, enforce the floor.

Coverage proves a line ran; mutation testing proves that if the line were wrong,
a test would notice. Surviving mutants are the review artifact worth reading.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

FLOOR = float(os.environ.get("MIN_MUTATION_SCORE", "70"))


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RUN_DB_TESTS": ""}
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)  # noqa: S603


def main() -> int:
    print("→ running mutmut (the slow gate)")
    proc = run(["mutmut", "run"])
    out = proc.stdout + proc.stderr

    counts: dict[str, int] = {}
    for emoji, key in (("🎉", "killed"), ("🙁", "survived"), ("🤔", "suspicious"),
                       ("⏰", "timeout"), ("🫥", "no_tests"), ("🔇", "skipped")):
        hits = re.findall(rf"{emoji}\s+(\d+)", out)
        counts[key] = int(hits[-1]) if hits else 0

    considered = counts["killed"] + counts["survived"] + counts["suspicious"] + counts["timeout"]
    if considered <= 0:
        print("✗ no mutants were generated — the gate is not actually running")
        print(out[-2000:])
        return 1

    killed = counts["killed"] + counts["timeout"]
    score = 100.0 * killed / considered
    print(f"  mutants: {considered}  killed: {killed}  survived: {counts['survived']}"
          f"  suspicious: {counts['suspicious']}")
    print(f"  score:   {score:.1f}%  (floor {FLOOR:.1f}%)")

    if counts["survived"]:
        survivors = run(["mutmut", "results"])
        lines = [ln for ln in survivors.stdout.splitlines() if "survived" in ln.lower()]
        if lines:
            print("\n  surviving mutants — read these, not the implementation:")
            for ln in lines[:40]:
                print(f"    · {ln.strip()}")

    if score < FLOOR:
        print(f"\n✗ mutation score {score:.1f}% is below the {FLOOR:.1f}% floor")
        return 1

    print("\n✓ mutation gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
