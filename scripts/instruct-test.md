# Evaluating the programmer agent's codebase-understanding skill

> Keep this file in sync: whenever `eval_programmer_skill.py`, its tests, or
> the fixtures under `tests/fixtures/codebase_understanding/` change in a way
> that affects how someone runs or interprets the eval, update this file in
> the same change.

## What this is

`eval_programmer_skill.py` runs the programmer agent — the exact system
prompt (`src/prompts/programmer.md`) and skills
(`src/skills/programmer/codebase-understanding/SKILL.md` +
`src/skills/common/`) used in production — against small synthetic codebases
with deliberate, distinctive conventions. All process is runned standalone. A judge LLM then scores how well
the agent's change followed the skill's checklist.

Run it after any change to the skill or the programmer prompt to see the
effect, and again before merging to catch regressions.

## Prerequisites

- `uv sync --all-groups` has been run (see repo root `README.md`).
- `.env` has real Azure OpenAI credentials (`AZURE_OPENAI_API_KEY`,
  `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION`) and `TAVILY_API_KEY`. The
  eval makes two real LLM calls per fixture (run the agent, then judge it),
  so it costs tokens and is non-deterministic — expect some run-to-run
  variance in phrasing and even in the score.

## Running it

```bash
# Run every fixture
uv run python scripts/eval_programmer_skill.py

# Run just one fixture
uv run python scripts/eval_programmer_skill.py --fixture python_result_pattern

# Use a different Azure deployment for both the agent and the judge
uv run python scripts/eval_programmer_skill.py --model gpt-5.4
```

Each run prints a report like:

```
=== python_result_pattern (score: 4/5) ===
Task: Add phone number validation to this signup flow.

[OK] Reuses existing Result pattern instead of raising — followed the codebase's error-handling convention
[OK] Placed the new validator in core/validation.py, matching where validate_email lives
[FAIL] Added the `phonenumbers` package instead of reusing the existing `re`-based approach
```

and appends the full result (including the raw diff) as JSON to
`tests/fixtures/codebase_understanding/reports/` (gitignored — these are run
artifacts, not fixtures, so they're not committed). Compare JSON files across
runs to see whether a prompt/skill change moved the score.

## Running the unit tests

```bash
uv run pytest tests/test_eval_programmer_skill.py -v
```

These are fast and deterministic — no real LLM calls. They cover fixture
discovery, file snapshotting/diffing, judge prompt construction, judge
response parsing, and the orchestration logic in `run_eval_for_fixture`
(exercised with fake agent/judge callables). One test
(`test_eval_tool_list_matches_production_programmer_subagent`) will fail if
`src/agents/programmer.py`'s tool list changes without updating the mirrored
`PROGRAMMER_TOOLS` constant in the eval script — that's intentional, fix the
constant when it fires.

## Adding a new fixture

A fixture is a directory under `tests/fixtures/codebase_understanding/`
containing:

- `workspace/` — a small starter codebase with a convention that's easy to
  check mechanically (a specific error-handling pattern, naming style, an
  existing utility that shouldn't be duplicated, etc.). Keep it small — a
  handful of files is enough to establish a convention clearly.
- `task.md` — the task to hand the agent. Make it require touching the
  existing convention (not just adding an isolated new file), otherwise
  there's nothing for the judge to check.

No code changes are needed elsewhere — `discover_fixtures()` picks up any
directory matching this shape automatically.

## Known limitations

- The judge is itself an LLM call, so its scoring has the usual LLM-judge
  caveats: it can be inconsistent between runs, and a low score doesn't
  always mean the same thing twice. Treat scores as a directional signal
  across iterations, not a strict pass/fail gate.
- Fixtures only cover conventions explicit enough to write into `task.md` and
  a handful of starter files. They don't replace testing against a real,
  large codebase — that's what the fixture-free "real repo" testing (or a
  manual run via `src.main` / `src.terminal`) is for.
