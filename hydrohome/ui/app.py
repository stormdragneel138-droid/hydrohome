"""Main window: navigation, status bar, and the background reminder checker."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from hydrohome import config
from hydrohome.errors import AppError
from hydrohome.ui.dashboard_view import DashboardView
from hydrohome.ui.households_view import HouseholdsView
from hydrohome.ui.meter_view import MeterView
from hydrohome.ui.readings_view import ReadingsView
from hydrohome.ui.reminders_view import RemindersView
from hydrohome.ui.widgets import COLORS, apply_theme

NAV = (("dashboard", "🏠  Dashboard", DashboardView),
       ("households", "👪  Households", HouseholdsView),
       ("readings", "📟  Meter Readings", ReadingsView),
       ("meters", "📡  Smart Meter", MeterView),
       ("reminders", "⏰  Reminders", RemindersView))


class HydroHomeApp(tk.Tk):
    def __init__(self, services, start_polling=True):
        super().__init__()
        self.services = services
        self.title(f"{config.APP_NAME} - {config.APP_SUBTITLE}")
        self.geometry("1240x740")
        self.minsize(1040, 660)
        apply_theme(self)

        nav = tk.Frame(self, bg=COLORS["nav"], width=210)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text="💧 " + config.APP_NAME, bg=COLORS["nav"], fg="white",
                 font=("Segoe UI", 18, "bold")).pack(pady=(20, 2))
        tk.Label(nav, text="Water reminders\nfor your home", bg=COLORS["nav"], fg="#BFE3F2",
                 font=("Segoe UI", 9)).pack(pady=(0, 18))
        self.nav_buttons = {}
        content = ttk.Frame(self)
        content.pack(side="right", fill="both", expand=True)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(content, textvariable=self.status_var, style="Muted.TLabel", padding=(16, 4)).pack(
            side="bottom", fill="x")
        holder = ttk.Frame(content)
        holder.pack(fill="both", expand=True)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.views = {}
        for key, label, cls in NAV:
            btn = ttk.Button(nav, text=label, style="Nav.TButton", command=lambda k=key: self.show(k))
            btn.pack(fill="x")
            self.nav_buttons[key] = btn
            view = cls(holder, self)
            view.grid(row=0, column=0, sticky="nsew")
            self.views[key] = view
        self.current = None
        self.show("dashboard")
        if start_polling:
            self.after(2000, self._poll_reminders)
            self.after(5000, self._poll_meters)
            self.after(config.DASHBOARD_REFRESH_MS, self._auto_refresh_dashboard)

    def show(self, key):
        self.current = key
        for k, btn in self.nav_buttons.items():
            btn.configure(style="NavActive.TButton" if k == key else "Nav.TButton")
        view = self.views[key]
        view.tkraise()
        view.refresh()

    def set_status(self, text):
        self.status_var.set(text)

    def _poll_reminders(self):
        """Runs every REMINDER_CHECK_MS: pops up reminders that just became due."""
        try:
            due = self.services.reminders.collect_due_alerts()
            if due:
                lines = [f"• {r['title']}  ({r['household_name']}, due {r['due_at']})" for r in due]
                self.set_status(f"{len(due)} reminder(s) due!")
                if self.current == "reminders":
                    self.views["reminders"].load_table()
                elif self.current == "dashboard":
                    self.views["dashboard"].refresh(quiet=True)
                messagebox.showinfo("💧 Water reminder", "\n".join(lines))
        except AppError as exc:
            self.set_status(f"Reminder check failed: {exc}")
        finally:
            self.after(config.REMINDER_CHECK_MS, self._poll_reminders)

    # ---- background work (keeps the window responsive during network calls) ----
    def run_background(self, work, done):
        """Run work() in a thread; call done('ok'|'err', result) back on the Tk thread."""
        results = queue.Queue()

        def worker():
            try:
                results.put(("ok", work()))
            except AppError as exc:
                results.put(("err", str(exc)))
            except Exception as exc:                  # never let a thread die silently
                results.put(("err", f"Unexpected error: {exc}"))

        def poll():
            try:
                kind, payload = results.get_nowait()
            except queue.Empty:
                self.after(150, poll)
                return
            done(kind, payload)

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, poll)

    def _poll_meters(self):
        """Every SYNC_CHECK_MS: sync smart meters whose interval has elapsed."""
        def done(kind, payload):
            if kind == "ok" and payload:
                good = sum(1 for _h, ok, _m in payload if ok)
                bad = len(payload) - good
                self.set_status(f"Smart meter auto-sync: {good} updated"
                                + (f", {bad} failed" if bad else "") + ".")
                if self.current in ("dashboard", "readings", "meters"):
                    self.views[self.current].refresh()
            elif kind == "err":
                self.set_status(f"Smart meter auto-sync error: {payload}")
            self.after(config.SYNC_CHECK_MS, self._poll_meters)
        self.run_background(self.services.meters.sync_due, done)

    def _auto_refresh_dashboard(self):
        """Keeps the dashboard live: usage, chart, reminders and (cached) weather update by themselves."""
        try:
            if self.current == "dashboard":
                self.views["dashboard"].refresh(quiet=True)
        finally:
            self.after(config.DASHBOARD_REFRESH_MS, self._auto_refresh_dashboard)
