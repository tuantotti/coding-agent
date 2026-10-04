# SWE-bench evaluation

This directory runs the coding agent against
[SWE-bench Verified](https://www.swebench.com/) and grades its patches with the
official Docker harness. Results are local evaluations, not official
leaderboard scores.

## Safety

> [!CAUTION]
> The benchmark runner automatically approves agent file writes and shell
> commands. Run it in a disposable container or virtual machine with
> benchmark-only credentials. Do not expose secrets or valuable host paths.

The runner requires web search to be disabled. Run the API and benchmark in the
same filesystem namespace because the runner sends workspace paths to the API.
Use one API worker; the server supports one unfinished run at a time.

## Setup

From the repository root:

```bash
uv sync --group benchmark --group dev
cp .env.example .env
```

Configure `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`,
`OPENAI_API_VERSION`, and `CODING_MODEL` in `.env`.

Start the API:

```bash
export CODING_WEB_SEARCH_ENABLED=false
export LANGSMITH_TRACING=false
export LANGFUSE_TRACING_ENABLED=false
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Verify that `web_search_enabled` is `false` and that `model` matches the label
you will use for the run:

```bash
curl --fail --silent http://127.0.0.1:8000/v1/benchmark-config
```

## Generate predictions

Start with one instance:

```bash
uv run python -m benchmarks.swebench generate \
  --api-url http://127.0.0.1:8000 \
  --output .benchmark-results \
  --run-id agent-gpt54nano-verified-smoke \
  --dataset-revision 78f471bf655a3137b2e8a75af1501690ec009ec3 \
  --model-label coding-agent-gpt-5.4-nano \
  --instance-id sympy__sympy-20590 \
  --acknowledge-auto-approval-risk
```

Repeat `--instance-id` to select more instances, or use `--all` for the full
dataset. Rerunning the command skips completed attempts. Add
`--retry-failures` to retry failed attempts, and use a new run ID whenever the
model, prompt, configuration, dataset revision, or generated patches change.

Each run is written to `.benchmark-results/<run-id>/`:

```text
.benchmark-results/<run-id>/
├── manifest.json
├── predictions.jsonl
└── instances/<instance-id>/attempt-001/
    ├── request.json
    ├── events.jsonl
    ├── approvals.jsonl
    ├── patch.diff
    └── result.json
```

Failed generation attempts remain in `predictions.jsonl` with an empty patch so
the evaluation denominator is preserved.

## Grade predictions

Stop the coding-agent API before exporting the grading dataset, which contains
gold answers. Export the same pinned revision used during generation:

```bash
uv run python -c 'from datasets import load_dataset; load_dataset("SWE-bench/SWE-bench_Verified", split="test", revision="78f471bf655a3137b2e8a75af1501690ec009ec3").to_json(".benchmark-results/swe-bench-verified-78f471bf.jsonl")'
```

With Docker running, evaluate a run using the helper script:

```bash
bash benchmarks/eval.sh agent-gpt54nano-verified-smoke
```

The script evaluates nonempty patches one at a time. For each instance it pulls
the official `linux/amd64` image, runs the harness, removes the image, and
refreshes the combined report. Completed instances are skipped when the script
is resumed. Pressing Ctrl+C preserves completed instance reports and refreshes
the combined report before exiting.

Detailed instance reports are stored under:

```text
logs/run_evaluation/<run-id>/<model-label>/<instance-id>/report.json
```

The combined report is written in the repository root:

```text
<model-label>.<run-id>.json
```

SWE-bench images and tests are resource intensive. Plan for at least 16 GB of
RAM and substantial free disk space. Apple Silicon uses AMD64 emulation and may
run considerably slower.

For methodology and publication guidance, see the
[SWE-bench evaluation guide](../docs/swebench-evaluation.md).
