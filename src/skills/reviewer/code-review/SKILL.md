---
name: code-review
description: Produce evidence-based, actionable reviews of a proposed code change.
---

# Code Review

## Establish the review scope

Read the delegated requirements and acceptance criteria. Identify the changed files and
the available diff or baseline. Check repository instructions and the implementation
independently of the programmer's explanation. Request missing change context through
the coordinator; the reviewer has file tools and must not run Git or shell commands.

Read the full affected functions and relevant callers, interfaces, and tests. Distinguish
new behavior from existing behavior when evidence permits. If a baseline is unavailable,
explain the limitation rather than attributing every observed problem to the change.

## Inspect behavior and contracts

- Trace representative inputs through the changed paths to their observable results.
  Compare those results with the requirements and existing public contracts.
- Check boundary values, empty or invalid inputs, failure handling, and compatibility
  with affected callers. Assess state changes and cleanup when relevant.
- Inspect security boundaries, concurrent access, resource use, and performance only
  where the change provides a concrete reason to investigate them.
- Read the tests as code: confirm their setup reaches the affected path, assertions
  check the intended behavior, and mocks do not hide the defect being tested.
- Identify missing verification through specific scenarios. Passing reported tests do
  not replace static inspection, and static inspection does not establish test success.
- On remediation rounds, inspect the latest changes and reassess previous findings.

## Build actionable findings

For each candidate finding, establish a triggering condition, code evidence, and an
observable consequence. Verify the claim against the inspected context. Identify the
smallest useful file/line location and suggest a focused correction or regression test.
Use the role prompt's P0-P3 severity definitions and report contract.

Do not inflate uncertain risks into confirmed defects. Put unresolved questions and
runtime evidence requests in Verification gaps. Exclude cosmetic preferences, unrelated
pre-existing problems, duplicate findings, and unsupported claims.

Keep review read-only. Route requested execution evidence to the coordinator for the
tester, and code/test changes to the coordinator for the programmer. Attribute supplied
test results to their source. State explicitly when no material issues were found and
limit any PASS verdict to the actual static-review scope.
