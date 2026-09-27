# Benchmarks

This directory contains the local evaluation tooling for running the coding
agent against [SWE-bench Verified](https://www.swebench.com/). The runner uses
the public coding-agent HTTP API to generate patches and writes predictions in
the format expected by the official SWE-bench harness.

Results produced by this workflow are **local SWE-bench Verified evaluations**,
not official leaderboard scores.

## Safety warning

> [!CAUTION]
> The benchmark runner automatically approves every file write and shell command
> requested by the agent. Run the API and benchmark inside a disposable
> container or virtual machine, never on a valuable host filesystem. Approved
> commands inherit the API environment and retain network access, so use
> benchmark-only, least-privilege credentials and restrict egress where
> practical.

The runner refuses to start unless the API reports that web search is disabled.
It also records the effective model, remediation limit, shell timeout, and
web-search state in the run manifest. Disable external tracing unless exporting
benchmark prompts, code, and command output is intentional. Do not mount
valuable host directories or secrets into the runtime.

The runner sends checkout paths to the API rather than uploading files. Run the
runner and API in the same filesystem namespace, or provide a shared mount at
identical absolute paths. Use one API worker because the server allows only one
unfinished run at a time.

Official grading uses Docker. A full evaluation may require at least 16 GB of
RAM and 120 GB of free disk space.

## Install the benchmark dependencies

From the repository root:

```bash
uv sync --group benchmark --group dev
cp .env.example .env
```

Configure `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`,
`OPENAI_API_VERSION`, and `CODING_MODEL` in `.env`. Use benchmark-only Azure
credentials where possible. The `--model-label` and `--run-id` used below must
describe the effective `CODING_MODEL`; confirm it through the benchmark-config
endpoint before starting a run.

## Start the API in benchmark-safe mode

Disable web search and start a single API worker inside the disposable runtime:

```bash
export CODING_WEB_SEARCH_ENABLED=false
export LANGSMITH_TRACING=false
export LANGFUSE_TRACING_ENABLED=false
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Verify the effective settings before generating predictions:

```bash
curl --fail --silent http://127.0.0.1:8000/v1/benchmark-config
```

The response must contain `"web_search_enabled":false`. Confirm that its
`model` value also matches the label you intend to publish.

## Run one Verified instance

Start with a single-instance plumbing run before attempting a larger
evaluation. The dataset revision below was resolved on 2026-09-27 and is pinned
to keep the inputs reproducible:

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

By default, rerunning the same command skips every instance that already has a
terminal attempt artifact, including failed attempts. Add `--retry-failures` to
create a new attempt for failed instances; completed instances remain skipped.
If the runner exits while an API run is still active or awaiting approval,
restart the disposable API to clear that in-memory run before rerunning the
command. Use a new `--run-id` after changing the dataset revision, model label,
agent commit, prompt, effective configuration, or selected instances.

To evaluate several instances, repeat `--instance-id`. To generate predictions
for the complete dataset, replace the instance selection with `--all`; a full
run requires an immutable 40-character dataset commit SHA.

## Inspect the generated artifacts

Each run is stored under `.benchmark-results/<run-id>/`:

```text
.benchmark-results/<run-id>/
├── manifest.json
├── predictions.jsonl
└── instances/
    └── <instance-id>/
        └── attempt-001/
            ├── request.json
            ├── events.jsonl       # Created when events are observed
            ├── approvals.jsonl    # Created when approvals are observed
            ├── patch.diff
            └── result.json
```

- `manifest.json` records the pinned dataset, agent identity, prompt checksum,
  and selected effective settings.
- `instances/` contains each attempt's request, result, and patch, plus event and
  approval logs when those records were observed.
- `predictions.jsonl` contains the official three-field prediction rows. Failed
  attempts remain present with an empty patch so the denominator is preserved.

Benchmark output is excluded from Git through `/.benchmark-results/`.

## Materialize the pinned grading dataset

The official harness does not accept a Hugging Face dataset revision. After
prediction generation is complete, stop the coding-agent API so the agent cannot
access gold fields, then export the same pinned dataset revision to a local JSON
file:

```bash
uv run python -c 'from datasets import load_dataset; load_dataset("SWE-bench/SWE-bench_Verified", split="test", revision="78f471bf655a3137b2e8a75af1501690ec009ec3").to_json(".benchmark-results/swe-bench-verified-78f471bf.jsonl")'
```

This file contains gold grading fields. Create and use it only in a separate
grading runtime or storage location that is not mounted into the generation
runtime. Approved agent commands are not filesystem-sandboxed, so merely placing
the file outside an agent workspace does not protect it. If the same disposable
runtime must be reused, remove the exported dataset and any other gold-bearing
grading inputs before restarting the coding-agent API.

## Grade with the official harness

With Docker running, grade the generated predictions using the official
SWE-bench harness:

```bash
uv run python -m swebench.harness.run_evaluation \
  --dataset_name .benchmark-results/swe-bench-verified-78f471bf.jsonl \
  --split test \
  --predictions_path .benchmark-results/agent-gpt54nano-verified-smoke/predictions.jsonl \
  --run_id agent-gpt54nano-verified-smoke \
  --max_workers 1
```

Use a new harness run ID whenever the prediction patches change. On Apple
Silicon, some official images may only provide an `amd64` manifest; configure
Docker to use `linux/amd64` emulation when necessary.

## Recommended evaluation progression

1. Generate one instance, then grade it in the isolated grading runtime to
   validate the complete flow.
2. Select and commit a fixed 10-instance smoke set before tuning.
3. Freeze the agent commit, model configuration, prompt, and dataset revision.
4. Generate predictions for all 500 Verified instances with `--all`.
5. Grade with the official harness and publish the reproducibility metadata.

When publishing results, include the resolved count and denominator, empty-patch
count, dataset revision, harness version, agent commit and dirty state, model and
non-secret settings, prompt checksum, cost, and latency distribution. Explain
any differences in tool access, retries, scaffolding, or resource limits when
comparing with public entries.

For the complete methodology and publication checklist, see the
[SWE-bench evaluation guide](../docs/swebench-evaluation.md).

## Package layout

```text
benchmarks/swebench/
├── api.py        # Coding-agent API client and automatic approval loop
├── artifacts.py  # Resumable manifests, attempt records, and predictions
├── cli.py        # `python -m benchmarks.swebench generate` command
├── config.py     # Validated benchmark configuration
├── dataset.py    # SWE-bench dataset loading and selection
├── patch.py      # Git patch capture and size validation
├── prompt.py     # Benchmark task template and checksum
├── runner.py     # Sequential instance execution
└── workspace.py  # Cached repository checkout preparation
```
