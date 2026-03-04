"""CLI entry point for the harness.

Commands:
    harness run <config.yaml> [--model MODEL] [--tag TAG] [--session-mode MODE]
    harness list [--runs-dir DIR]
    harness inspect <run_dir>
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Optional

import typer

from harness.config import SessionMode, load_config

app = typer.Typer(
    name="harness",
    help="Multi-session agent interpretability harness",
    add_completion=False,
)


@app.command()
def run(
    config_path: Annotated[Path, typer.Argument(help="Path to YAML config file")],
    model: Annotated[Optional[str], typer.Option(help="Override model")] = None,
    tag: Annotated[Optional[list[str]], typer.Option(help="Add tags")] = None,
    session_mode: Annotated[Optional[SessionMode], typer.Option(help="Override session mode")] = None,
    run_name: Annotated[Optional[str], typer.Option(help="Custom run name")] = None,
    runs_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("runs"),
) -> None:
    """Run a multi-session experiment from a config file."""
    config = load_config(config_path)

    if model:
        config.model = model
    if tag:
        config.tags.extend(tag)
    if session_mode:
        config.session_mode = session_mode
    if run_name:
        config.run_name = run_name

    from harness.experiment import run_experiment

    run_dir = asyncio.run(run_experiment(config, output_base=runs_dir))
    typer.echo(f"\nOutputs saved to: {run_dir}")


@app.command(name="list")
def list_runs(
    runs_dir: Annotated[Path, typer.Option(help="Runs directory")] = Path("runs"),
) -> None:
    """List all completed runs."""
    if not runs_dir.exists():
        typer.echo("No runs directory found.")
        raise typer.Exit()

    run_dirs = sorted(runs_dir.iterdir())
    if not run_dirs:
        typer.echo("No runs found.")
        raise typer.Exit()

    for d in run_dirs:
        if not d.is_dir():
            continue
        meta_path = d / "run_meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            sessions = meta.get("session_count", "?")
            mode = meta.get("session_mode", "?")
            model_name = meta.get("model", "?")
            steps = meta.get("total_steps", "?")
            cost = meta.get("total_cost_usd")
            cost_str = f"${cost:.4f}" if cost is not None else "n/a"
            errors = len(meta.get("errors", []))
            err_str = f" [{errors} errors]" if errors else ""
            typer.echo(
                f"  {d.name}  |  {model_name}  |  {mode}  |  "
                f"{sessions} sessions, {steps} steps  |  {cost_str}{err_str}"
            )
        else:
            typer.echo(f"  {d.name}  |  (no metadata)")


@app.command()
def inspect(
    run_dir: Annotated[Path, typer.Argument(help="Path to run directory")],
) -> None:
    """Inspect a completed run: sessions, steps, tool calls, writes, compaction."""
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        typer.echo(f"No run_meta.json found in {run_dir}")
        raise typer.Exit(1)

    with open(meta_path) as f:
        meta = json.load(f)

    typer.echo(f"Run: {meta['run_name']}")
    typer.echo(f"Model: {meta['model']} ({meta.get('provider', 'unknown')})")
    typer.echo(f"Mode: {meta['session_mode']}")
    typer.echo(f"Tags: {', '.join(meta.get('tags', []))}")
    typer.echo(f"Total: {meta['total_steps']} steps, {meta['total_tool_calls']} tool calls")

    cost = meta.get("total_cost_usd")
    if cost is not None:
        typer.echo(f"Cost: ${cost:.4f}")

    compactions = meta.get("total_compaction_events", 0)
    if compactions:
        typer.echo(f"Compaction events: {compactions}")

    subagents = meta.get("total_subagent_invocations", 0)
    if subagents:
        typer.echo(f"Subagent invocations: {subagents}")

    typer.echo(f"File writes: {meta['total_file_writes']}")
    typer.echo("")

    for s in meta.get("sessions", []):
        idx = s["session_index"]
        steps = s.get("step_count", 0)
        tools = s.get("tool_call_count", 0)
        cost_s = s.get("total_cost_usd")
        cost_str = f"  ${cost_s:.4f}" if cost_s is not None else ""
        resumed = s.get("resumed_from")
        error = s.get("error")

        resume_str = f"  (resumed from {resumed})" if resumed else ""
        err_str = f"  ERROR: {error[:80]}" if error else ""
        sub_count = s.get("subagent_count", 0)
        sub_str = f", {sub_count} subagents" if sub_count else ""

        typer.echo(
            f"  Session {idx}: {steps} steps, {tools} tool calls"
            f"{cost_str}{sub_str}{resume_str}{err_str}"
        )

    # Show changelog summary
    changelog = run_dir / "state_changelog.jsonl"
    if changelog.exists() and changelog.stat().st_size > 0:
        typer.echo("")
        typer.echo("File changes:")
        with open(changelog) as f:
            for line in f:
                event = json.loads(line)
                stats = event.get("diff_stats", {})
                typer.echo(
                    f"  session {event['session_index']}, step {event['step_id']}: "
                    f"{event['file_path']} "
                    f"(+{stats.get('added', 0)}/-{stats.get('removed', 0)})"
                )


if __name__ == "__main__":
    app()
