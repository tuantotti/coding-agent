"""Evaluation harness for the programmer agent's codebase-understanding skill.

Runs the programmer agent — the same system prompt and skills as production —
against small synthetic fixtures with distinctive, deliberate conventions,
then asks a judge LLM to score how well it followed the codebase-understanding
skill's checklist. Meant to be re-run after every change to the skill or the
programmer prompt, to catch regressions and see the effect of a change.

Usage:
    uv run python scripts/eval_programmer_skill.py [--fixture NAME] [--model DEPLOYMENT]

Requires the same environment as the rest of the app (.env with Azure OpenAI
credentials) since it makes two real LLM calls per fixture: one to run the
programmer agent, one to judge its output.
"""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "codebase_understanding"
REPORTS_DIR = FIXTURES_DIR / "reports"
SKILL_PATH = (
    REPO_ROOT
    / "src"
    / "skills"
    / "programmer"
    / "codebase-understanding"
    / "SKILL.md"
)

# Mirrors src/agents/programmer.py's create_programmer_subagent. Kept as a
# separate constant (not imported) because the eval harness needs always-allow
# write permissions instead of interrupt-gated ones, to run unattended;
# test_eval_programmer_skill.py asserts this stays in sync with production.
PROGRAMMER_TOOLS = [
    "ls",
    "read_file",
    "glob",
    "grep",
    "write_file",
    "edit_file",
    "delete",
]
PROGRAMMER_SKILLS = ["/agent_skills/common", "/agent_skills/programmer"]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Fixture:
    """A synthetic codebase plus the task to hand the programmer agent."""

    name: str
    workspace_dir: Path
    task: str


@dataclass(slots=True, frozen=True)
class AgentRunResult:
    """What the programmer agent reported after attempting the task."""

    summary: str


@dataclass(slots=True, frozen=True)
class JudgeItem:
    """One checklist item's verdict from the judge LLM."""

    checklist_item: str
    verdict: str  # "followed" | "violated" | "not_applicable"
    reason: str


@dataclass(slots=True, frozen=True)
class JudgeReport:
    """The judge LLM's full assessment of one run."""

    overall_score: int  # 1-5
    items: list[JudgeItem]
    raw_response: str


@dataclass(slots=True, frozen=True)
class EvalReport:
    """One fixture's complete evaluation result."""

    fixture: str
    task: str
    agent_summary: str
    diff: str
    judge: JudgeReport
    ran_at: str


class AgentRunner(Protocol):
    """Runs the programmer agent against a workspace; injectable for tests."""

    def __call__(self, *, workspace_dir: Path, task: str) -> AgentRunResult:
        """Run the agent against workspace_dir with the given task."""
        ...


class JudgeCaller(Protocol):
    """Calls the judge LLM with a prompt; injectable for tests."""

    def __call__(self, prompt: str) -> str:
        """Call the judge model and return its raw text response."""
        ...


# ---------------------------------------------------------------------------
# Fixture discovery and file snapshotting
# ---------------------------------------------------------------------------


def discover_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> list[Fixture]:
    """Find every fixture directory containing a workspace/ and task.md."""
    if not fixtures_dir.is_dir():
        return []
    fixtures = []
    for entry in sorted(fixtures_dir.iterdir()):
        if not entry.is_dir() or entry.name == "reports":
            continue
        workspace = entry / "workspace"
        task_file = entry / "task.md"
        if workspace.is_dir() and task_file.is_file():
            fixtures.append(
                Fixture(
                    name=entry.name,
                    workspace_dir=workspace,
                    task=task_file.read_text(encoding="utf-8").strip(),
                )
            )
    return fixtures


