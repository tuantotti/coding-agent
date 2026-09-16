# Coding Agent API

A local FastAPI service coordinating Deep Agents programmer, reviewer, tester,
and information-retrieval specialists. Submit a local source folder with each
task, stream progress and assistant text, and explicitly approve proposed writes,
deletes, and shell commands. Polling remains available.

## Setup

Requires Python 3.12+ and uv.

```bash
uv sync --all-groups
cp .env.example .env
# Configure your model provider and TAVILY_API_KEY in .env.
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 1
# Or, after activating the virtual environment:
python -m src.main
```

Interactive API documentation: http://127.0.0.1:8000/docs.
Startup validates configuration. Each submitted run gets its own graph and
checkpointer, retained across approval pauses. Importing
`main` does not require credentials or create external clients.

| Setting                                                         | Default                                                    |
| --------------------------------------------------------------- | ---------------------------------------------------------- |
| OPENAI_API_KEY                                                  | Required when using OpenAI                                 |
| AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, OPENAI_API_VERSION | Used for Azure OpenAI                                      |
| TAVILY_API_KEY                                                  | Required                                                   |
| CODING_MODEL                                                    | openai:gpt-5.4                                             |
| CODING_WORKSPACE_ROOT                                           | Default for direct Python usage only                       |
| CODING_MAX_REMEDIATION_CYCLES                                   | 2                                                          |
| CODING_SHELL_TIMEOUT_SECONDS                                    | 120                                                        |
| CODING_AGENT_API_URL                                            | http://127.0.0.1:8000 (exported terminal environment only) |

Server environment variables override `.env`; the terminal-specific
`CODING_AGENT_API_URL` exception is described below. Model deployment
availability depends on your provider account. API clients select their source
folder but cannot override model credentials.

## Interactive terminal client

Start the API separately, then connect the Rich terminal client from another
shell. The client never starts or stops the server:

```bash
uv run python -m src.terminal \
  --task "Review this project for bugs" \
  --source-folder /absolute/path/on/api/server
```

Both `--task` and `--source-folder` are optional; missing values are prompted
for interactively. Select the API with `--api-url`, then
`CODING_AGENT_API_URL`, or the default `http://127.0.0.1:8000`, in that order.
The terminal reads `CODING_AGENT_API_URL` from its process environment; it does
not load `.env`. Export the value in the shell or supply `--api-url` directly.
The `.env.example` entry is a shell-configuration example for this option.
The source folder is interpreted and validated by the API server. The terminal
does not check it locally or upload files, so remote projects must already be
available to the server at the path supplied.

Queued and running states, agent activity, and incremental assistant text are
shown while the run proceeds. Approval pauses display every proposed action,
its description, and formatted JSON arguments in server order. Each action
must be explicitly approved, edited, or rejected; edits keep the action name
and require a JSON object, while rejection feedback is optional. The client
never auto-approves.

If the event connection drops, the terminal makes at most three reconnects
after 0.5, 1, and 2 seconds and resumes with the last event ID without
redisplaying events. If replay history has expired, it polls the run once to
recover an already completed or failed result; otherwise it reports that
history was lost and exits unsuccessfully. Sessions are not persisted.

## Optional Langfuse tracing

After installing dependencies, configure these server environment variables
(or put them in `.env`) and restart:

```dotenv
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Tracing defaults to disabled. Both keys are required when enabled. Set the base
URL to your Langfuse region or self-hosted instance. LangSmith remains independent
and can be enabled alongside Langfuse.

Each initial graph execution and approval resume gets a fresh callback and trace;
all traces for a run share its `run_id` as the Langfuse session ID. Callbacks
propagate to delegated agents and tools without changing SSE or approvals.
Shutdown stops agent jobs before flushing queued traces off the event loop.

The [standard Langfuse callback](https://langfuse.com/integrations/frameworks/langchain)
captures available model/tool inputs and outputs, which may include source code,
prompts, command output, and sensitive data. Enable it only when exporting this
workspace data to your configured Langfuse instance is acceptable. No custom
redaction is applied.

## Submit and poll

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"task":"Review this project for bugs.","source_folder":"/absolute/path/to/project"}'
curl http://127.0.0.1:8000/v1/runs/RUN_ID
```

Submission returns HTTP 202 with a generated `run_id`. Poll that ID for
`queued`, `running`, `awaiting_approval`, `completed`, or `failed`.
Responses include the resolved `source_folder`, timestamps, final assistant
`output`, pending `approvals`,
and a sanitized `error`. Internal graph state is not returned.

The source folder is required and must be an absolute path to an existing,
readable directory on the API server. Symlinks are resolved before execution.
The selected directory becomes the file-tool root and shell working directory.
Missing, relative, nonexistent, or inaccessible paths return HTTP 422. Old
task-only submissions must add this field; no default is silently substituted.
This is not a file-upload API: a remote client's files must first be mounted or
copied to the server.

