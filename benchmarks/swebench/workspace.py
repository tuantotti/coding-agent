"""Create clean, commit-pinned workspaces from a reusable bare cache."""

import subprocess
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from benchmarks.swebench.models import BenchmarkInstance


class WorkspaceError(RuntimeError):
    """A repository cache or checkout operation failed."""


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkspaceError("Unable to execute Git.") from exc
    if result.returncode:
        raise WorkspaceError(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


def _github_remote(instance: BenchmarkInstance) -> str:
    return f"https://github.com/{instance.repo}.git"


class WorkspaceManager:
    """Own the repository cache and fresh checkout lifecycle."""

    def __init__(
        self,
        cache_root: Path,
        *,
        remote_url: Callable[[BenchmarkInstance], str] = _github_remote,
    ) -> None:
        """Configure the cache root and repository URL resolver."""
        self.cache_root = cache_root
        self.remote_url = remote_url

    def prepare(self, instance: BenchmarkInstance, attempt_dir: Path) -> Path:
        """Return a clean checkout detached at the requested base commit."""
        logger.info(
            "Preparing workspace instance={} repo={} commit={}",
            instance.instance_id,
            instance.repo,
            instance.base_commit,
        )
        repos = self.cache_root / "repos"
        repos.mkdir(parents=True, exist_ok=True)
        cache = repos / f"{instance.repo.replace('/', '__')}.git"
        if not cache.exists():
            logger.info("Cloning repository={} into cache={}", instance.repo, cache)
            _git("clone", "--bare", self.remote_url(instance), str(cache))
        try:
            _git("cat-file", "-e", f"{instance.base_commit}^{{commit}}", cwd=cache)
        except WorkspaceError:
            logger.info(
                "Fetching missing commit={} repo={}",
                instance.base_commit,
                instance.repo,
            )
            _git("fetch", "--prune", "origin", instance.base_commit, cwd=cache)

        workspace = attempt_dir / "workspace"
        if workspace.exists() and any(workspace.iterdir()):
            raise WorkspaceError(f"Workspace is not empty: {workspace}")
        workspace.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--no-hardlinks", "--no-checkout", str(cache), str(workspace))
        _git("checkout", "--detach", instance.base_commit, cwd=workspace)
        if _git("rev-parse", "HEAD", cwd=workspace) != instance.base_commit:
            raise WorkspaceError("Workspace HEAD does not match base_commit.")
        if _git("status", "--porcelain", cwd=workspace):
            raise WorkspaceError("Prepared workspace is not clean.")
        logger.info(
            "Workspace ready instance={} path={}", instance.instance_id, workspace
        )
        return workspace
