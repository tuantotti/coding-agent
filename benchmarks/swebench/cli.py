"""Command-line entry point for SWE-bench patch generation."""

import argparse
import asyncio
import platform
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from benchmarks.swebench.api import (
    AgentApiClient,
    AgentApiError,
    BenchmarkServerSettings,
)
from benchmarks.swebench.artifacts import ArtifactError, ArtifactStore, RunManifest
from benchmarks.swebench.config import BenchmarkConfig
from benchmarks.swebench.dataset import DatasetError, load_instances
from benchmarks.swebench.prompt import prompt_template_sha256
from benchmarks.swebench.runner import BenchmarkRunner
from benchmarks.swebench.workspace import WorkspaceManager


def build_parser() -> argparse.ArgumentParser:
    """Build the public benchmark command parser."""
    parser = argparse.ArgumentParser(prog="python -m benchmarks.swebench")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="generate SWE-bench predictions")
    generate.add_argument("--api-url", default="http://127.0.0.1:8000")
    generate.add_argument("--output", type=Path, default=Path(".benchmark-results"))
    generate.add_argument("--cache", type=Path)
    generate.add_argument("--run-id", required=True)
    generate.add_argument("--model-label", required=True)
    generate.add_argument(
        "--dataset-name", default="SWE-bench/SWE-bench_Verified"
    )
    generate.add_argument("--split", default="test")
    generate.add_argument("--dataset-revision")
    selection = generate.add_mutually_exclusive_group(required=True)
    selection.add_argument("--instance-id", action="append", default=[])
    selection.add_argument("--all", action="store_true", dest="all_instances")
    generate.add_argument("--instance-timeout-seconds", type=float, default=3600)
    generate.add_argument("--poll-interval-seconds", type=float, default=1)
    generate.add_argument("--max-patch-bytes", type=int, default=10_000_000)
    generate.add_argument("--retry-failures", action="store_true")
    generate.add_argument(
        "--acknowledge-auto-approval-risk", action="store_true", required=True
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    output = args.output.resolve()
    cache = (args.cache or output / "cache").resolve()
    return BenchmarkConfig(
        api_url=args.api_url,
        output_root=output,
        cache_root=cache,
        run_id=args.run_id,
        model_label=args.model_label,
        dataset_name=args.dataset_name,
        split=args.split,
        dataset_revision=args.dataset_revision,
        instance_ids=tuple(args.instance_id),
        all_instances=args.all_instances,
        instance_timeout_seconds=args.instance_timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        max_patch_bytes=args.max_patch_bytes,
        retry_failures=args.retry_failures,
        acknowledge_auto_approval_risk=args.acknowledge_auto_approval_risk,
    )


def _git_value(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _manifest(
    config, selection, server_settings: BenchmarkServerSettings
) -> RunManifest:
    project_root = Path(__file__).resolve().parents[2]
    return RunManifest(
        run_id=config.run_id,
        dataset_name=selection.dataset_name,
        split=selection.split,
        requested_revision=selection.requested_revision,
        resolved_revision=selection.resolved_revision,
        instance_ids=tuple(item.instance_id for item in selection.instances),
        model_label=config.model_label,
        api_url=config.api_url,
        agent_git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        agent_git_dirty=bool(_git_value(project_root, "status", "--porcelain")),
        prompt_template_sha256=prompt_template_sha256(),
        instance_timeout_seconds=config.instance_timeout_seconds,
        poll_interval_seconds=config.poll_interval_seconds,
        max_patch_bytes=config.max_patch_bytes,
        agent_settings={
            "CODING_MODEL": server_settings.model,
            "CODING_MAX_REMEDIATION_CYCLES": (
                server_settings.max_remediation_cycles
            ),
            "CODING_SHELL_TIMEOUT_SECONDS": server_settings.shell_timeout_seconds,
            "CODING_WEB_SEARCH_ENABLED": server_settings.web_search_enabled,
        },
        python_version=sys.version,
        platform=platform.platform(),
        started_at=datetime.now(timezone.utc).isoformat(),
    )


async def async_main(argv: Sequence[str] | None = None) -> int:
    """Parse, validate, and run one generation command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _config_from_args(args)
        print(
            "WARNING: benchmark mode automatically approves agent writes and shell "
            "commands. Run the API in a disposable container or VM.",
            file=sys.stderr,
        )
        selection = load_instances(config)
        async with AgentApiClient(
            config.api_url,
            poll_interval_seconds=config.poll_interval_seconds,
        ) as api_client:
            server_settings = await api_client.require_benchmark_safe()
            artifacts = ArtifactStore(config.output_root / config.run_id)
            artifacts.initialize(_manifest(config, selection, server_settings))
            runner = BenchmarkRunner(
                config,
                selection,
                WorkspaceManager(config.cache_root),
                api_client,
                artifacts,
            )
            summary = await runner.run()
        artifacts.finalize(datetime.now(timezone.utc).isoformat())
    except (
        ValidationError,
        DatasetError,
        ArtifactError,
        AgentApiError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Predictions: {summary.predictions_path}")
    print(f"Completed: {summary.completed}/{summary.total}")
    return 0 if summary.attempted or summary.skipped else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the async command from a synchronous console entry point."""
    return asyncio.run(async_main(argv))
