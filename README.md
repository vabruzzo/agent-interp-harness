# agent-interp-harness

A harness for running multi-session agent trajectories using the Claude Agent SDK, capturing them in [ATIF](https://harborframework.com/docs/agents/trajectory-format) (Agent Trajectory Interchange Format), and tracking file state changes across sessions.

Built for agent interpretability research — studying how LLM agents behave across multi-turn, multi-session, multi-agent interactions.

## What it does

The harness takes a YAML config describing a sequence of sessions (prompts to an agent), runs each session against a target repository via the Claude Agent SDK, and produces structured outputs:

- **ATIF trajectories** — standardized JSON capturing every agent step, tool call, observation, and thinking block
- **File state tracking** — snapshots, unified diffs, and per-step write attribution across sessions
- **Session chaining** — three modes for controlling how sessions relate to each other (isolated, chained, forked)
- **Subagent capture** — separate ATIF trajectories for each subagent invocation, linked to the parent via `SubagentTrajectoryRef`

## Install

Requires Python >= 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo>
cd agent-interp-harness
uv sync
```

## Quick start

Set your API key (see [Providers](#providers) for all options):

```bash
export OPENROUTER_API_KEY=sk-or-...
```

Run the smoke test:

```bash
harness run tests/smoke.yaml
```

Inspect results:

```bash
harness inspect runs/<run-name>
```

## Providers

The harness uses the [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) to run Claude Code sessions programmatically. **Only Claude models are supported** — the SDK speaks the Anthropic Messages API protocol and cannot run non-Claude models. Set the `provider` field in your config to choose how to route API calls.

| Provider | Config value | Env var | Notes |
|----------|-------------|---------|-------|
| [OpenRouter](https://openrouter.ai) | `openrouter` (default) | `OPENROUTER_API_KEY` | Routes through OpenRouter. The harness sets `ANTHROPIC_BASE_URL` automatically. |
| [Anthropic](https://console.anthropic.com) | `anthropic` | `ANTHROPIC_API_KEY` | Direct Anthropic API. The SDK reads the key from the environment. |
| [AWS Bedrock](https://aws.amazon.com/bedrock/) | `bedrock` | Standard AWS credentials (`AWS_ACCESS_KEY_ID`, etc.) | Sets `CLAUDE_CODE_USE_BEDROCK=1`. |
| [GCP Vertex AI](https://cloud.google.com/vertex-ai) | `vertex` | Standard GCP credentials (`GOOGLE_APPLICATION_CREDENTIALS`, etc.) | Sets `CLAUDE_CODE_USE_VERTEX=1`. |

You can also set `base_url` in your config to point at a custom Anthropic-compatible endpoint.

Example configs:

```yaml
# OpenRouter (default)
model: "claude-sonnet-4-20250514"
provider: openrouter

# Anthropic direct
model: "claude-sonnet-4-20250514"
provider: anthropic
```

## Configuration

Experiments are defined as YAML config files. Here's a full example:

```yaml
model: "claude-sonnet-4-20250514"
provider: openrouter                    # openrouter | anthropic | bedrock | vertex
hypothesis: "The agent preserves hedging across sessions"  # what this experiment tests
repo_path: "./repos/my_project"        # target codebase the agent works in
session_mode: chained                   # isolated | chained | forked
tags: ["experiment-1"]

system_prompt: |
  You are exploring a Python codebase. Use MEMORY.md to keep notes.

allowed_tools:                          # Claude Code tools the agent can use
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit

max_turns: 30                           # max agent turns per session
permission_mode: acceptEdits            # acceptEdits | bypassPermissions
max_budget_usd: 1.00                    # optional spend cap per session
load_project_settings: false            # whether to load the repo's CLAUDE.md

tracked_files:                          # files to snapshot and diff across sessions
  - path: "MEMORY.md"
    seed_content: "# Project Notes\n"   # optional initial content

sessions:
  - session_index: 1
    prompt: "Explore the project structure. Take notes in MEMORY.md."
  - session_index: 2
    prompt: "Read the main module in detail. Update your notes."
  - session_index: 3
    prompt: "Summarize what you know about this project."
    max_turns: 10                       # per-session override
```

### Automatic behaviors

- **MEMORY.md is always tracked.** If your config doesn't include it in `tracked_files`, the harness adds it automatically with seed content `# Notes\n`. You can override the seed content by including it explicitly.
- **Tracked file paths are injected into the system prompt.** The harness appends the absolute paths of all tracked files to the system prompt so the agent knows exactly where to read/write. This prevents the agent from guessing wrong paths.
- **The working directory is the repo.** The agent's cwd is set to the resolved `repo_path`.

### Session modes

| Mode | Behavior |
|------|----------|
| `isolated` | Each session starts fresh with no memory of previous sessions. The agent only knows what's written to tracked files. |
| `chained` | Each session resumes from the previous session's conversation. The agent has full context of all prior interactions. |
| `forked` | Sessions 2+ fork from session 1. Each sees session 1's context but not each other's. Useful for branching experiments. |

### Subagents

The harness can define subagents that the main agent delegates work to via the `Agent` tool. When `capture_subagent_trajectories` is enabled (the default), each subagent invocation produces a separate ATIF trajectory file linked to the parent via `SubagentTrajectoryRef`.

```yaml
agents:
  - name: "code-explorer"
    description: "Explores code structure, reads files, and reports findings."
    prompt: "You are a code exploration specialist. Read files and report structure."
    tools: ["Read", "Glob", "Grep"]    # tool restrictions (null = inherit all)
    model: "sonnet"                     # sonnet | opus | haiku | inherit
```

Each agent in `agents` has:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | yes | — | Agent name (used as key in SDK's agents dict) |
| `description` | yes | — | When to use this agent (shown to the parent) |
| `prompt` | yes | — | System prompt for the subagent |
| `tools` | no | inherit all | Tool restrictions for the subagent |
| `model` | no | inherit | Model override: `sonnet`, `opus`, `haiku`, or `inherit` |

The `Agent` tool is automatically added to `allowed_tools` when `agents` is non-empty.

Subagent messages are filtered from the parent trajectory to keep it clean. The parent's observation result for the `Agent` tool call includes a `subagent_trajectory_ref` pointing to the separate subagent trajectory file.

### Config reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `model` | yes | — | Claude model identifier (e.g. `claude-sonnet-4-20250514`). Use Anthropic model names, not OpenRouter-format names. |
| `provider` | no | `openrouter` | API provider: `openrouter`, `anthropic`, `bedrock`, `vertex` |
| `base_url` | no | — | Custom API base URL (overrides provider default) |
| `hypothesis` | no | — | One-sentence hypothesis this experiment tests. Shown in the web UI and saved to `run_meta.json`. |
| `repo_path` | yes | — | Path to the target codebase |
| `repo_name` | no | — | Human-readable name for the repo |
| `sessions` | yes | — | List of `SessionConfig` objects |
| `session_mode` | no | `isolated` | `isolated`, `chained`, or `forked` |
| `system_prompt` | no | — | System prompt for all sessions |
| `allowed_tools` | no | Read, Grep, Glob, Bash, Write, Edit | Tools the agent can use |
| `max_turns` | no | `50` | Max agent turns per session |
| `permission_mode` | no | `acceptEdits` | `acceptEdits` or `bypassPermissions` |
| `tracked_files` | no | MEMORY.md auto-added | Files to snapshot/diff across sessions. MEMORY.md is always tracked. |
| `max_budget_usd` | no | — | Per-session spend cap |
| `load_project_settings` | no | `false` | Load repo's CLAUDE.md and .claude/settings.json |
| `agents` | no | `[]` | Subagent definitions (see [Subagents](#subagents)) |
| `capture_subagent_trajectories` | no | `true` | Save separate ATIF trajectories for each subagent invocation |
| `capture_api_requests` | no | `true` | Capture raw API requests via proxy (enables resampling and intervention testing) |
| `run_name` | no | auto-generated | Custom name for the run directory |
| `tags` | no | `[]` | Metadata tags |

Each session in `sessions` has:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `session_index` | yes | — | Sequential index starting at 1 |
| `prompt` | yes | — | The user prompt for this session |
| `system_prompt` | no | — | Per-session system prompt override |
| `max_turns` | no | — | Per-session max turns override |

## CLI

```
harness run <config.yaml>                Run an experiment
harness list [--json]                    List completed runs
harness inspect <run_dir> [--json]       Show run details
harness resample <run_dir> --session N --request N --count N   Resample an API turn
```

All commands support `--json` for machine-readable output.

### `harness run`

```bash
harness run examples/isolated.yaml \
  --model anthropic/claude-sonnet-4 \
  --tag baseline \
  --session-mode chained \
  --run-name my-run-01 \
  --runs-dir ./output
```

### `harness inspect`

```
$ harness inspect runs/smoke-test-01

Run: smoke-test-01
Model: anthropic/claude-sonnet-4 (openrouter)
Mode: isolated
Tags: smoke-test
Total: 15 steps, 5 tool calls
Cost: $0.0596
File writes: 1

  Session 1: 15 steps, 5 tool calls  $0.0596

File changes:
  session 1, step 15: MEMORY.md (+9/-0)
```

### `harness resample`

Replay a specific API turn N times to study output variance:

```bash
harness resample runs/my-run --session 1 --request 5 --count 10
```

Resample results are saved to `session_NN/resamples/request_NNN/` and can be viewed in the web UI.

## Web UI

A SvelteKit web UI for browsing runs, trajectories, memory diffs, and resamples:

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:5173`. The UI reads from the `runs/` directory and provides:

- **Run overview** — stats, session list, hypothesis display
- **Trajectory viewer** — full chat view with thinking blocks, tool calls, and observations
- **Memory diff** — per-session diffs of tracked files
- **API captures** — raw request/response viewer with token usage
- **Resamples** — compare N resample outputs for a given API turn, with intervention testing (edit inputs and resample)
- **Analysis** — rendered markdown from `analysis.md` (generated by the `/experiment` skill)

The UI expects `RUNS_DIR=../runs` (configured in `ui/.env`).

## Output structure

Each run produces a directory under `runs/`:

```
runs/<run_name>/
├── config.yaml                 # frozen copy of the run config
├── run_meta.json               # run-level metadata and aggregates
├── analysis.md                 # experiment analysis (generated by /experiment skill)
├── state_init/                 # tracked files before any sessions
├── state_final/                # tracked files after all sessions
├── state_changelog.jsonl       # per-step write log across all sessions
├── session_01/
│   ├── trajectory.json         # ATIF v1.6 trajectory (parent)
│   ├── subagent_<name>_<id>.json  # subagent ATIF trajectory (if any)
│   ├── api_captures.jsonl      # raw API request log (if capture enabled)
│   ├── raw_dumps/              # full API request/response JSON (if capture enabled)
│   ├── resamples/              # resample outputs (created by UI or CLI)
│   │   ├── request_005/        # vanilla resamples for request 5
│   │   │   ├── sample_01.json
│   │   │   └── sample_02.json
│   │   └── request_005_v01/    # intervention variant
│   │       ├── variant.json    # edit metadata (label, find/replace pairs)
│   │       ├── request.json    # modified request body
│   │       └── sample_01.json
│   ├── state_before/           # tracked files before this session
│   ├── state_after/            # tracked files after this session
│   └── state_diff.patch        # unified diff of changes
└── session_02/
    └── ...
```

### ATIF trajectory

Each session produces a `trajectory.json` in [ATIF v1.6](https://harborframework.com/docs/agents/trajectory-format) format. Key fields:

- `steps[].source` — `"agent"`, `"user"`, or `"system"`
- `steps[].message` — the text content of the step
- `steps[].reasoning_content` — extended thinking / chain-of-thought (when available)
- `steps[].tool_calls[]` — tool invocations with function name and arguments
- `steps[].observation` — tool results, linked back to their tool call by `source_call_id`
- `final_metrics` — token counts, cost, step count

### State changelog

`state_changelog.jsonl` records every detected file write with step-level attribution:

```json
{
  "session_index": 1,
  "step_id": 15,
  "file_path": "MEMORY.md",
  "diff": "--- MEMORY.md\n+++ MEMORY.md\n@@ ...",
  "diff_stats": {"added": 9, "removed": 0}
}
```

### API request capture

When `capture_api_requests: true` is set (or `--capture-requests` CLI flag), the harness runs a local reverse proxy between the SDK and the API. This captures data not available in the SDK message stream:

- **System prompt** — the SDK's system prompt (a minimal agent prompt plus your `system_prompt` config)
- **Tool definitions** — JSON schemas for each tool (Read, Write, Bash, etc.)
- **Context management** — `applied_edits` from the API response when compaction occurs
- **Per-request token usage** — input/output tokens, cache creation/read breakdown
- **Compaction detection** — when message count drops between requests, captures the post-compaction messages
- **Sampling parameters** — model, temperature, max_tokens

The proxy logs to `api_captures.jsonl` in each session directory. System prompt and tools are logged in full on the first request and on change; otherwise only a hash is recorded to keep file sizes small.

## Architecture

```
src/harness/
├── config.py            # Pydantic config models, YAML loading
├── atif_adapter.py      # Claude SDK Message -> ATIF Step mapping
├── state.py             # File snapshots, diffs, write tracking
├── runner.py            # Single session execution
├── experiment.py        # Multi-session orchestration
└── cli.py               # Typer CLI
```

The core complexity lives in `atif_adapter.py`: the Claude Agent SDK streams messages (AssistantMessage, UserMessage, SystemMessage, ResultMessage) and the adapter maps them into ATIF steps with correct tool call / observation pairing, thinking block capture, and sequential step IDs.

## Dependencies

- [claude-agent-sdk](https://pypi.org/project/claude-agent-sdk/) — runs Claude Code sessions programmatically
- [harbor](https://pypi.org/project/harbor/) — ATIF Pydantic models for trajectory validation
- [typer](https://typer.tiangolo.com/) — CLI framework
- [pyyaml](https://pyyaml.org/) — config file loading
- [pydantic](https://docs.pydantic.dev/) — config validation
