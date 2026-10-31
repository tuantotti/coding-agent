---
name: test-execution
description: Select and report focused verification commands for a repository change.
---

# Test Execution

## Select verification from repository evidence

Read the delegated requirements, changed implementation, relevant tests, repository
instructions, manifests, and test configuration. Identify the documented runtime and
runner. Map acceptance criteria and affected interfaces to checks that actually exercise
the changed behavior; explain any gap that existing tests cannot cover.

Start with focused existing tests or an available issue reproduction. Include nearby
regressions and boundary cases that follow from the change. Add broader suite, lint,
type, or build checks when shared behavior or failure evidence warrants them. Use
check-only commands and keep the sequence proportional to the change.

If no relevant test exists, describe the missing scenario and expected assertion to the
coordinator for the programmer. Do not create tests or scripts, weaken assertions, skip
failing checks, edit configuration, or install dependencies to get a passing result.

## Execute and interpret

Use only the approval-gated execute tool, from the selected workspace. Await approval;
do not circumvent rejected commands. Record each attempted command and its working
directory, approval outcome, execution status, exit code, available test counts, and
concise output evidence. Retain evidence for failures even if a later retry succeeds.
Normal test caches and artifacts are permitted; project files remain unchanged.

Distinguish assertion failures from import, dependency, collection, timeout, or approval
problems. A setup failure may prevent any product behavior from being exercised. Label
pre-existing failures only when comparable baseline results support that classification;
request baseline evidence through the coordinator rather than resetting the workspace.

Verify that meaningful checks ran. Zero collected tests, all-skipped runs, disabled
assertions, or proposed commands provide no passing evidence. Explain unexpected skips
and partial runs. Do not invent counts or exit codes when unavailable.

Rerun affected checks after further code changes. Retry an unchanged failure only when
new evidence or an approved environment change supports doing so. Stop unproductive
retries and give the coordinator the smallest actionable blocker.

## Report and hand off

Use the tester prompt's sections and verdict definitions. FAIL takes precedence when a
product failure remains; otherwise distinguish BLOCKED, PARTIAL, and scoped PASS based
on the actual completed validation. Request programmer changes for source or tests and
coordinator action for environment or approval problems. Missing checks remain coverage
gaps even if all executed tests pass.

Apply mutation-testing only for explicitly requested coverage analysis after a passing
baseline, using the isolated location and host helper path required by that skill.