def snapshot_files(root: Path) -> dict[str, str]:
    """Return a relative-path -> content map of every file under root."""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel_path = path.relative_to(root).as_posix()
            snapshot[rel_path] = path.read_text(encoding="utf-8")
    return snapshot


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> str:
    """Build a unified diff covering every file that changed, was added, or removed."""
    chunks = []
    for path in sorted(set(before) | set(after)):
        before_text = before.get(path, "")
        after_text = after.get(path, "")
        if before_text == after_text:
            continue
        chunks.extend(
            difflib.unified_diff(
                before_text.splitlines(keepends=True),
                after_text.splitlines(keepends=True),
                fromfile=f"a/{path}" if path in before else "/dev/null",
                tofile=f"b/{path}" if path in after else "/dev/null",
            )
        )
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Judge prompt construction and response parsing
# ---------------------------------------------------------------------------


def build_judge_prompt(
    *,
    skill_markdown: str,
    task: str,
    files_before: dict[str, str],
    diff: str,
    agent_summary: str,
) -> str:
    """Compose the judge prompt: skill checklist, task, before-state, diff, summary."""
    before_listing = "\n\n".join(
        f"### {path}\n```\n{content}\n```"
        for path, content in sorted(files_before.items())
    )
    return f"""You are grading whether a coding agent followed the skill below when \
completing the task in an existing codebase.

## Skill definition (the checklist to grade against)
{skill_markdown}

## Task given to the agent
{task}

## Codebase before the change
{before_listing}

## Diff produced by the agent
```diff
{diff or "(no changes)"}
```

## Agent's own summary of what it did
{agent_summary}

## Your job
For each concrete, checkable item in the skill's checklist, decide whether the \
agent's change followed it, violated it, or the item does not apply to this task. \
Then give an overall adherence score from 1 (ignored the skill) to 5 (fully \
matched every applicable convention).

Respond with ONLY a JSON object of this exact shape, no prose outside it:
{{
  "items": [
    {{
      "checklist_item": "...",
      "verdict": "followed|violated|not_applicable",
      "reason": "..."
    }}
  ],
  "overall_score": 1-5
}}
"""


