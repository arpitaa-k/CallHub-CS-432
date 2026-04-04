"""Compatibility launcher for the Locust stress test.

This keeps the old command-line entrypoint, but the real workload now lives in locustfile.py.
Run this script to start Locust headlessly and write the summary JSON.
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_SUMMARY = "../benchmarks/locust_stress_summary.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CallHub Locust stress test")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--users-file", default="test_users.json")
    parser.add_argument("--target-member-id", type=int, default=1)
    parser.add_argument("--requests", type=int, default=1000, help="Used to estimate run time for Locust")
    parser.add_argument("--workers", type=int, default=50, help="Used as the Locust user count")
    parser.add_argument("--update-every", type=int, default=4, help="Passed through for workload mix")
    parser.add_argument("--unauth-update-every", type=int, default=10, help="Passed through for workload mix")
    parser.add_argument("--durability-delay-sec", type=int, default=3, help="Kept for compatibility; not used by Locust")
    parser.add_argument("--category-name", default="Public", help="Kept for compatibility; not used by Locust")
    parser.add_argument("--role-title", default="Director", help="Kept for compatibility; not used by Locust")
    parser.add_argument("--summary-file", default=DEFAULT_SUMMARY)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    env = os.environ.copy()
    env["TARGET_MEMBER_ID"] = str(args.target_member_id)
    env["USERS_FILE"] = args.users_file
    env["STRESS_SUMMARY_FILE"] = args.summary_file
    env["LOCUST_HOST"] = args.base_url
    env["UPDATE_EVERY"] = str(args.update_every)
    env["UNAUTH_UPDATE_EVERY"] = str(args.unauth_update_every)

    estimated_seconds = max(30, int(math.ceil(args.requests / max(1, args.workers))))
    locustfile = Path(__file__).with_name("locustfile.py")

    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(locustfile),
        "--headless",
        "-H",
        args.base_url,
        "-u",
        str(args.workers),
        "-r",
        str(max(1, args.workers)),
        "--run-time",
        f"{estimated_seconds}s",
        "--stop-timeout",
        "10",
    ]

    print("Running Locust stress test with:")
    print(f"  host={args.base_url}")
    print(f"  users={args.workers}")
    print(f"  spawn_rate={max(1, args.workers)}")
    print(f"  estimated_run_time={estimated_seconds}s")
    print(f"  summary_file={args.summary_file}")
    print()

    completed = subprocess.run(command, env=env)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
