"""Tests for the programmer-skill evaluation harness (scripts/eval_programmer_skill.py).

Fast and deterministic: no real LLM calls. The two functions that make live
calls (run_programmer_agent, call_judge) are only exercised indirectly, via
fakes injected into run_eval_for_fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import eval_programmer_skill as eval_mod

# ---------------------------------------------------------------------------
# discover_fixtures
# ---------------------------------------------------------------------------


def test_discover_fixtures_finds_valid_fixtures(tmp_path: Path) -> None:
    good = tmp_path / "good"
    (good / "workspace").mkdir(parents=True)
    (good / "workspace" / "a.py").write_text("x = 1\n")
    (good / "task.md").write_text("Do the thing.\n")

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "task.md").write_text("Missing workspace.\n")

    (tmp_path / "reports").mkdir()  # must be skipped, not treated as a fixture

    fixtures = eval_mod.discover_fixtures(tmp_path)

    assert [f.name for f in fixtures] == ["good"]
    assert fixtures[0].task == "Do the thing."


def test_discover_fixtures_returns_empty_list_for_empty_dir(tmp_path: Path) -> None:
    assert eval_mod.discover_fixtures(tmp_path) == []


# ---------------------------------------------------------------------------
# snapshot_files / diff_snapshots
# ---------------------------------------------------------------------------


def test_snapshot_files_captures_relative_contents(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("hello\n")
    (tmp_path / "sub" / "b.txt").write_text("world\n")

    snapshot = eval_mod.snapshot_files(tmp_path)

    assert snapshot == {"a.txt": "hello\n", "sub/b.txt": "world\n"}


def test_diff_snapshots_reports_only_changed_files() -> None:
    before = {"a.py": "x = 1\n", "unchanged.py": "same\n"}
    after = {"a.py": "x = 2\n", "unchanged.py": "same\n", "new.py": "y = 1\n"}

    diff = eval_mod.diff_snapshots(before, after)

    assert "a.py" in diff
    assert "new.py" in diff
    assert "unchanged.py" not in diff


def test_diff_snapshots_empty_when_nothing_changed() -> None:
    same = {"a.py": "x = 1\n"}
    assert eval_mod.diff_snapshots(same, dict(same)) == ""


# ---------------------------------------------------------------------------
# build_judge_prompt
# ---------------------------------------------------------------------------


def test_build_judge_prompt_includes_all_required_sections() -> None:
    prompt = eval_mod.build_judge_prompt(
        skill_markdown="## Checklist\n- Match naming conventions",
        task="Add a widget.",
        files_before={"a.py": "x = 1\n"},
        diff="--- a/a.py\n+++ b/a.py\n",
        agent_summary="I added a widget.",
    )

    assert "Match naming conventions" in prompt
    assert "Add a widget." in prompt
    assert "x = 1" in prompt
    assert "I added a widget." in prompt
    assert "overall_score" in prompt


# ---------------------------------------------------------------------------
# parse_judge_response
# ---------------------------------------------------------------------------


def test_parse_judge_response_parses_plain_json() -> None:
    raw = json.dumps(
        {
            "items": [
                {
                    "checklist_item": "naming",
                    "verdict": "followed",
                    "reason": "snake_case used",
                }
            ],
            "overall_score": 4,
        }
    )

    report = eval_mod.parse_judge_response(raw)

    assert report.overall_score == 4
    assert report.items == [eval_mod.JudgeItem("naming", "followed", "snake_case used")]
    assert report.raw_response == raw


def test_parse_judge_response_strips_markdown_code_fence() -> None:
    raw = '```json\n{"items": [], "overall_score": 3}\n```'

    report = eval_mod.parse_judge_response(raw)

    assert report.overall_score == 3
    assert report.items == []


def test_parse_judge_response_raises_on_malformed_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        eval_mod.parse_judge_response("not json at all")


# ---------------------------------------------------------------------------
# run_eval_for_fixture (orchestration, with fakes for the two live calls)
# ---------------------------------------------------------------------------


def test_run_eval_for_fixture_orchestrates_copy_run_diff_judge(tmp_path: Path) -> None:
    workspace = tmp_path / "fixture" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "a.py").write_text("x = 1\n")
    fixture = eval_mod.Fixture(name="demo", workspace_dir=workspace, task="Change a.py")

    captured_calls: dict[str, object] = {}

    def fake_agent_runner(*, workspace_dir: Path, task: str) -> eval_mod.AgentRunResult:
        captured_calls["workspace_dir"] = workspace_dir
        captured_calls["task"] = task
        # Simulate the agent editing a file inside the copied workspace.
        (workspace_dir / "a.py").write_text("x = 2\n")
        return eval_mod.AgentRunResult(summary="Changed x to 2.")

    def fake_judge_caller(prompt: str) -> str:
        captured_calls["judge_prompt"] = prompt
        return json.dumps({"items": [], "overall_score": 5})

    report = eval_mod.run_eval_for_fixture(
        fixture,
        agent_runner=fake_agent_runner,
        judge_caller=fake_judge_caller,
        skill_markdown="## Checklist\n- Do the thing",
    )

    # The agent ran against a temp copy, not the fixture's own workspace.
    assert captured_calls["workspace_dir"] != workspace
    assert captured_calls["task"] == "Change a.py"
    assert (workspace / "a.py").read_text() == "x = 1\n"  # fixture itself untouched

    assert report.fixture == "demo"
    assert report.agent_summary == "Changed x to 2."
    assert "x = 1" in report.diff and "x = 2" in report.diff
    assert report.judge.overall_score == 5
    assert "Do the thing" in captured_calls["judge_prompt"]


# ---------------------------------------------------------------------------
# write_report / format_report_text
# ---------------------------------------------------------------------------


def test_write_report_writes_valid_json(tmp_path: Path) -> None:
    report = eval_mod.EvalReport(
        fixture="demo",
        task="Do the thing.",
        agent_summary="Done.",
        diff="",
        judge=eval_mod.JudgeReport(
            overall_score=5,
            items=[eval_mod.JudgeItem("naming", "followed", "ok")],
            raw_response="{}",
        ),
        ran_at="2026-01-01T00:00:00+00:00",
    )

    out_path = eval_mod.write_report(report, reports_dir=tmp_path)

    assert out_path.exists()
    payload = json.loads(out_path.read_text())
    assert payload["fixture"] == "demo"
    assert payload["judge"]["overall_score"] == 5
    assert payload["judge"]["items"][0]["checklist_item"] == "naming"


def test_format_report_text_includes_score_and_items() -> None:
    report = eval_mod.EvalReport(
        fixture="demo",
        task="Do the thing.\nMore detail.",
        agent_summary="Done.",
        diff="",
        judge=eval_mod.JudgeReport(
            overall_score=4,
            items=[eval_mod.JudgeItem("naming", "violated", "used camelCase")],
            raw_response="{}",
        ),
        ran_at="2026-01-01T00:00:00+00:00",
    )

    text = eval_mod.format_report_text(report)

    assert "demo" in text
    assert "4/5" in text
    assert "naming" in text
    assert "used camelCase" in text


# ---------------------------------------------------------------------------
# Consistency check: eval harness must mirror production's programmer tools
# ---------------------------------------------------------------------------


def test_eval_tool_list_matches_production_programmer_subagent(tmp_path: Path) -> None:
    """Guards against the harness silently drifting from src/agents/programmer.py.

    The harness can't call create_programmer_subagent directly (it needs
    always-allow write permissions instead of interrupt-gated ones, so it can
    run unattended). It duplicates the tool/skills list instead. This test
    fails loudly if production's list ever changes without updating this
    module's PROGRAMMER_TOOLS / PROGRAMMER_SKILLS.
    """
    from deepagents.backends import FilesystemBackend

    from src.agents.programmer import create_programmer_subagent

    backend = FilesystemBackend(root_dir=tmp_path)
    spec = create_programmer_subagent("fake-model", backend)
    production_tools = sorted(t.name for t in spec["middleware"][0].tools)

    assert production_tools == sorted(eval_mod.PROGRAMMER_TOOLS)
    assert spec["skills"] == eval_mod.PROGRAMMER_SKILLS
