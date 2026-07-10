"""Tkinter GUI for Teams Cache Buster."""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from .metadata import APP_NAME, COMPANY_NAME, COPYRIGHT, DESCRIPTION
from .models import WorkflowResult
from .service import clear_cache, detect_running_apps, relaunch_apps, stop_running_apps


@dataclass(frozen=True)
class UiStep:
    label: str


UI_STEPS = [
    UiStep("Waiting for user confirmation"),
    UiStep("Detecting running apps"),
    UiStep("Closing Outlook"),
    UiStep("Closing Teams"),
    UiStep("Clearing cache"),
    UiStep("Relaunching apps"),
    UiStep("Complete"),
]


class TeamsCacheBusterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("640x480")
        self.minsize(640, 480)
        self.configure(bg="#101418")

        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._step_vars: list[tk.StringVar] = []
        self._build_styles()
        self._build_ui()
        self.after(100, self._poll_queue)
        self.after(250, self._populate_initial_state)

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background="#101418")
        style.configure("Card.TFrame", background="#171c22")
        style.configure("Title.TLabel", background="#101418", foreground="#f2f5f7", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background="#101418", foreground="#a9b4bf", font=("Segoe UI", 10))
        style.configure("Body.TLabel", background="#171c22", foreground="#d7dde4", font=("Segoe UI", 10))
        style.configure("Status.TLabel", background="#171c22", foreground="#d7dde4", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 10))
        style.map(
            "Accent.TButton",
            foreground=[("disabled", "#6b7785"), ("!disabled", "#ffffff")],
            background=[("disabled", "#2b333b"), ("active", "#1f6feb"), ("!disabled", "#1b4d9b")],
        )
        style.configure("TProgressbar", troughcolor="#252c35", background="#3b82f6", thickness=8)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=DESCRIPTION, style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(
            header,
            text=f"{COMPANY_NAME}  •  {COPYRIGHT}",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        card = ttk.Frame(root, style="Card.TFrame", padding=18)
        card.pack(fill="both", expand=True, pady=(18, 14))

        self.status_var = tk.StringVar(value="Ready to clear Teams and Outlook cache.")
        ttk.Label(card, textvariable=self.status_var, style="Status.TLabel", wraplength=560).pack(anchor="w")

        self.progress = ttk.Progressbar(card, mode="determinate", maximum=len(UI_STEPS) - 1)
        self.progress.pack(fill="x", pady=(16, 18))

        steps_frame = ttk.Frame(card, style="Card.TFrame")
        steps_frame.pack(fill="both", expand=True)
        for step in UI_STEPS:
            row = ttk.Frame(steps_frame, style="Card.TFrame")
            row.pack(fill="x", pady=4)
            dot = tk.Label(row, text="●", bg="#171c22", fg="#5b6672", font=("Segoe UI", 10))
            dot.pack(side="left", padx=(0, 10))
            text = tk.StringVar(value=step.label)
            self._step_vars.append(text)
            ttk.Label(row, textvariable=text, style="Body.TLabel").pack(side="left", anchor="w")
            row.dot = dot  # type: ignore[attr-defined]

        self._step_rows = steps_frame.winfo_children()

        controls = ttk.Frame(root)
        controls.pack(fill="x")
        self.run_button = ttk.Button(controls, text="Clear Teams Cache", style="Accent.TButton", command=self._begin_workflow)
        self.run_button.pack(side="left")
        self.detail_var = tk.StringVar(value="Close Outlook and Teams before starting if you can.")
        ttk.Label(controls, textvariable=self.detail_var, style="Subtitle.TLabel").pack(side="left", padx=16)

    def _populate_initial_state(self) -> None:
        try:
            detected = detect_running_apps()
        except Exception:
            self.status_var.set("Ready to clear Teams and Outlook cache.")
            self.detail_var.set("Process detection will run when you start the cleanup.")
            return

        if detected:
            self.status_var.set(
                "Detected running apps: " + ", ".join(app.display_name for app in detected) + "."
            )
            self.detail_var.set("The app will close only the apps that are currently running.")
        else:
            self.status_var.set("No Teams or Outlook processes are currently running.")
            self.detail_var.set("Cache cleanup can still proceed safely.")

    def _begin_workflow(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        if not messagebox.askyesno(
            APP_NAME,
            "Teams and Outlook should be closed so cache files can be cleared safely.\n\n"
            "Please save your work first, especially in Outlook.\n\n"
            "Continue?",
            parent=self,
        ):
            return

        self.run_button.configure(state="disabled")
        self._queue.put(("step", 0))
        self._queue.put(("status", "Waiting for user confirmation"))
        self._worker = threading.Thread(target=self._run_workflow, daemon=True)
        self._worker.start()

    def _run_workflow(self) -> None:
        try:
            result = WorkflowResult()

            self._queue.put(("step", 1))
            self._queue.put(("status", "Detecting running apps"))
            detected = detect_running_apps()
            result.detected_apps = [app.display_name for app in detected]

            outlook = [app for app in detected if app.display_name == "Outlook"]
            teams = [app for app in detected if app.display_name != "Outlook"]

            self._queue.put(("step", 2))
            self._queue.put(("status", "Closing Outlook"))
            stop_running_apps(outlook)

            self._queue.put(("step", 3))
            self._queue.put(("status", "Closing Teams"))
            stop_running_apps(teams)

            self._queue.put(("step", 4))
            self._queue.put(("status", "Clearing cache"))
            result.cleared_paths = clear_cache([path for app in detected for path in app.cache_paths])

            self._queue.put(("step", 5))
            self._queue.put(("status", "Relaunching apps"))
            result.relaunched_apps = relaunch_apps(detected)

            self._queue.put(("step", 6))
            self._queue.put(("result", result))
        except Exception as exc:  # pragma: no cover - surfaced in UI
            self._queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "step":
                    self._set_step(int(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "result":
                    self._handle_result(payload)
                elif kind == "error":
                    self._handle_error(str(payload))
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _set_step(self, active_index: int) -> None:
        self.progress["value"] = active_index
        for index, row in enumerate(self._step_rows):
            dot = getattr(row, "dot", None)
            if dot is None:
                continue
            if index < active_index:
                dot.configure(fg="#22c55e")
            elif index == active_index:
                dot.configure(fg="#f59e0b")
            else:
                dot.configure(fg="#5b6672")

    def _handle_result(self, result: WorkflowResult) -> None:
        status = "Cleanup completed."
        if result.relaunched_apps:
            status += " Restarted: " + ", ".join(result.relaunched_apps) + "."
        elif result.detected_apps:
            status += " No apps were relaunched."
        else:
            status += " No running apps were detected."
        self.status_var.set(status)
        self.detail_var.set(
            f"Removed {len(result.cleared_paths)} cache folder(s)."
        )
        self._set_step(len(UI_STEPS) - 1)
        self.run_button.configure(state="normal")

    def _handle_error(self, message: str) -> None:
        self.status_var.set(f"Cleanup failed: {message}")
        self.detail_var.set("Review the error and try again.")
        self.run_button.configure(state="normal")
        messagebox.showerror(APP_NAME, message, parent=self)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run a non-destructive startup check and exit.",
    )
    return parser.parse_args(argv)


def run_smoke_test() -> None:
    detect_running_apps()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.smoke_test:
        run_smoke_test()
        return 0

    app = TeamsCacheBusterApp()
    app.mainloop()
    return 0
