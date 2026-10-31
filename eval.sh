#!/usr/bin/env bash
# Run from anywhere: bash /path/to/eval.sh [run-id]
set -euo pipefail
cd "$(dirname "$0")"

run_id="${1:-agent-gpt54mini-verified-03-10-2026}"
run_dir=".benchmark-results/$run_id"
dataset=".benchmark-results/swe-bench-verified-78f471bf.jsonl"
predictions="$run_dir/predictions.jsonl"
current_image=""
jobs=""
ready=0

evaluate() {
  caffeinate -i uv run --group benchmark python -m swebench.harness.run_evaluation \
    --dataset_name "$dataset" \
    --split test \
    --predictions_path "$predictions" \
    --run_id "$run_id" \
    --namespace swebench \
    --max_workers 1 \
    --cache_level instance \
    "$@"
}

aggregate() {
  # Use the official report writer directly. This reads saved report.json files;
  # it does not pull images, rebuild test specs, or rerun/regrade tests.
  caffeinate -i uv run --group benchmark python - "$dataset" "$predictions" "$run_id" <<'PY'
import json
import sys
from swebench.harness.reporting import make_run_report

with open(sys.argv[1]) as stream:
    dataset = [json.loads(line) for line in stream if line.strip()]
with open(sys.argv[2]) as stream:
    predictions = {row["instance_id"]: row for row in
                   (json.loads(line) for line in stream if line.strip())}
make_run_report(predictions, dataset, sys.argv[3], namespace="swebench")
PY
}

cleanup_image() {
  if [[ -n "$current_image" ]]; then
    if docker image inspect "$current_image" >/dev/null 2>&1; then
      docker image rm "$current_image" || return 1
    fi
    current_image=""
  fi
}

finish() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  cleanup_image
  if [[ "$ready" == 1 ]]; then
    echo "Refreshing combined evaluation report..."
    aggregate
    local report_status=$?
    if [[ "$status" == 0 && "$report_status" != 0 ]]; then
      status=$report_status
    fi
  fi
  [[ -z "$jobs" ]] || rm -f "$jobs"
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ -f "$dataset" && -f "$predictions" ]] || {
  echo "Missing dataset or predictions: $dataset, $predictions" >&2
  exit 1
}
docker info >/dev/null
jobs="$(mktemp)"

# Derive jobs from predictions rather than relying on a stale image list.
caffeinate -i uv run --group benchmark python - "$predictions" "$run_id" > "$jobs" <<'PY'
import json
import sys
from pathlib import Path

with open(sys.argv[1]) as stream:
    rows = [json.loads(line) for line in stream if line.strip()]
for row in rows:
    if not (row.get("model_patch") or "").strip():
        continue
    instance = row["instance_id"]
    model = row["model_name_or_path"].replace("/", "__")
    report = Path("logs/run_evaluation") / sys.argv[2] / model / instance / "report.json"
    try:
        result = json.loads(report.read_text())[instance]
        if isinstance(result.get("resolved"), bool):
            continue
    except (OSError, ValueError, KeyError):
        pass
    image = "swebench/sweb.eval.x86_64." + instance.lower().replace("__", "_1776_") + ":latest"
    print(instance, image, report, sep="\t")
PY
ready=1
aggregate

while IFS=$'\t' read -r instance image report; do
  echo "Evaluating $instance"
  current_image="$image"
  docker pull --platform linux/amd64 "$image"
  evaluate --instance_ids "$instance"
  cleanup_image
  aggregate

  # The harness can return exit code 0 even when an instance failed to evaluate.
  caffeinate -i uv run --group benchmark python - "$report" "$instance" <<'PY'
import json
import sys
from pathlib import Path

try:
    result = json.loads(Path(sys.argv[1]).read_text())[sys.argv[2]]
    assert isinstance(result.get("resolved"), bool)
except (OSError, ValueError, KeyError, AssertionError):
    raise SystemExit(f"No valid evaluation result for {sys.argv[2]}; check logs/run_evaluation.")
PY
done < "$jobs"