"""run_full_synthetic_test_suite.py

Runs a full synthetic test suite and writes logs you can share.
- Runs unit tests (ambient_lighting/test*.py)
- Runs multiple soak scenarios across all modes (1-5)
- Saves a timestamped .log and per-scenario .json summary

This is intentionally synthetic: it does NOT require real screen capture or audio devices.

Usage (PowerShell):
  E:/ambient_light_project/.venv/Scripts/python.exe tools/run_full_synthetic_test_suite.py --minutes 30

Outputs:
  logs/synthetic_suite_YYYYmmdd_HHMMSS.log
  logs/synthetic_suite_YYYYmmdd_HHMMSS__soak_*.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], log_path: Path, title: str) -> int:
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n" + ("=" * 80) + "\n")
        f.write(f"{title}\n")
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.write(("=" * 80) + "\n")
        f.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        return int(proc.wait())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30.0, help="Total soak time budget in minutes (split across scenarios).")
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--out-dir", type=str, default="logs")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = out_dir / f"synthetic_suite_{stamp}.log"

    py = sys.executable

    # Split time budget across scenarios
    total_s = max(float(args.minutes) * 60.0, 60.0)
    # 3 scenarios: baseline, spatial bias, longer spatial bias
    s1 = max(total_s * 0.2, 60.0)
    s2 = max(total_s * 0.3, 60.0)
    s3 = max(total_s - s1 - s2, 60.0)

    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Synthetic test suite started: {stamp}\n")
        f.write(f"Python: {py}\n")
        f.write(f"Repo: {repo_root}\n")
        f.write(f"minutes={args.minutes} fps={args.fps}\n")

    rc = 0

    # 1) Unit tests
    rc |= _run(
        [py, "-m", "unittest", "discover", "-s", "ambient_lighting", "-p", "test*.py", "-q"],
        log_path,
        "UNIT TESTS",
    )

    # 2) Soak tests
    soak = repo_root / "tools" / "soak_test_synthetic_screen_modes.py"

    scenarios = [
        (
            "SOAK baseline (no spatial bias)",
            s1,
            False,
            out_dir / f"synthetic_suite_{stamp}__soak_baseline.json",
        ),
        (
            "SOAK spatial bias enabled",
            s2,
            True,
            out_dir / f"synthetic_suite_{stamp}__soak_spatial.json",
        ),
        (
            "SOAK spatial bias (longer)",
            s3,
            True,
            out_dir / f"synthetic_suite_{stamp}__soak_spatial_long.json",
        ),
    ]

    for title, seconds, spatial, json_out in scenarios:
        cmd = [
            py,
            str(soak),
            "--seconds",
            f"{seconds:.0f}",
            "--fps",
            f"{float(args.fps):.2f}",
            "--json-out",
            str(json_out),
        ]
        if spatial:
            cmd.append("--spatial-bias")
        rc |= _run(cmd, log_path, title)

    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n" + ("=" * 80) + "\n")
        f.write(f"DONE. exit_code={rc}\n")

    print(f"Wrote log: {log_path}")
    print(f"Wrote JSON summaries under: {out_dir}")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
