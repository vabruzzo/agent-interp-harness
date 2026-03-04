"""File state tracking across sessions.

Three levels of granularity:
1. Snapshots: full file copies at each boundary
2. Per-session diffs: unified diff between before/after
3. Per-step write log: fine-grained attribution of changes to step_ids
"""

from __future__ import annotations

import difflib
import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from harness.config import TrackedFile

logger = logging.getLogger(__name__)


def _safe_read_text(path: Path) -> str:
    """Read a file as UTF-8, returning a placeholder for binary/undecodable files."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        logger.warning("Cannot read %s as UTF-8 text; treating as binary.", path)
        return f"[binary file: {path.name}]"


@dataclass
class WriteEvent:
    """A single file write detected between steps."""

    timestamp: str
    session_index: int
    step_id: int
    file_path: str
    diff: str
    content_before: str
    content_after: str
    diff_stats: dict[str, int]


class StateManager:
    """Manages file state snapshots, diffs, and write detection."""

    def __init__(self, repo_path: Path, tracked_files: list[TrackedFile]):
        self.repo_path = repo_path
        self.tracked = tracked_files
        self.write_log: list[WriteEvent] = []
        self._cached_contents: dict[str, str] = {}

    def seed(self) -> None:
        """Initialize tracked files with seed content and cache initial state."""
        for tf in self.tracked:
            target = self.repo_path / tf.path
            target.parent.mkdir(parents=True, exist_ok=True)
            if tf.seed_content is not None:
                target.write_text(tf.seed_content)
            if target.exists():
                self._cached_contents[tf.path] = _safe_read_text(target)
            else:
                self._cached_contents[tf.path] = ""

    def snapshot(self, dest_dir: Path) -> None:
        """Copy all tracked files to dest_dir. Also captures git state if available."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        for tf in self.tracked:
            src = self.repo_path / tf.path
            dst = dest_dir / tf.path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst)
            else:
                sentinel = dst.parent / (dst.name + ".missing")
                sentinel.touch()

        git_dir = self.repo_path / ".git"
        if git_dir.exists():
            try:
                diff_result = subprocess.run(
                    ["git", "diff", "--no-color"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (dest_dir / "git_diff.txt").write_text(diff_result.stdout)

                status_result = subprocess.run(
                    ["git", "status", "--short", "--no-color"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                (dest_dir / "git_status.txt").write_text(status_result.stdout)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

    def diff_session(self, before_dir: Path, after_dir: Path, dest: Path) -> None:
        """Compute unified diff between before and after snapshots."""
        patches: list[str] = []
        for tf in self.tracked:
            before_file = before_dir / tf.path
            after_file = after_dir / tf.path
            before_text = _safe_read_text(before_file) if before_file.exists() else ""
            after_text = _safe_read_text(after_file) if after_file.exists() else ""
            if before_text != after_text:
                diff_lines = difflib.unified_diff(
                    before_text.splitlines(keepends=True),
                    after_text.splitlines(keepends=True),
                    fromfile=f"before/{tf.path}",
                    tofile=f"after/{tf.path}",
                )
                patches.append("".join(diff_lines))

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(patches) if patches else "# No changes detected\n")

    def check_for_writes(self, session_index: int, step_id: int) -> list[WriteEvent]:
        """Compare tracked files to cache. Returns and logs any WriteEvents detected."""
        new_events: list[WriteEvent] = []
        for tf in self.tracked:
            current_path = self.repo_path / tf.path
            previous = self._cached_contents.get(tf.path, "")

            if not current_path.exists():
                if previous:
                    event = self._create_write_event(
                        session_index, step_id, tf.path, previous, ""
                    )
                    new_events.append(event)
                    self._cached_contents[tf.path] = ""
                continue

            current = _safe_read_text(current_path)
            if current != previous:
                event = self._create_write_event(
                    session_index, step_id, tf.path, previous, current
                )
                new_events.append(event)
                self._cached_contents[tf.path] = current

        self.write_log.extend(new_events)
        return new_events

    def _create_write_event(
        self,
        session_index: int,
        step_id: int,
        file_path: str,
        before: str,
        after: str,
    ) -> WriteEvent:
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
            )
        )
        lines = diff.splitlines()
        added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))

        return WriteEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_index=session_index,
            step_id=step_id,
            file_path=file_path,
            diff=diff,
            content_before=before,
            content_after=after,
            diff_stats={"added": added, "removed": removed},
        )

    def save_changelog(self, dest: Path) -> None:
        """Write all write events to a JSONL file."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w") as f:
            for event in self.write_log:
                f.write(json.dumps(asdict(event), default=str) + "\n")

    def refresh_cache(self) -> None:
        """Re-read all tracked files into cache. Call at session boundaries."""
        for tf in self.tracked:
            path = self.repo_path / tf.path
            if path.exists():
                self._cached_contents[tf.path] = _safe_read_text(path)
            else:
                self._cached_contents[tf.path] = ""
