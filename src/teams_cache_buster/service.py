"""Core Teams cache clearing logic."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

try:
    import psutil
except ImportError:  # pragma: no cover - enforced in packaging/tests
    class _PsutilShim:
        Error = Exception

        @staticmethod
        def process_iter(*args, **kwargs):
            raise RuntimeError("psutil is required to run Teams Cache Buster")

    psutil = _PsutilShim()

from .models import RunningAppSnapshot, WorkflowResult


TaskKiller = Callable[[Sequence[str]], None]
Sleeper = Callable[[float], None]
Launcher = Callable[[Sequence[str]], subprocess.Popen]


@dataclass(frozen=True)
class CacheTargets:
    classic_teams: Path
    new_teams: Path


def default_cache_targets() -> CacheTargets:
    appdata = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Teams"
    localappdata = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Packages"
        / "MSTeams_8wekyb3d8bbwe"
        / "LocalCache"
        / "Microsoft"
        / "MSTeams"
    )
    return CacheTargets(classic_teams=appdata, new_teams=localappdata)


def _normalize_name(name: str | None) -> str:
    return (name or "").strip().lower()


def _default_launchers() -> dict[str, tuple[str, ...]]:
    localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
    classic_candidate = localappdata / "Microsoft" / "Teams" / "current" / "Teams.exe"
    return {
        "Classic Teams": (str(classic_candidate),),
        "New Teams": ("explorer.exe", r"shell:AppsFolder\MSTeams_8wekyb3d8bbwe!MSTeams"),
        "Outlook": ("outlook.exe",),
    }


def detect_running_apps(cache_targets: CacheTargets | None = None) -> list[RunningAppSnapshot]:
    """Return snapshots for Teams/Outlook processes that are currently running."""

    cache_targets = cache_targets or default_cache_targets()
    launchers = _default_launchers()

    snapshots: list[RunningAppSnapshot] = []
    seen: set[str] = set()

    for proc in psutil.process_iter(["name", "exe"]):
        try:
            name = _normalize_name(proc.info.get("name"))
            exe = proc.info.get("exe") or ""
        except (psutil.Error, OSError):
            continue

        for display_name, process_names in (
            ("Classic Teams", ("teams.exe",)),
            ("New Teams", ("msteams.exe", "ms-teams.exe")),
            ("Outlook", ("outlook.exe",)),
        ):
            if display_name in seen:
                continue
            if name not in process_names:
                continue

            launch_command = (exe,) if exe else launchers[display_name]
            cache_paths = _cache_paths_for(display_name, cache_targets)
            snapshots.append(
                RunningAppSnapshot(
                    display_name=display_name,
                    process_names=process_names,
                    launch_command=launch_command,
                    cache_paths=cache_paths,
                )
            )
            seen.add(display_name)

    snapshots.sort(key=lambda item: item.display_name)
    return snapshots


def _cache_paths_for(display_name: str, cache_targets: CacheTargets) -> tuple[Path, ...]:
    if display_name == "Classic Teams":
        return (cache_targets.classic_teams,)
    if display_name == "New Teams":
        return (cache_targets.new_teams,)
    return tuple()


def stop_running_apps(apps: Iterable[RunningAppSnapshot], killer: TaskKiller = subprocess.run, sleeper: Sleeper = time.sleep) -> None:
    """Forcefully terminate the selected apps and give Windows time to release hooks."""

    for app in apps:
        for process_name in app.process_names:
            killer(["taskkill", "/F", "/T", "/IM", process_name],)
            sleeper(1.0)


def clear_cache(paths: Iterable[Path]) -> list[Path]:
    """Delete all cache folders that exist."""

    removed: list[Path] = []
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
            removed.append(path)
    return removed


def relaunch_apps(
    apps: Iterable[RunningAppSnapshot],
    launcher: Launcher = subprocess.Popen,
) -> list[str]:
    """Restart only the apps that were detected before cleanup."""

    relaunched: list[str] = []
    for app in apps:
        try:
            launcher(app.launch_command)
        except (FileNotFoundError, OSError):
            fallback = _default_launchers().get(app.display_name)
            if fallback is None:
                continue
            try:
                launcher(fallback)
            except (FileNotFoundError, OSError):
                continue
        relaunched.append(app.display_name)
    return relaunched


def run_cleanup(
    *,
    cache_targets: CacheTargets | None = None,
    killer: TaskKiller = subprocess.run,
    sleeper: Sleeper = time.sleep,
    launcher: Launcher = subprocess.Popen,
) -> WorkflowResult:
    """Run the full cleanup workflow and return a summary for the UI."""

    detected = detect_running_apps(cache_targets=cache_targets)
    result = WorkflowResult(detected_apps=[app.display_name for app in detected])

    stop_running_apps(detected, killer=killer, sleeper=sleeper)
    sleeper(1.5)

    cache_paths = [path for app in detected for path in app.cache_paths]
    result.cleared_paths = clear_cache(cache_paths)

    result.relaunched_apps = relaunch_apps(detected, launcher=launcher)
    return result
