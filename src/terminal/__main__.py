"""Command-line entry point for the Rich coding-agent client."""

import argparse
import os
from collections.abc import Callable, Mapping, Sequence

from rich.console import Console
from rich.text import Text

from src.terminal.client import ReplayExpired, TerminalClient, TerminalError
from src.terminal.ui import Ask, Choose, TerminalUI, rich_ask, rich_choose

ClientFactory = Callable[[str], TerminalClient]


def parser() -> argparse.ArgumentParser:
    """Build the standard argparse command contract."""
    value = argparse.ArgumentParser(description="Connect to a coding-agent API.")
    value.add_argument("--api-url")
    value.add_argument("--task")
    value.add_argument("--source-folder")
    return value


def _required(value: str | None, label: str, ask: Ask) -> str:
    while value is None or not value.strip():
        value = ask(label)
    return value.strip()


def _source_folder(value: str | None, ask: Ask) -> str:
    """Preserve explicit paths while tidying values entered at a prompt."""
    if value is not None and value.strip():
        return value
    while True:
        prompted = ask("Source folder on API server").strip()
        if (
            len(prompted) >= 2
            and prompted[0] in {'"', "'"}
            and prompted[-1] == prompted[0]
        ):
            prompted = prompted[1:-1]
        if prompted.strip():
            return prompted


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    console: Console | None = None,
    ask: Ask = rich_ask,
    choose: Choose = rich_choose,
    client_factory: ClientFactory = TerminalClient,
) -> int:
    """Run one non-persistent terminal session and return its shell code."""
    args = parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    output = console or Console()
    ui = TerminalUI(output, ask=ask, choose=choose)
    client: TerminalClient | None = None
    try:
        task = _required(args.task, "Task", ask)
        source_folder = _source_folder(args.source_folder, ask)
        api_url = (
            args.api_url
            or environment.get("CODING_AGENT_API_URL")
            or "http://127.0.0.1:8000"
        )
        client = client_factory(api_url)
        run = client.start_run(task, source_folder)
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise TerminalError("Server response did not include a run ID.")
        resolved_source = run.get("source_folder")
        ui.confirm_connection(
            api_url,
            resolved_source if isinstance(resolved_source, str) else None,
        )
        for event in client.events(run_id):
            if event.event == "approval_required":
                decisions = ui.collect_decisions(event.data.get("approvals", []))
                client.resume(run_id, decisions)
            else:
                ui.handle_event(event.event, event.data)
        if not ui.terminal:
            raise TerminalError("Event stream ended before a final result.")
        return 0 if event.event == "completed" else 1
    except ReplayExpired as exc:
        status = exc.run.get("status")
        if status in {"completed", "failed"}:
            ui.handle_event(status, exc.run)
            return 0 if status == "completed" else 1
        output.print(
            Text("Event history was lost before the run finished.", style="red")
        )
        return 1
    except KeyboardInterrupt:
        output.print(Text("\nInterrupted.", style="yellow"))
        return 130
    except TerminalError as exc:
        message = Text("Error: ", style="red")
        message.append(str(exc), style="none")
        output.print(message)
        return 1
    finally:
        ui.finish()
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
