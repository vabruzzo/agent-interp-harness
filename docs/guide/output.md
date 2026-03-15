# Output Structure

Each run produces a directory under `runs/`:

```
runs/<run_name>/
├── config.yaml                 # frozen copy of the run config
├── run_meta.json               # run-level metadata and aggregates
├── full_diff.patch             # unified diff of all changes (baseline → final)
├── state_changelog.jsonl       # per-step write log across all sessions
├── analysis.md                 # experiment analysis (if created)
├── .shadow_git/                # shadow git repo (invisible change tracker)
│
├── session_01/
│   ├── trajectory.json         # ATIF v1.6 trajectory (parent)
│   ├── session_diff.patch      # unified diff of this session's changes
│   ├── subagent_<name>_<id>.json  # subagent ATIF trajectory (if any)
│   ├── api_captures.jsonl      # API request/response metadata
│   ├── raw_dumps/              # full API request/response JSON
│   │   ├── request_NNN.json
│   │   ├── request_NNN_headers.json
│   │   ├── response_NNN.txt
│   │   └── response_NNN_headers.json
│   └── resamples/              # resample outputs
│       ├── request_005/        # vanilla resamples for request 5
│       │   ├── sample_01.json
│       │   └── sample_02.json
│       └── request_005_v01/    # intervention variant
│           ├── variant.json
│           ├── request.json
│           └── sample_01.json
│
├── session_02/
│   └── ...
├── session_03_r01/             # replicate 1 of 3
├── session_03_r02/             # replicate 2 of 3
└── session_03_r03/             # replicate 3 of 3
```

## Key files

### `trajectory.json`

ATIF v1.6 trajectory with:

- `steps[].source` — `"agent"`, `"user"`, or `"system"`
- `steps[].message` — text content
- `steps[].reasoning_content` — extended thinking / chain-of-thought
- `steps[].tool_calls[]` — tool invocations with function name and arguments
- `steps[].observation` — tool results, linked by `source_call_id`
- `final_metrics` — token counts, cost, step count

### `state_changelog.jsonl`

Per-step write log with file diffs:

```json
{
  "session_index": 1,
  "step_id": 15,
  "file_path": "MEMORY.md",
  "diff": "--- MEMORY.md\n+++ MEMORY.md\n@@ ...",
  "diff_stats": {"added": 9, "removed": 0}
}
```

### `run_meta.json`

Run-level metadata including per-session summaries, total cost, step counts, errors, and tags.

### `session_diff.patch`

Unified diff showing what a specific session changed relative to its starting point.

### `full_diff.patch`

Unified diff of all changes from baseline to final state across all sessions.

## API capture files

When `capture_api_requests: true`:

- `api_captures.jsonl` — structured metadata per request (token usage, context classification, compaction detection)
- `raw_dumps/request_NNN.json` — full request body sent to the API
- `raw_dumps/request_NNN_headers.json` — request headers and target URL
- `raw_dumps/response_NNN.txt` — raw response body
- `raw_dumps/response_NNN_headers.json` — response headers
