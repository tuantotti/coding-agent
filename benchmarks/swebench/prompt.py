"""Stable SWE-bench task prompt."""

import hashlib

TASK_TEMPLATE = """Resolve the following software issue in the supplied repository.

{problem_statement}

Constraints:
- Work only inside the supplied repository.
- Diagnose and implement the requested fix.
- Run relevant tests when practical.
- Do not search the web or seek the upstream solution.
- Leave all solution changes in the working tree.
- Do not commit, reset, or discard the changes.
- No interactive user is available. Do not ask clarifying questions;
  make the best reasonable inference from the repository and proceed.
- The repository is already checked out at the workspace root.
- Do NOT output text like "Please approve" or "Ready to implement".
  Invoke write_file, edit_file, and execute tools directly.
  The runtime auto-approves all such tool calls without human intervention.
- After planning, delegate immediately to the programmer subagent to make
  file edits. Do not stop at planning or handoff-request text.

"""


def render_task(problem_statement: str) -> str:
    """Insert the public problem statement without transforming it."""
    return TASK_TEMPLATE.format(problem_statement=problem_statement)


def prompt_template_sha256() -> str:
    """Return an integrity identifier for the exact task template."""
    return hashlib.sha256(TASK_TEMPLATE.encode("utf-8")).hexdigest()
