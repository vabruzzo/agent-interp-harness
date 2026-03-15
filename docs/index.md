# AgentLens

A harness for running multi-session agent trajectories using the Claude Agent SDK, capturing them in [ATIF](https://harborframework.com/docs/agents/trajectory-format) (Agent Trajectory Interchange Format), and tracking file state changes across sessions.

Built for agent interpretability research — studying how LLM agents behave across multi-turn, multi-session, multi-agent interactions.

## What it does

The harness takes a YAML config describing a sequence of sessions (prompts to an agent), runs each session against a working directory via the Claude Agent SDK, and produces structured outputs:

- **ATIF trajectories** — standardized JSON capturing every agent step, tool call, observation, and thinking block
- **Shadow git change tracking** — automatic tracking of all file changes via an invisible git repo, with per-step write attribution and full unified diffs
- **Session chaining** — three modes for controlling how sessions relate to each other (isolated, chained, forked)
- **Replay** — reset the working directory to its exact baseline state and re-run the same prompt to study variance
- **Subagent capture** — separate ATIF trajectories for each subagent invocation, linked to the parent via `SubagentTrajectoryRef`
- **Resampling** — replay specific API turns or entire sessions to study output variance, with intervention testing (edit inputs and resample)

## Next steps

<div class="grid cards" markdown>

- :material-download: **[Installation](getting-started/install.md)** — get set up
- :material-rocket-launch: **[Quick Start](getting-started/quickstart.md)** — run your first experiment
- :material-cog: **[Configuration](guide/configuration.md)** — full config reference
- :material-console: **[CLI Reference](cli.md)** — all commands

</div>