Only one unfinished run is permitted across this server, including while
awaiting approval, even when requests select different folders. A conflicting
submission returns HTTP 409. Review-only prompts return inspection findings;
they no longer automatically trigger implementation and testing.

## Stream results

After submission, connect to the run's Server-Sent Events endpoint:

```bash
curl -N http://127.0.0.1:8000/v1/runs/RUN_ID/events
```

Events have a monotonically increasing per-run `id`, an `event` type, and JSON
`data` containing `run_id`, `timestamp`, and event-specific fields:

| Event | Data |
| --- | --- |
| status | queued or running status |
| text_delta | visible assistant text, message_id, agent, agent_path |
| agent_activity | graph node and subgraph path reporting progress |
| approval_required | awaiting_approval status and ordered approvals |
| completed | completed status and final root assistant output |
| failed | failed status and sanitized error |

Specialist text is identified separately from the coordinator's final output.
Models without token streaming may emit complete text chunks. Reasoning blocks,
raw graph state, and provider exception details are excluded.

The connection remains open while awaiting approval and sends a heartbeat
comment every 15 seconds when idle. Submit decisions through the resume endpoint;
events continue on the same connection. Completion or failure closes the stream.
Disconnecting a stream does not cancel the agent, and multiple subscribers are
supported. Browser clients should close their EventSource on terminal events.

Reconnect after the last event you received:

```bash
curl -N -H 'Last-Event-ID: 12' http://127.0.0.1:8000/v1/runs/RUN_ID/events
```

The latest 1,000 events per run are retained in memory. Without a cursor, replay
starts at event 1. An expired cursor (including a late initial connection after
event 1 has been evicted) returns HTTP 409; malformed or future cursors return
422, and unknown runs return 404. A connected subscriber that falls behind
receives `replay_expired` and is disconnected. Poll the run for its complete
final result if replay history is no longer available.

## Approve and resume

When a run pauses, inspect every entry in `approvals`. Each contains an
`interrupt_id`, ordered `action_requests` (tool name, arguments, description),
and `review_configs` describing allowed decisions.

```bash
curl -X POST http://127.0.0.1:8000/v1/runs/RUN_ID/resume \
  -H 'Content-Type: application/json' \
  -d '{"decisions":{"INTERRUPT_ID":[{"type":"approve"}]}}'
```

Supply exactly the pending interrupt IDs and one decision per action, preserving
the order returned by the API. Available decision shapes are:

```json
{"type":"approve"}
{"type":"reject","message":"Do not run this command."}
{"type":"edit","edited_action":{"name":"execute","args":{"command":"pytest -q"}}}
```

Edits must preserve the tool name and match the supplied argument schema;
invalid edits return 422 without consuming pending approvals.
Resumption returns HTTP 202 and continues the
same checkpoint; poll again because the agent may request further approvals.
Never automatically approve every request. Rejection gives feedback to the agent;
it does not cancel the whole run.

Errors: HTTP 404 for an unknown run; 409 for occupied workspace, duplicate
resume, or a run not awaiting approval; 422 for malformed input, stale/missing
interrupt IDs, mismatched decision counts, or disallowed decisions.

## Design and operational limits

- `src/agents`: typed graph and specialist factories.
- `src/services`: injected graph, run storage, background task lifecycle,
  workspace serialization, and approval handling independent of HTTP.
- `src/routes` and `src/models`: thin HTTP handlers and Pydantic contracts.
- `src/main.py`: application factory, dependency lifetime, and error mapping.
- `src/prompts`, `src/skills`, and `src/tools`: role instructions, reusable
  workflows, and Tavily integration.

This is an unauthenticated localhost API for one trusted user, one process, and
one active run at a time. Do not expose it as a shared remote service.
Run summaries and event history live in memory and disappear on restart.
Graphs and checkpoints are released after terminal outcomes. Avoid auto-reload
during active runs.
Shutdown cancels and awaits tracked Python jobs; an already approved host command
may continue until it exits or reaches its timeout.

Commands run through LocalShellBackend on the host with the server's environment
and permissions. File tools use workspace-rooted virtual paths and a protected
skills mount; these restrictions do not sandbox shell commands. Review every
command and proposed change before approving. The tester lacks file-edit tools,
but an approved command can still modify files.

The two-remediation-cycle limit is prompt-directed, not a guaranteed execution
counter. The service also sets a graph recursion limit to terminate runaway runs.
Failures do not roll back changes already approved and executed.

## Python usage and testing

Run Python from the project root and import
`AgentSettings` and `create_coding_agent` from `src.agents`. The factory returns
a compiled graph; supply a stable
`configurable.thread_id` for invocation and LangGraph `Command(resume=...)`
for direct approval handling. The service uses each run ID as its thread ID.
Its Python interface now takes a graph factory accepting a resolved `Path`,
and `await service.start(task, source_folder)` requires an explicit folder.

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Tests inject fake graphs and a deterministic chat model; no provider credentials
or live model/search requests are required.
