"""Rich presentation and human approval prompting."""

import json
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.status import Status
from rich.syntax import Syntax
from rich.text import Text

PromptLabel = str | Text
Ask = Callable[[PromptLabel], str]
Choose = Callable[[PromptLabel, tuple[str, ...]], str]


def rich_ask(message: PromptLabel) -> str:
    """Prompt for free-form input through Rich."""
    return Prompt.ask(message)


def rich_choose(message: PromptLabel, choices: tuple[str, ...]) -> str:
    """Prompt for one constrained choice through Rich."""
    return Prompt.ask(message, choices=list(choices), default=choices[0])


class TerminalUI:
    """Render run progress while keeping transport logic elsewhere."""

    def __init__(
        self,
        console: Console,
        *,
        choose: Choose = rich_choose,
        ask: Ask = rich_ask,
    ) -> None:
        """Inject the console and prompt functions for deterministic tests."""
        self.console = console
        self._choose = choose
        self._ask = ask
        self._status: Status | None = None
        self._live: Live | None = None
        self._text = ""
        self._terminal = False

    def handle_event(self, kind: str, data: dict[str, Any]) -> None:
        """Render one validated API event."""
        if kind == "status":
            self._start_status(data["status"])
        elif kind == "agent_activity":
            self._stop_status()
            activity = Text(data["agent"], style="cyan")
            activity.append(": ")
            activity.append(data["status"])
            self.console.print(activity)
        elif kind == "text_delta":
            self._stop_status()
            self._text += data["text"]
            if self._live is None:
                self._live = Live(
                    Text(self._text),
                    console=self.console,
                    transient=True,
                    refresh_per_second=8,
                )
                self._live.start()
            else:
                self._live.update(Text(self._text), refresh=True)
        elif kind == "completed":
            self._stop_progress()
            self.console.print(Markdown(str(data.get("output") or "")))
            self._terminal = True
        elif kind == "failed":
            self._stop_progress()
            failure = Text("Run failed: ", style="red")
            failure.append(data["error"], style="none")
            self.console.print(failure)
            self._terminal = True

    def confirm_connection(
        self, api_url: str, resolved_source_folder: str | None
    ) -> None:
        """Show the API and server-resolved workspace as literal text."""
        connection = Text("Connected to API: ", style="green")
        connection.append(api_url, style="none")
        self.console.print(connection)
        if resolved_source_folder is not None:
            source = Text("Server source folder: ")
            source.append(resolved_source_folder)
            self.console.print(source)

    def collect_decisions(
        self, approvals: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Show every action and collect a complete ordered decision map."""
        self._stop_progress()
        decisions: dict[str, list[dict[str, Any]]] = {}
        for approval in approvals:
            interrupt_id = str(approval["interrupt_id"])
            selected = []
            for action in approval.get("action_requests", []):
                name = action["name"]
                title = Text("Approval required: ")
                title.append(name)
                self.console.rule(title)
                if action.get("description"):
                    self.console.print(Text(action["description"]))
                arguments = json.dumps(
                    action.get("args", {}), ensure_ascii=False, indent=2, sort_keys=True
                )
                self.console.print(Syntax(arguments, "json", word_wrap=True))
                prompt = Text("Decision for ")
                prompt.append(name)
                choice = self._choose(prompt, ("approve", "edit", "reject"))
                if choice == "approve":
                    selected.append({"type": "approve"})
                elif choice == "edit":
                    selected.append(self._edit_decision(name))
                else:
                    feedback = self._ask("Optional rejection feedback").strip()
                    decision = {"type": "reject"}
                    if feedback:
                        decision["message"] = feedback
                    selected.append(decision)
            decisions[interrupt_id] = selected
        return decisions

    def _edit_decision(self, name: str) -> dict[str, Any]:
        while True:
            prompt = Text("Edited JSON arguments for ")
            prompt.append(name)
            raw = self._ask(prompt)
            try:
                args = json.loads(raw)
                if isinstance(args, dict):
                    json.dumps(args, allow_nan=False)
            except (TypeError, ValueError):
                args = None
            if isinstance(args, dict):
                return {
                    "type": "edit",
                    "edited_action": {"name": name, "args": args},
                }
            self.console.print("[red]Enter a valid JSON object.[/red]")

    def finish(self) -> None:
        """Stop transient views before returning control to the shell."""
        self._stop_progress()

    @property
    def terminal(self) -> bool:
        """Report whether a completed or failed event was displayed."""
        return self._terminal

    @property
    def streamed_text(self) -> str:
        """Return assistant text accumulated by the transient live view."""
        return self._text

    def _start_status(self, state: str) -> None:
        self._stop_progress()
        self._status = self.console.status(Text(f"Run {state}…"), spinner="dots")
        self._status.start()

    def _stop_status(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    def _stop_progress(self) -> None:
        self._stop_status()
        if self._live is not None:
            self._live.stop()
            self._live = None
