#!/usr/bin/env bash
# Benchmark smoke run wrapper for Apple Silicon — ONE instance per invocation.
#
# This script does NOT run anything on its own. It prints the exact command
# sequence you should execute — split across two terminals — so nothing surprising
# happens on your machine. See benchmarks/README.md for the safety warning.
#
# Each invocation targets exactly one instance and picks a run-id derived from
# that instance so the runner's manifest stays consistent. Re-invoking with the
# same instance appends a new attempt under the same run-id.
#
# Prerequisites (verify manually first):
#   1. .env has AZURE_OPENAI_API_KEY / ENDPOINT / OPENAI_API_VERSION / CODING_MODEL
#   2. Docker Desktop (or Colima) is running
#   3. You have run: uv sync --group benchmark --group dev
#   4. You accept auto-approve risk on THIS host, or you moved to a container/VM
#
# Usage:
#   dat_test/benchmark_smoke_run.sh                          # list instances with numbers
#   dat_test/benchmark_smoke_run.sh <n>                      # pick instance #n from file
#   dat_test/benchmark_smoke_run.sh <instance-id>            # pick by full id
#   dat_test/benchmark_smoke_run.sh <n> <run-id>             # override run-id
#   INSTANCE_FILE=path/to/list.txt dat_test/benchmark_smoke_run.sh 3

set -euo pipefail

INSTANCE_FILE="${INSTANCE_FILE:-.benchmark-results/arm_smoke.txt}"
MODEL_LABEL="${MODEL_LABEL:-azure_openai:gpt-4.1-mini}"
DATASET_REVISION="78f471bf655a3137b2e8a75af1501690ec009ec3"
API_URL="${API_URL:-http://127.0.0.1:8000}"
API_PORT="${API_URL##*:}"

if [[ ! -f "$INSTANCE_FILE" ]]; then
  echo "error: instance file not found: $INSTANCE_FILE" >&2
  echo "Generate one with:" >&2
  echo "  uv run python dat_test/benchmark_filter_instances.py --limit 20 --out $INSTANCE_FILE" >&2
  exit 1
fi

INSTANCES=()
while IFS= read -r line; do
  [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
  INSTANCES+=("$line")
done < "$INSTANCE_FILE"

if [[ ${#INSTANCES[@]} -eq 0 ]]; then
  echo "error: no instance IDs in $INSTANCE_FILE" >&2
  exit 1
fi

# No arg → list available instances and exit.
if [[ $# -eq 0 ]]; then
  echo "Available instances in $INSTANCE_FILE (${#INSTANCES[@]} total):"
  for i in "${!INSTANCES[@]}"; do
    printf "  %3d  %s\n" $((i + 1)) "${INSTANCES[i]}"
  done
  echo
  echo "Pick one: $0 <n>    (e.g. $0 1)"
  echo "Or by id: $0 <instance-id>"
  exit 0
fi

SELECTOR="$1"
INSTANCE_ID=""

if [[ "$SELECTOR" =~ ^[0-9]+$ ]]; then
  INDEX=$((SELECTOR - 1))
  if [[ $INDEX -lt 0 || $INDEX -ge ${#INSTANCES[@]} ]]; then
    echo "error: index $SELECTOR out of range (1..${#INSTANCES[@]})" >&2
    exit 1
  fi
  INSTANCE_ID="${INSTANCES[$INDEX]}"
else
  for candidate in "${INSTANCES[@]}"; do
    if [[ "$candidate" == "$SELECTOR" ]]; then
      INSTANCE_ID="$candidate"
      break
    fi
  done
  if [[ -z "$INSTANCE_ID" ]]; then
    echo "error: instance-id '$SELECTOR' not in $INSTANCE_FILE" >&2
    echo "Run without args to list available instances." >&2
    exit 1
  fi
fi

# run-id must be unique per instance because ArtifactStore.initialize rejects
# a manifest whose instance_ids differ from a previous run at the same path.
SLUG="${INSTANCE_ID//__/-}"
RUN_ID="${2:-smoke-${SLUG}}"

cat <<EOF
================================================================
Benchmark smoke run plan — SINGLE INSTANCE
  instance:     $INSTANCE_ID
  run_id:       $RUN_ID
  model_label:  $MODEL_LABEL
  api_url:      $API_URL
  dataset rev:  ${DATASET_REVISION:0:8}
================================================================

STEP 1 — In terminal A, start the API in benchmark-safe mode:

  export CODING_WEB_SEARCH_ENABLED=false
  export LANGSMITH_TRACING=false
  export LANGFUSE_TRACING_ENABLED=false
  uv run uvicorn src.main:app --host 127.0.0.1 --port $API_PORT --workers 1

STEP 2 — In terminal B, verify the API is benchmark-safe:

  curl --fail --silent $API_URL/v1/benchmark-config | python -m json.tool

  Expect: "web_search_enabled": false, and "model" matching $MODEL_LABEL.

STEP 3 — In terminal B, generate the patch for this one instance:

  uv run python -m benchmarks.swebench generate \\
    --api-url $API_URL \\
    --output .benchmark-results \\
    --run-id $RUN_ID \\
    --dataset-revision $DATASET_REVISION \\
    --model-label $MODEL_LABEL \\
    --instance-id $INSTANCE_ID \\
    --acknowledge-auto-approval-risk

  Re-running the same command skips completed attempts. Add --retry-failures
  to make a new attempt after a failure.

STEP 4 — Stop the API (terminal A: Ctrl-C) BEFORE exporting gold dataset.

STEP 5 — Export the pinned dataset for grading (once per revision, reusable):

  uv run python -c 'from datasets import load_dataset; load_dataset("SWE-bench/SWE-bench_Verified", split="test", revision="$DATASET_REVISION").to_json(".benchmark-results/swe-bench-verified-${DATASET_REVISION:0:8}.jsonl")'

STEP 6 — Grade this one instance with the official harness (build native arm64):

  uv run python -m swebench.harness.run_evaluation \\
    --dataset_name .benchmark-results/swe-bench-verified-${DATASET_REVISION:0:8}.jsonl \\
    --split test \\
    --predictions_path .benchmark-results/$RUN_ID/predictions.jsonl \\
    --run_id $RUN_ID \\
    --namespace '' \\
    --max_workers 1

  '--namespace' with an empty value tells the harness to build images locally
  instead of pulling amd64-only images from the registry. First build per repo
  can take 5–15 minutes.

STEP 7 — Move on to the next instance:

  $0                     # re-list to pick a different number
  $0 <n+1>               # or jump straight to the next one

================================================================
EOF
