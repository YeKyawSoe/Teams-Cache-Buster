from __future__ import annotations

from pathlib import Path

import types

from teams_cache_buster import app as app_module
from teams_cache_buster.models import RunningAppSnapshot
from teams_cache_buster import service


class DummyProcess:
    def __init__(self, name: str, exe: str | None = None):
        self.info = {"name": name, "exe": exe}


def test_detect_running_apps_maps_known_processes(monkeypatch, tmp_path):
    processes = [
        DummyProcess("OUTLOOK.EXE", r"C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE"),
        DummyProcess("Teams.exe", r"C:\\Users\\u\\AppData\\Local\\Microsoft\\Teams\\current\\Teams.exe"),
    ]
    monkeypatch.setattr(service.psutil, "process_iter", lambda attrs: iter(processes))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))

    detected = service.detect_running_apps()

    assert [app.display_name for app in detected] == ["Classic Teams", "Outlook"]
    assert detected[0].cache_paths[0] == Path(tmp_path / "AppData" / "Roaming" / "Microsoft" / "Teams")


def test_run_cleanup_stops_clears_and_relaunches(monkeypatch, tmp_path):
    classic_cache = tmp_path / "AppData" / "Roaming" / "Microsoft" / "Teams"
    new_cache = tmp_path / "AppData" / "Local" / "Packages" / "MSTeams_8wekyb3d8bbwe" / "LocalCache" / "Microsoft" / "MSTeams"
    classic_cache.mkdir(parents=True)
    new_cache.mkdir(parents=True)

    snapshots = [
        RunningAppSnapshot(
            display_name="Classic Teams",
            process_names=("teams.exe",),
            launch_command=("C:\\Teams\\Teams.exe",),
            cache_paths=(classic_cache,),
        ),
        RunningAppSnapshot(
            display_name="Outlook",
            process_names=("outlook.exe",),
            launch_command=("C:\\Office\\OUTLOOK.EXE",),
            cache_paths=(),
        ),
    ]

    monkeypatch.setattr(service, "detect_running_apps", lambda cache_targets=None: snapshots)
    taskkill_calls: list[list[str]] = []
    launcher_calls: list[tuple[str, ...]] = []

    def fake_killer(cmd):
        taskkill_calls.append(list(cmd))

    def fake_launcher(cmd):
        launcher_calls.append(tuple(cmd))
        return types.SimpleNamespace()

    monkeypatch.setattr(service, "clear_cache", lambda paths: list(paths))

    result = service.run_cleanup(killer=fake_killer, sleeper=lambda seconds: None, launcher=fake_launcher)

    assert taskkill_calls == [
        ["taskkill", "/F", "/T", "/IM", "teams.exe"],
        ["taskkill", "/F", "/T", "/IM", "outlook.exe"],
    ]
    assert launcher_calls == [("C:\\Teams\\Teams.exe",), ("C:\\Office\\OUTLOOK.EXE",)]
    assert result.detected_apps == ["Classic Teams", "Outlook"]


def test_clear_cache_deletes_existing_directories(tmp_path):
    cache_dir = tmp_path / "Microsoft" / "Teams"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache.db").write_text("payload", encoding="utf-8")

    removed = service.clear_cache([cache_dir])

    assert removed == [cache_dir]
    assert not cache_dir.exists()


def test_smoke_test_flag_skips_gui(monkeypatch):
    called = []

    monkeypatch.setattr(app_module, "run_smoke_test", lambda: called.append(True))
    monkeypatch.setattr(app_module, "TeamsCacheBusterApp", lambda: (_ for _ in ()).throw(AssertionError("GUI should not start")))

    exit_code = app_module.main(["--smoke-test"])

    assert exit_code == 0
    assert called == [True]
