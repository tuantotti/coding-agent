# SWE-bench Local Evaluation Guide

This guide walks you through running the coding-agent against SWE-bench Verified
on a local machine (tested on Apple Silicon), using the two helper scripts in
this directory:

- [`benchmark_filter_instances.py`](benchmark_filter_instances.py) — pick a subset of
  instances likely to build on your hardware.
- [`benchmark_smoke_run.sh`](benchmark_smoke_run.sh) — print the exact command
  sequence to generate a patch for one instance at a time.

Nothing here spends money on its own. The filter script is pure metadata; the
wrapper only prints commands you copy-paste yourself.

Results produced by this workflow are **local SWE-bench Verified evaluations**,
not official leaderboard scores.

---

## Safety warning

The benchmark runner in [`benchmarks/`](../../benchmarks/) automatically
approves every file write and shell command the agent requests, and those
commands inherit network access. Read
[`benchmarks/README.md`](../../benchmarks/README.md) before running anything.
Prefer a disposable VM or container; if you must use your workstation, be
aware of the risk.

---

## Prerequisites

1. Repo is cloned and `.env` is populated with Azure OpenAI credentials:
   `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION`,
   `CODING_MODEL`.
2. Benchmark and dev dependencies installed:
   ```bash
   uv sync --group benchmark --group dev
   ```
3. Docker Desktop (or Colima) is running — required for the grading step.
4. You have at least ~5 GB of free disk for a smoke set (add more if you plan
   to evaluate many instances).

---

## Step 1 — Pick instances with `benchmark_filter_instances.py`

The full SWE-bench Verified dataset has 500 instances across 12 repositories.
Some of them (matplotlib, scikit-learn, numpy-heavy deps) are painful to build
on Apple Silicon. The filter script narrows the list to pure-Python repos.

**Tiers:**

| Tier       | Repos included                                                   |
| ---------- | ---------------------------------------------------------------- |
| `safe`   | django, flask, requests, pytest, pylint, sphinx, sympy (default) |
| `likely` | `safe` + astropy, xarray                                       |
| `all`    | Everything, no filter                                            |

**Common invocations:**

```bash
# Preview the full repo breakdown for the pinned dataset revision
uv run python tests/swebench/benchmark_filter_instances.py

# Take up to 20 instances from the safe tier, at most 3 per repo,
# and write to a file the wrapper will read.
uv run python tests/swebench/benchmark_filter_instances.py \
  --tier safe \
  --per-repo 3 \
  --limit 20 \
  --out .benchmark-results/arm_smoke.txt

# Single instance for a quick pipeline check
uv run python tests/swebench/benchmark_filter_instances.py \
  --limit 1 --out .benchmark-results/one.txt

# Explicit repo allowlist
uv run python tests/swebench/benchmark_filter_instances.py \
  --repos psf/requests pallets/flask --out .benchmark-results/tiny.txt
```

The dataset revision is pinned inside the script
(`78f471bf655a3137b2e8a75af1501690ec009ec3`). Do not change it without
regenerating any prior `--run-id` — see the reproducibility note at the end.

---

## Step 2 — Start the coding-agent API in benchmark-safe mode

Open **terminal A** and keep it running for the whole session:

```bash
export CODING_WEB_SEARCH_ENABLED=false
export LANGSMITH_TRACING=false
export LANGFUSE_TRACING_ENABLED=false
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
```

The runner refuses to start if the API reports web search enabled — this is a
guardrail to prevent the agent from Googling for the upstream patch.

---

## Step 3 — Verify the API is safe

From **terminal B**:

```bash
curl --fail --silent http://127.0.0.1:8000/v1/benchmark-config | python -m json.tool
```

Expected response:

```json
{
  "model": "azure_openai:gpt-4.1-mini",
  "max_remediation_cycles": 2,
  "shell_timeout_seconds": 120,
  "web_search_enabled": false
}
```

Confirm `"web_search_enabled": false` and that `model` matches what you plan
to publish. Use the exact `model` string as `--model-label` in the next step.

---

## Step 4 — Generate a patch for ONE instance

