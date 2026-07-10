"""Data models used by the cache clearing workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RunningAppSnapshot:
    """Captures enough state to relaunch an app after cleanup."""

    display_name: str
    process_names: tuple[str, ...]
    launch_command: tuple[str, ...]
    cache_paths: tuple[Path, ...]


@dataclass
class WorkflowResult:
    """Outcome of a cleanup run."""

    detected_apps: list[str] = field(default_factory=list)
    cleared_paths: list[Path] = field(default_factory=list)
    relaunched_apps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

