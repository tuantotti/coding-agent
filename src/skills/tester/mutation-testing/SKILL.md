---
name: mutation-testing
description: Evaluate test-suite quality by running mutation testing on a target module and reporting surviving mutants as coverage gaps.
---

# Mutation Testing

Mutation testing injects deliberate small faults ("mutants") into source code and checks
whether the existing test suite detects them. A surviving mutant means a test gap.

## When to use

Use only when the delegated task explicitly requests test-quality or coverage-depth
analysis, after relevant baseline tests pass. Focus on one relevant module with business
logic or boundary behavior; avoid generated code, migrations, and I/O wiring unless the
request establishes a useful mutation target.

Mutation tooling changes source files during execution. Never run it in the submitted
workspace. The coordinator must supply an isolated disposable copy, with independent
source files and a suitable runtime. Do not create the copy, change project files, or
install dependencies yourself. If isolation is not supplied, report a blocker.

## Execution protocol

### 1. Scope selection
Identify the target module, corresponding tests, runtime, runner, and bounded execution
budget. Verify that source and test paths point into the supplied disposable copy and
that its source is the version under review. Do not use symlinks or shared files that
could cause mutations to reach the submitted workspace. If isolation cannot be
established, do not execute mutation tooling.

### 2. Dependency check
Check that the supplied runtime already has the required mutation tooling. Use approved
inspection commands; do not automatically install or upgrade anything. Run the relevant
baseline tests in the disposable copy and record their actual result. If dependencies
are missing or the baseline fails, stop mutation analysis and route evidence to the
coordinator. Do not label a baseline failure as pre-existing without supporting evidence.

### 3. Run via the helper script
The helper script `run_mutation.py` wraps mutmut and emits a structured JSON report.
Its /agent_skills/tester/mutation-testing/run_mutation.py path is virtual: file tools
can read it, but the host shell cannot execute it. The coordinator must supply a real
absolute host helper path. Verify it is readable and points to the expected helper;
never guess the path or run the virtual path. If unavailable, report a blocker.

The bundled helper supports Python with the exact runner value `pytest` and mutmut 2.x.
Verify this matches the project and supplied runtime. For other runners or languages,
report unsupported mutation infrastructure to the coordinator rather than passing an
arbitrary runner to this helper. Ordinary test execution remains language-neutral.

Use the supplied Python runtime, host helper path, and paths inside the disposable copy.
Replace the placeholders below with verified values; run from the disposable root:

```
"<RUNTIME>" "<HOST_HELPER_PATH>" \
    --src "<DISPOSABLE_MODULE_PATH>" \
    --tests "<DISPOSABLE_TESTS_PATH>" \
    --project-root "<DISPOSABLE_ROOT>" \
    --runner pytest \
    --timeout <APPROVED_TIMEOUT_SECONDS>
```

All commands require caller approval. This explicitly supplied disposable location is
the tester prompt's only exception to normal workspace execution. The helper can also
produce caches and temporary mutants there; leave the submitted workspace unchanged.

### 4. Interpret results
On a completed run, inspect these JSON fields alongside command status and raw output:

- `summary`: total / killed / survived / timeout counts
- `surviving_mutants`: list of `{id, file, diff}`; inspect each diff to identify the fault
  and its location rather than assuming separate line or description fields
- `killed_ratio`: float 0..1 (mutation score)

Check the run completed and produced meaningful mutant counts before reporting a score.
An error report, incomplete run, or zero mutants does not establish coverage quality.
Do not use a universal score threshold as proof of correctness or test adequacy.

### 5. Report
Use the tester prompt's report sections. State the target, commands, disposable working
directory, baseline evidence, mutant counts, timeouts, and score when valid. For each
relevant surviving mutant, describe:

- What fault was injected
- What assertion is missing to catch it
- A minimal test case that would kill it

Consider equivalent mutants or mutations irrelevant to the requirements before calling
a survivor a concrete coverage gap. Explain uncertainty. Suggest assertions to the
coordinator for the programmer; do not modify source or tests in the submitted workspace.
Requested but blocked mutation analysis keeps overall validation PARTIAL if useful
ordinary checks ran, or BLOCKED if no meaningful validation ran. An observed unresolved
product failure still takes precedence as FAIL.

## Performance notes
- Mutation cost grows with mutant count and test-suite runtime. Limit to one module
  and a relevant test subset supported by the runner.
- The helper's `--timeout` sets mutmut's test-time base; it is not a strict per-mutant
  time cap. The helper uses a 120-second baseline limit and an outer mutation limit
  of 50 times that argument. Keep the full command within the approved execute budget.
- Respect the approved execute timeout and the helper's limits. Report
  an interrupted run as incomplete; do not repeatedly restart it without new evidence.
- Request further scope or budget changes from the coordinator instead of editing
  project configuration to speed up the run.

## Failure modes to distinguish
- **Environment or infrastructure failure:** Missing tooling, runtime, host helper path,
  or verified isolation; report the blocker and stop.
- **Baseline failure:** Stop mutation analysis and route evidence through the coordinator.
  The tester does not fix source, tests, or dependencies.
- **Timeout mutant:** Report separately; a timeout may reflect slow execution or a faulty
  mutant and is not automatically a surviving coverage gap.
- **Incomplete or empty run:** Report insufficient evidence rather than a passing score.
