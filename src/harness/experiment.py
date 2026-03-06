"""Multi-session experiment orchestrator.

Runs sessions sequentially, passing session IDs forward based on session_mode:
- isolated: no resume, fresh each time
- chained: resume from previous session_id
- forked: fork from first session_id
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path

import yaml

from harness.config import RunConfig, SessionMode
from harness.runner import SessionResult, run_session
from harness.state import StateManager

logger = logging.getLogger(__name__)


async def run_experiment(config: RunConfig, output_base: Path | None = None) -> Path:
    """Run a complete multi-session experiment.

    Returns:
        Path to the run directory.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    model_slug = config.model.replace("/", "_").replace(":", "_")
    run_name = config.run_name or f"{timestamp}_{model_slug}"

    base = output_base or Path("runs")
    run_dir = base / run_name
    if run_dir.exists():
        raise FileExistsError(
            f"Run directory already exists: {run_dir}. "
            "Use a different --run-name or remove the existing directory."
        )
    run_dir.mkdir(parents=True)

    # Save frozen config
    with open(run_dir / "config.yaml", "w") as f:
        yaml.dump(config.model_dump(mode="json"), f, default_flow_style=False, sort_keys=False)

    # Initialize state manager
    state = StateManager(
        repo_path=Path(config.repo_path),
        tracked_files=config.tracked_files,
    )
    state.seed()
    state.snapshot(run_dir / "state_init")

    # Run sessions
    results: list[SessionResult] = []
    first_session_id: str | None = None

    for sc in sorted(config.sessions, key=lambda s: s.session_index):
        session_dir = run_dir / f"session_{sc.session_index:02d}"

        # Determine resume behavior based on session_mode
        resume_id: str | None = None
        fork = False

        if config.session_mode == SessionMode.CHAINED and results:
            resume_id = results[-1].session_id
            if resume_id is None:
                logger.warning(
                    "Cannot chain session %d: previous session returned no session_id. "
                    "Falling back to isolated.",
                    sc.session_index,
                )
        elif config.session_mode == SessionMode.FORKED and first_session_id:
            resume_id = first_session_id
            fork = True

        mode_desc = config.session_mode.value
        resume_desc = f", resume={resume_id}" if resume_id else ""
        fork_desc = ", fork=True" if fork else ""
        print(f"[session {sc.session_index}] starting (mode={mode_desc}{resume_desc}{fork_desc})...")

        try:
            result = await run_session(
                session_config=sc,
                run_config=config,
                session_dir=session_dir,
                state_manager=state,
                resume_session_id=resume_id,
                fork=fork,
            )
        except Exception as e:
            logger.exception("Session %d crashed", sc.session_index)
            result = SessionResult(
                session_index=sc.session_index,
                error=f"CRASHED: {e}",
                started_at=datetime.now(timezone.utc).isoformat(),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        results.append(result)

        if sc.session_index == 1 and result.session_id:
            first_session_id = result.session_id

        status = "ERROR" if result.error else "done"
        cost_str = f", ${result.total_cost_usd:.4f}" if result.total_cost_usd is not None else ""
        compact_str = (
            f", {result.compaction_count} compactions" if result.compaction_count else ""
        )
        subagent_str = (
            f", {result.subagent_count} subagents" if result.subagent_count else ""
        )
        print(
            f"[session {sc.session_index}] {status} -- "
            f"{result.step_count} steps, {result.tool_call_count} tool calls"
            f"{cost_str}{compact_str}{subagent_str}"
        )
        if result.error:
            print(f"  error: {result.error[:200]}")

    # Final state
    state.snapshot(run_dir / "state_final")
    state.save_changelog(run_dir / "state_changelog.jsonl")

    # Build run metadata
    meta = _build_run_meta(config, run_name, results, state)
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"\nRun complete: {run_dir}")
    return run_dir


def _build_run_meta(
    config: RunConfig,
    run_name: str,
    results: list[SessionResult],
    state: StateManager,
) -> dict:
    def _get_version(pkg: str) -> str | None:
        try:
            return pkg_version(pkg)
        except Exception:
            return None

    return {
        "run_name": run_name,
        "hypothesis": config.hypothesis,
        "model": config.model,
        "provider": config.provider,
        "sdk_version": _get_version("claude-agent-sdk"),
        "harness_version": _get_version("agent-interp-harness"),
        "session_mode": config.session_mode.value,
        "repo_path": config.repo_path,
        "repo_name": config.repo_name,
        "tags": config.tags,
        "session_count": len(results),
        "sessions": [
            {
                "session_index": r.session_index,
                "session_id": r.session_id,
                "resumed_from": r.resumed_from,
                "step_count": r.step_count,
                "tool_call_count": r.tool_call_count,
                "num_turns": r.num_turns,
                "total_cost_usd": r.total_cost_usd,
                "compaction_count": r.compaction_count,
                "subagent_count": r.subagent_count,
                "error": r.error,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
            }
            for r in results
        ],
        "started_at": results[0].started_at if results else None,
        "finished_at": results[-1].finished_at if results else None,
        "total_steps": sum(r.step_count for r in results),
        "total_tool_calls": sum(r.tool_call_count for r in results),
        "total_cost_usd": (
            sum(r.total_cost_usd for r in results if r.total_cost_usd is not None)
            if any(r.total_cost_usd is not None for r in results)
            else None
        ),
        "total_file_writes": len(state.write_log),
        "total_compaction_events": sum(r.compaction_count for r in results),
        "total_subagent_invocations": sum(r.subagent_count for r in results),
        "errors": [r.error for r in results if r.error],
    }