def parse_judge_response(raw_text: str) -> JudgeReport:
    """Parse the judge LLM's JSON response into a JudgeReport."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json") :]
        text = text.strip()
    data = json.loads(text)
    items = [
        JudgeItem(
            checklist_item=item["checklist_item"],
            verdict=item["verdict"],
            reason=item["reason"],
        )
        for item in data["items"]
    ]
    return JudgeReport(
        overall_score=int(data["overall_score"]),
        items=items,
        raw_response=raw_text,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_eval_for_fixture(
    fixture: Fixture,
    *,
    agent_runner: AgentRunner,
    judge_caller: JudgeCaller,
    skill_markdown: str | None = None,
) -> EvalReport:
    """Run one fixture end-to-end: copy workspace, run agent, diff, judge."""
    if skill_markdown is None:
        skill_markdown = SKILL_PATH.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix=f"ua-eval-{fixture.name}-") as tmp:
        run_dir = Path(tmp) / "workspace"
        shutil.copytree(fixture.workspace_dir, run_dir)
        files_before = snapshot_files(run_dir)

        result = agent_runner(workspace_dir=run_dir, task=fixture.task)

        files_after = snapshot_files(run_dir)
        diff = diff_snapshots(files_before, files_after)

        prompt = build_judge_prompt(
            skill_markdown=skill_markdown,
            task=fixture.task,
            files_before=files_before,
            diff=diff,
            agent_summary=result.summary,
        )
        judge_report = parse_judge_response(judge_caller(prompt))

    return EvalReport(
        fixture=fixture.name,
        task=fixture.task,
        agent_summary=result.summary,
        diff=diff,
        judge=judge_report,
        ran_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def write_report(report: EvalReport, reports_dir: Path = REPORTS_DIR) -> Path:
    """Persist an EvalReport as a timestamped JSON file; return the written path."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.ran_at.replace(":", "").replace("+00:00", "Z")
    out_path = reports_dir / f"{report.fixture}-{stamp}.json"
    payload = {
        "fixture": report.fixture,
        "task": report.task,
        "agent_summary": report.agent_summary,
        "diff": report.diff,
        "ran_at": report.ran_at,
        "judge": {
            "overall_score": report.judge.overall_score,
            "items": [
                {
                    "checklist_item": item.checklist_item,
                    "verdict": item.verdict,
                    "reason": item.reason,
                }
                for item in report.judge.items
            ],
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def format_report_text(report: EvalReport) -> str:
    """Render a human-readable report for stdout."""
    marker_by_verdict = {"followed": "OK", "violated": "FAIL", "not_applicable": "n/a"}
    lines = [
        f"=== {report.fixture} (score: {report.judge.overall_score}/5) ===",
        f"Task: {report.task.splitlines()[0]}",
        "",
    ]
    for item in report.judge.items:
        marker = marker_by_verdict.get(item.verdict, "?")
        lines.append(f"[{marker}] {item.checklist_item} — {item.reason}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live implementations (not exercised by unit tests)
# ---------------------------------------------------------------------------


def run_programmer_agent(
    *, workspace_dir: Path, task: str, model_deployment: str
) -> AgentRunResult:
    """Invoke a standalone deep agent configured like the production programmer.

    Same system prompt and skills as ``create_programmer_subagent``, but with
    write access always allowed instead of interrupt-gated, so it can
    complete a task unattended.
    """
    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import CompositeBackend, FilesystemBackend

    from src.agents.config import filesystem_middleware
    from src.models.llms import create_azure_model
    from src.prompts import load_prompt

    eval_write_permissions = [
        FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
        FilesystemPermission(
            operations=["write"], paths=["/agent_skills/**"], mode="deny"
        ),
        FilesystemPermission(operations=["write"], paths=["/**"], mode="allow"),
    ]

    skills_root = REPO_ROOT / "src" / "skills"
    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=workspace_dir, virtual_mode=False),
        routes={"/agent_skills/": FilesystemBackend(root_dir=skills_root)},
    )
    model = create_azure_model(deployment=model_deployment)
    agent = create_deep_agent(
        model=model,
        system_prompt=load_prompt("programmer"),
        middleware=[
            filesystem_middleware(backend, PROGRAMMER_TOOLS, eval_write_permissions)
        ],
        permissions=eval_write_permissions,
        backend=backend,
        skills=PROGRAMMER_SKILLS,
        name="programmer_eval",
    )
    response = agent.invoke({"messages": [{"role": "user", "content": task}]})
    return AgentRunResult(summary=response["messages"][-1].content)


def call_judge(prompt: str, *, model_deployment: str) -> str:
    """Call the judge LLM with the composed grading prompt."""
    from src.models.llms import create_azure_model

    model = create_azure_model(deployment=model_deployment)
    response = model.invoke(prompt)
    return response.content


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the eval for every fixture (or one, via --fixture), print + save reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", help="Run only the fixture with this name.")
    parser.add_argument(
        "--model",
        default="gpt-5.4",
        help="Azure deployment name used for both the agent and the judge.",
    )
    args = parser.parse_args()

    fixtures = discover_fixtures()
    if args.fixture:
        fixtures = [f for f in fixtures if f.name == args.fixture]
        if not fixtures:
            raise SystemExit(f"No fixture named {args.fixture!r} under {FIXTURES_DIR}")
    if not fixtures:
        raise SystemExit(f"No fixtures found under {FIXTURES_DIR}")

    for fixture in fixtures:
        report = run_eval_for_fixture(
            fixture,
            agent_runner=lambda *, workspace_dir, task: run_programmer_agent(
                workspace_dir=workspace_dir, task=task, model_deployment=args.model
            ),
            judge_caller=lambda prompt: call_judge(prompt, model_deployment=args.model),
        )
        print(format_report_text(report))
        out_path = write_report(report)
        print(f"Saved: {out_path}\n")


if __name__ == "__main__":
    main()
