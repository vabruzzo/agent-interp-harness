# CLI Reference

The harness provides a `harness` command with several subcommands.

## `harness run`

Run a multi-session experiment from a config file.

```bash
harness run <config.yaml> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--model TEXT` | Override the model from config |
| `--tag TEXT` | Add tags (can be repeated) |
| `--session-mode MODE` | Override session mode (`isolated`, `chained`, `forked`) |
| `--run-name TEXT` | Custom name for the run directory |
| `--runs-dir PATH` | Output directory (default: `runs`) |
| `--no-capture` | Disable API request capture (disables resampling) |

**Examples:**

```bash
# Basic run
harness run examples/isolated.yaml

# With overrides
harness run examples/isolated.yaml \
  --model claude-sonnet-4-20250514 \
  --tag baseline \
  --session-mode chained \
  --run-name my-experiment-01

# Custom output directory
harness run config.yaml --runs-dir ./output
```

## `harness list`

List all completed runs.

```bash
harness list [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--runs-dir PATH` | Runs directory (default: `runs`) |
| `--json` | Output as JSON |

**Example output:**

```
  my-run-01  |  claude-sonnet-4  |  isolated  |  2 sessions, 30 steps  |  $0.1234
  my-run-02  |  claude-sonnet-4  |  chained   |  3 sessions, 45 steps  |  $0.2345
```

## `harness inspect`

Show details of a completed run.

```bash
harness inspect <run_dir> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON (includes file changes) |

**Example output:**

```
Run: smoke-test-01
Model: claude-sonnet-4 (openrouter)
Mode: isolated
Tags: smoke-test
Total: 15 steps, 5 tool calls
Cost: $0.0596
File writes: 1

  Session 1: 15 steps, 5 tool calls  $0.0596

File changes:
  session 1, step 15: MEMORY.md (+9/-0)
```

## `harness resample`

Resample a specific API turn N times (no tool execution).

```bash
harness resample <run_dir> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--session INT` | `1` | Session index |
| `--request INT` | `1` | Request index to resample |
| `--count INT` | `5` | Number of resamples |
| `--model TEXT` | original | Override model |
| `--replicate INT` | — | Replicate number (for `session_NN_rNN` dirs) |
| `--list-requests` | — | List available requests and exit |

### Discovering requests

Before resampling, use `--list-requests` to see what's available:

```bash
$ harness resample runs/my-run --session 1 --list-requests

Session 1: 12 captured requests

    1  |  15 messages  |  claude-sonnet-4  |  Explore the project structure...
    2  |  17 messages  |  claude-sonnet-4  |  [tool_result for toolu_01H...]
    3  |  19 messages  |  claude-sonnet-4  |  [tool_result for toolu_01H...]
   ...
```

### Resampling

```bash
# Resample request 5 ten times
harness resample runs/my-run --session 1 --request 5 --count 10

# Resample from a replicate session
harness resample runs/my-run --session 2 --replicate 3 --request 5 --count 5
```

Results are saved to `session_NN/resamples/request_NNN/`.

## `harness resample-edit`

Edit a captured API request and resample with the modified version. This is the CLI equivalent of the web UI's "Edit & Resample" feature, designed for scriptable intervention testing.

```bash
harness resample-edit <run_dir> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--session INT` | `1` | Session index |
| `--request INT` | `1` | Request index |
| `--dump` | — | Dump the request JSON to stdout for editing |
| `--input PATH` | — | Path to edited request JSON (use `-` for stdin) |
| `--label TEXT` | `cli-edit` | Human-readable label for this variant |
| `--count INT` | `5` | Number of resamples |
| `--model TEXT` | original | Override model |
| `--replicate INT` | — | Replicate number |

### Two-step workflow

**Step 1** — Dump the original request:

```bash
harness resample-edit runs/my-run --session 1 --request 5 --dump > edit.json
```

**Step 2** — Edit the JSON file (change thinking, text, tool results, system prompt, etc.), then resample:

```bash
harness resample-edit runs/my-run --session 1 --request 5 \
  --input edit.json --label "removed hedging" --count 5
```

### Piping from stdin

You can pipe edits for scriptable interventions:

```bash
# Use jq to modify the request programmatically
harness resample-edit runs/my-run --session 1 --request 5 --dump \
  | jq '.messages[-1].content[0].thinking = "I should be more direct."' \
  | harness resample-edit runs/my-run --session 1 --request 5 \
      --input - --label "direct thinking" --count 10
```

### Batch interventions

Combine with shell loops for systematic intervention testing:

```bash
for req in 3 5 7 9; do
  harness resample-edit runs/my-run --session 1 --request $req --dump \
    | jq '.messages[-1].content[0].thinking = "Skip exploration, go straight to implementation."' \
    | harness resample-edit runs/my-run --session 1 --request $req \
        --input - --label "skip-exploration" --count 5
done
```

### Output

Variants are saved alongside vanilla resamples and are visible in the web UI:

```
session_01/resamples/
├── request_005/           # vanilla resamples
│   ├── sample_01.json
│   └── sample_02.json
└── request_005_v01/       # variant from resample-edit
    ├── variant.json       # label + metadata
    ├── request.json       # the edited request body
    ├── sample_01.json
    └── sample_05.json
```

## `harness resample-session`

Re-run a forked session N times to study behavioral variance.

```bash
harness resample-session <run_dir> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--session INT` | `2` | Session index to resample |
| `--count INT` | `5` | Number of new replicates |

**Example:**

```bash
harness resample-session runs/my-run --session 2 --count 5
```

This finds the session's `fork_from` target, resolves the session ID, and runs N new replicates. New directories are appended with auto-incrementing replicate numbers, and `run_meta.json` is updated.
