# Resampling

Resampling lets you study output variance by replaying API turns or entire sessions. There are three levels of resampling, all available from both the CLI and the web UI.

## Discovering requests

Before resampling, use `--list-requests` to see what API turns are available:

```bash
$ harness resample runs/my-run --session 1 --list-requests

Session 1: 12 captured requests

    1  |  15 messages  |  claude-sonnet-4  |  Explore the project...
    2  |  17 messages  |  claude-sonnet-4  |  [tool_result for toolu_01H...]
   ...
```

This shows existing resamples and variants if any have been created.

!!! note "Requires API capture"
    Turn-level resampling requires `capture_api_requests: true` in the config. The harness captures raw request/response bodies via a local reverse proxy.

## Turn-level resampling

Replay a specific API request N times to see how the model's response varies:

```bash
harness resample runs/my-run --session 1 --request 5 --count 10
```

This sends the exact same request body to the API and saves each response. Results go to:

```
session_01/resamples/request_005/
├── sample_01.json
├── sample_02.json
└── ...
```

For replicate sessions, use `--replicate`:

```bash
harness resample runs/my-run --session 2 --replicate 3 --request 5 --count 5
```

## Intervention testing (Edit & Resample)

Edit the conversation inputs before resampling to test counterfactuals — "What would the model do differently if it had seen X instead of Y?"

### From the CLI

A two-step workflow: dump, edit, resample.

```bash
# 1. Dump the request
harness resample-edit runs/my-run --session 1 --request 5 --dump > edit.json

# 2. Edit the JSON (change thinking, text, tool results, system prompt...)
# 3. Resample with the edited request
harness resample-edit runs/my-run --session 1 --request 5 \
  --input edit.json --label "removed hedging" --count 5
```

For scriptable interventions, pipe through `jq`:

```bash
harness resample-edit runs/my-run --session 1 --request 5 --dump \
  | jq '.messages[-1].content[0].thinking = "Be more direct."' \
  | harness resample-edit runs/my-run --session 1 --request 5 \
      --input - --label "direct thinking" --count 10
```

Batch across multiple requests:

```bash
for req in 3 5 7 9; do
  harness resample-edit runs/my-run --session 1 --request $req --dump \
    | jq '.messages[-1].content[0].thinking = "Skip exploration."' \
    | harness resample-edit runs/my-run --session 1 --request $req \
        --input - --label "skip-exploration" --count 5
done
```

### From the web UI

1. Open a session's API captures in the web UI
2. Click "Edit & Resample" on any request
3. Modify thinking blocks, text, tool results, or system prompts
4. Resample with the modified input

### Variant output

Both CLI and web UI variants produce the same directory structure:

```
session_01/resamples/request_005_v01/
├── variant.json     # label + metadata
├── request.json     # modified request body
├── sample_01.json   # response to modified input
└── ...
```

CLI-created variants appear in the web UI and vice versa.

## Session-level resampling

Re-run a full session N times to study variance across complete trajectories:

```bash
harness resample-session runs/my-run --session 2 --count 5
```

This finds session 2's `fork_from` target, resolves the session ID, and runs 5 new replicates. New directories are appended with auto-incrementing replicate numbers, and `run_meta.json` is updated.

## Thinking signature handling

When resampling, the harness automatically strips thinking block signatures from the request. Signatures are response-specific and would cause errors if replayed verbatim.
