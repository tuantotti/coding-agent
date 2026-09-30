"""Filter SWE-bench Verified instances to a set likely to build on Apple Silicon.

Load the pinned dataset revision, restrict to a curated allowlist of pure-Python
repositories, and print the selected instance IDs. Also print a summary of every
repo in the dataset so the caller can see what was excluded.

Nothing here calls the coding-agent API or spends money — this is a plumbing
tool for building a smoke-test instance list.

Examples:
    uv run python scripts/benchmark_filter_instances.py --limit 20
    uv run python scripts/benchmark_filter_instances.py --tier all --limit 5
    uv run python scripts/benchmark_filter_instances.py --out .benchmark-results/arm_smoke.txt
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

DATASET_NAME = "SWE-bench/SWE-bench_Verified"
DATASET_REVISION = "78f471bf655a3137b2e8a75af1501690ec009ec3"
SPLIT = "test"

TIERS: dict[str, set[str]] = {
    "safe": {
        "django/django",
        "pallets/flask",
        "psf/requests",
        "pytest-dev/pytest",
        "pylint-dev/pylint",
        "sphinx-doc/sphinx",
        "sympy/sympy",
    },
    "likely": {
        "django/django",
        "pallets/flask",
        "psf/requests",
        "pytest-dev/pytest",
        "pylint-dev/pylint",
        "sphinx-doc/sphinx",
        "sympy/sympy",
        "astropy/astropy",
        "pydata/xarray",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tier",
        choices=("safe", "likely", "all"),
        default="safe",
        help="'safe' = pure-Python repos (default). "
        "'likely' = adds astropy/xarray. 'all' = no filter.",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        help="Override the tier allowlist with an explicit list of repos.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Take at most N instances from the filtered set (0 = no limit).",
    )
    parser.add_argument(
        "--per-repo",
        type=int,
        default=0,
        help="Take at most N instances per repo (0 = no per-repo cap).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write the selected instance IDs to a file, one per line.",
    )
    parser.add_argument(
        "--args",
        action="store_true",
        help="Print '--instance-id X' pairs ready to paste into the runner.",
    )
    return parser.parse_args()


def load_rows():
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit(
            "error: 'datasets' not installed. Run: uv sync --group benchmark"
        )
    return load_dataset(DATASET_NAME, split=SPLIT, revision=DATASET_REVISION)


def main() -> int:
    args = parse_args()

    allowed: set[str] | None
    if args.repos:
        allowed = set(args.repos)
    elif args.tier == "all":
        allowed = None
    else:
        allowed = TIERS[args.tier]

    rows = load_rows()
    all_by_repo: Counter[str] = Counter()
    picked: list[tuple[str, str]] = []
    per_repo: Counter[str] = Counter()

    for row in rows:
        repo = row["repo"]
        instance_id = row["instance_id"]
        all_by_repo[repo] += 1
        if allowed is not None and repo not in allowed:
            continue
        if args.per_repo and per_repo[repo] >= args.per_repo:
            continue
        picked.append((repo, instance_id))
        per_repo[repo] += 1
        if args.limit and len(picked) >= args.limit:
            break

    print(f"# Dataset: {DATASET_NAME}@{DATASET_REVISION[:8]} split={SPLIT}")
    print(f"# Total instances in dataset: {sum(all_by_repo.values())}")
    print(f"# Repos in dataset: {len(all_by_repo)}")
    print("# Full repo breakdown (instance count):")
    for repo, count in sorted(all_by_repo.items(), key=lambda kv: -kv[1]):
        mark = "  " if allowed is None or repo in allowed else "X "
        print(f"#   {mark}{count:4d}  {repo}")
    print(f"# Selected: {len(picked)} instances "
          f"(tier={args.tier}, limit={args.limit}, per_repo={args.per_repo})")
    print()

    if args.args:
        for _, instance_id in picked:
            print(f"--instance-id {instance_id}")
    else:
        for _, instance_id in picked:
            print(instance_id)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(iid for _, iid in picked) + "\n")
        print(f"\n# Wrote {len(picked)} instance IDs to {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
