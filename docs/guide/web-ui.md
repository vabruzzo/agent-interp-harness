# Web UI

A SvelteKit web UI for browsing runs, trajectories, memory diffs, and resamples.

## Setup

```bash
cd ui
npm install
npm run dev
# Open http://localhost:5173
```

The UI reads from the `runs/` directory (configured in `ui/.env` as `RUNS_DIR=../runs`).

## Features

### Run list
Searchable, filterable list of all runs showing model, cost, session count, and tags.

### Run overview
Metrics dashboard with session list, fork relationships, and hypothesis display.

### Trajectory viewer
Full chat view rendering:

- Agent text responses
- Extended thinking blocks (collapsible)
- Tool calls with arguments
- Tool results / observations
- System messages

### Memory diff
Before/after diffs of the memory file per session, showing how the agent's notes evolve.

### API captures
Request/response viewer showing:

- Token usage per request
- System prompts
- Tool definitions
- Compaction events (when context is summarized)
- Sampling parameters

### Subagent viewer
Separate trajectory view for each subagent invocation, showing the task prompt and return value.

### Resamples
Compare N resample outputs for a given API turn side-by-side.

### Edit & Resample
Interactive message editor for intervention testing:

1. Edit thinking blocks, text, tool results, or system prompts
2. Resample with the modified input
3. Compare original vs. variant responses

### Changelog
Per-step file write log across all sessions with expandable diffs.

### Config viewer
The frozen YAML config from the run.

### Analysis
Rendered markdown from `analysis.md` (if present in the run directory).

### Dark mode
Toggle between light and dark themes.
