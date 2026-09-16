---
name: mutation-testing
description: Evaluate test-suite quality by running mutation testing on a target module and reporting surviving mutants as coverage gaps.
---

# Mutation Testing

Mutation testing injects deliberate small faults ("mutants") into source code and checks
whether the existing test suite detects them. A surviving mutant means a test gap.

## When to use
Apply after a normal test run passes. Use it to answer: "Are these tests actually verifying
the logic, or just executing it?" Focus on modules with business logic or edge-case
arithmetic; skip generated code, migrations, and I/O wiring.

## Execution protocol

### 1. Scope selection
Identify the target module (one file at a time to bound runtime). Prefer the module
most relevant to the current change.

### 2. Dependency check
```
python3 -m mutmut --version 2>&1 || pip install mutmut
```
If pip is unavailable or the environment is restricted, report the gap and stop.

### 3. Run via the helper script
The helper script `run_mutation.py` (in this skill directory) wraps mutmut and emits
a structured JSON report. Run it as:
```
python3 /agent_skills/tester/mutation-testing/run_mutation.py \
    --src <path/to/module.py> \
    --tests <path/to/tests/> \
    [--runner pytest] \
    [--timeout 120]
```

### 4. Interpret results
The JSON output has three keys:
- `summary`: total / killed / survived / timeout counts
- `surviving_mutants`: list of `{line, original, mutant, description}` — these are the gaps
- `killed_ratio`: float 0..1 (mutation score); below 0.7 is a concern

### 5. Report
State the mutation score. For each surviving mutant, describe:
- What fault was injected
- What assertion is missing to catch it
- A minimal test case that would kill it

Never modify source or test files. Report only.

## Performance notes
- Mutation testing is O(n_mutants × test_suite_time). Limit to one module at a time.
- Use `--timeout` to cap per-mutant test time (default 30 s per mutant in mutmut).
- If the full suite is slow, instruct mutmut to run only tests in the same directory as
  the target: add `--test-time-base` and `--test-time-multiplier` in `.mutmut.toml`.

## Failure modes to distinguish
- **Environment failure:** mutmut/pytest not installed, import errors → report, do not retry.
- **Test suite failure (pre-existing):** baseline run fails before mutation → stop; the
  test-execution skill must fix this first.
- **Timeout mutant:** mutation caused an infinite loop → counted separately, not a gap.
