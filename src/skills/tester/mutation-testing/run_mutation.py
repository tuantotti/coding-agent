"""Mutation testing helper — wraps mutmut and emits a JSON report.

Usage:
    python3 run_mutation.py --src path/to/module.py --tests path/to/tests/ \
        [--runner pytest] [--timeout 120]

Exit codes:
    0  Report written successfully (even if mutants survived).
    1  Pre-flight failure (import error, baseline failure, mutmut not found).
    2  Argument error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )


def _check_mutmut() -> bool:
    import importlib.util
    return importlib.util.find_spec("mutmut") is not None


def _baseline_run(tests_path: str, runner: str) -> tuple[bool, str]:
    """Return (passed, output). A failing baseline means mutation testing is invalid."""
    if runner == "pytest":
        result = _run([sys.executable, "-m", "pytest", tests_path, "-x", "-q", "--tb=short"], timeout=120)
        return result.returncode == 0, result.stdout + result.stderr
    return False, f"Unsupported runner: {runner}"


def _parse_mutmut_results(project_root: str) -> list[dict]:
    """Read mutmut's sqlite cache and return surviving mutant details."""
    result = _run(
        [sys.executable, "-m", "mutmut", "results"],
        cwd=project_root,
    )
    surviving: list[dict] = []
    if result.returncode != 0:
        return surviving

    current_file: str = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("---- ") and line.endswith(" ----"):
            current_file = line[5:-5].strip()
        elif line.startswith("Survived:") or ("⠿" not in line and line.startswith("#")):
            pass  # progress lines
        elif line.isdigit() or (line and line[0] == "#"):
            mutant_id = line.lstrip("#").strip().split()[0] if line else ""
            if mutant_id:
                show = _run(
                    [sys.executable, "-m", "mutmut", "show", mutant_id],
                    cwd=project_root,
                )
                surviving.append({
                    "id": mutant_id,
                    "file": current_file,
                    "diff": show.stdout.strip(),
                })
    return surviving


def _run_mutmut(src_path: str, tests_path: str, runner: str, timeout: int, project_root: str) -> dict:
    """Execute mutmut and return a structured report dict."""
    cmd = [
        sys.executable, "-m", "mutmut", "run",
        f"--paths-to-mutate={src_path}",
        f"--tests-dir={tests_path}",
        f"--runner={runner}",
        f"--test-time-base={timeout}",
        "--simple-output",
    ]
    result = _run(cmd, cwd=project_root, timeout=timeout * 50)

    import re

    total = killed = survived = timed_out = 0
    # mutmut 2.x spinner format: "6/6  KILLED 3  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 3  SKIPPED 0"
    _PROGRESS = re.compile(
        r"(\d+)/(\d+)\s+KILLED\s+(\d+)\s+TIMEOUT\s+(\d+).*?SURVIVED\s+(\d+)"
    )
    for line in (result.stdout + result.stderr).splitlines():
        m = _PROGRESS.search(line)
        if m:
            total = int(m.group(2))
            killed = int(m.group(3))
            timed_out = int(m.group(4))
            survived = int(m.group(5))

    surviving_detail = _parse_mutmut_results(project_root)
    killed_ratio = killed / total if total > 0 else 0.0

    return {
        "summary": {
            "total": total,
            "killed": killed,
            "survived": survived,
            "timeout": timed_out,
        },
        "killed_ratio": round(killed_ratio, 4),
        "surviving_mutants": surviving_detail,
        "raw_output": (result.stdout + result.stderr)[-3000:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mutation testing helper for the tester agent.")
    parser.add_argument("--src", required=True, help="Path to the source module to mutate.")
    parser.add_argument("--tests", required=True, help="Path to the test directory.")
    parser.add_argument("--runner", default="pytest", help="Test runner command (default: pytest).")
    parser.add_argument("--timeout", type=int, default=30, help="Per-mutant timeout in seconds.")
    parser.add_argument("--project-root", default=None, help="Project root (default: cwd).")

    args = parser.parse_args(argv)
    project_root = args.project_root or os.getcwd()

    src_path = str(Path(args.src).resolve())
    tests_path = str(Path(args.tests).resolve())

    report: dict = {"src": src_path, "tests": tests_path, "runner": args.runner}

    if not _check_mutmut():
        report["error"] = "mutmut not found. Install with: pip install mutmut"
        print(json.dumps(report, indent=2))
        return 1

    baseline_ok, baseline_out = _baseline_run(tests_path, args.runner)
    if not baseline_ok:
        report["error"] = "Baseline test run failed — fix failing tests before mutation testing."
        report["baseline_output"] = baseline_out[-2000:]
        print(json.dumps(report, indent=2))
        return 1

    report.update(_run_mutmut(src_path, tests_path, args.runner, args.timeout, project_root))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