The wrapper script targets one instance per invocation. This is deliberate —
the runner's manifest is per-`run_id`, and mixing instances under a shared
`run_id` triggers a validation error.

**List available instances:**

```bash
tests/swebench/benchmark_smoke_run.sh
```

Prints a numbered list from `.benchmark-results/arm_smoke.txt`.

**Print the plan for instance #4:**

```bash
tests/swebench/benchmark_smoke_run.sh 4
```

**Or pick by full instance id:**

```bash
tests/swebench/benchmark_smoke_run.sh pallets__flask-5014
```

**Override the auto-derived `run_id`:**

```bash
tests/swebench/benchmark_smoke_run.sh 4 my-custom-run-id
```

The wrapper prints, but does not run, the six-step command sequence. Copy the
`uv run python -m benchmarks.swebench generate ...` block into terminal B and
run it. Predictions land under
`.benchmark-results/<run-id>/predictions.jsonl`.

**Wrapper environment overrides (all optional):**

| Variable          | Default                              | Purpose                               |
| ----------------- | ------------------------------------ | ------------------------------------- |
| `INSTANCE_FILE` | `.benchmark-results/arm_smoke.txt` | Where to read the instance list       |
| `MODEL_LABEL`   | `azure_openai:gpt-4.1-mini`        | Written into`predictions.jsonl`     |
| `API_URL`       | `http://127.0.0.1:9080`            | Host address; port must match Uvicorn |

Example:

```bash
INSTANCE_FILE=.benchmark-results/one.txt MODEL_LABEL=azure_openai:gpt-5 \
  tests/swebench/benchmark_smoke_run.sh 1
```

---

## Step 5 — Stop the API before exporting the gold dataset

The gold dataset contains the reference patch and the grading tests. If the
API is still running while the file is on disk, the agent's auto-approved
shell commands can read it and cheat.

In terminal A, press **Ctrl-C** to stop Uvicorn. Then:

```bash
uv run python -c 'from datasets import load_dataset; \
  load_dataset("SWE-bench/SWE-bench_Verified", split="test", \
  revision="78f471bf655a3137b2e8a75af1501690ec009ec3") \
  .to_json(".benchmark-results/swe-bench-verified-78f471bf.jsonl")'
```

This file is reusable across grading runs for the same dataset revision.

---

## Step 6 — Grade with the official SWE-bench harness

Grading uses Docker. On Apple Silicon, pass `--namespace ''` to make the
harness build images locally for arm64 instead of pulling amd64-only images
from the registry. First build per repo can take 5–15 minutes.

```bash
uv run python -m swebench.harness.run_evaluation \
  --dataset_name .benchmark-results/swe-bench-verified-78f471bf.jsonl \
  --split test \
  --predictions_path .benchmark-results/smoke-pallets-flask-5014/predictions.jsonl \
  --run_id smoke-pallets-flask-5014 \
  --namespace '' \
  --max_workers 1
```

Report file: `<model_label>.<run_id>.json`.

---

## Step 7 — Iterate

To try another instance safely:

```bash
# Wipe the gold file first so a re-started API cannot read it
rm .benchmark-results/swe-bench-verified-*.jsonl

# Restart terminal A with the same commands from Step 2
# Then in terminal B:
tests/swebench/benchmark_smoke_run.sh 5   # next instance
```

Each instance gets its own `.benchmark-results/<run-id>/` folder, so runs
never overwrite each other.

---

## Reading the harness output

A representative report line:

```
Total instances: 500
Instances submitted: 1
Instances completed: 0
Instances incomplete: 499
Instances resolved: 0
Instances unresolved: 0
Instances with empty patches: 1
Instances with errors: 0
```

Only these three numbers matter for a one-instance smoke run:

- **Instances submitted** — count of rows in your predictions file.
- **Instances with empty patches** — the agent finished but produced no diff.
  Investigate: `.benchmark-results/<run-id>/instances/<id>/attempt-001/result.json`
  and `events.jsonl`. Common causes are agent-behavior bugs, not infra.
- **Instances resolved / unresolved** — the grading verdict.

Ignore `Instances incomplete: 499`. The harness counts against the full
dataset; you only submitted one prediction, so 499 are "not attempted".
