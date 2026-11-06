"""Dashboard: usage summary, chart, upcoming reminders, and weather-based advice (REST API)."""
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from hydrohome.errors import AppError
from hydrohome.services import advisor, consumption
from hydrohome.services.weather_service import ForecastCache
from hydrohome.ui.widgets import COLORS, STATUS_COLORS, DataTable, HouseholdPicker, guarded


class DashboardView(ttk.Frame):
    title = "Dashboard"
    CHART_W, CHART_H = 460, 210

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.suggestions = []
        self.cache = ForecastCache()
        self._wx_busy = False
        self._rendered = None          # (household_id, city) currently shown in the weather panel
        self.updated = tk.StringVar()
        self.stat = {k: tk.StringVar(value="-") for k in ("latest", "avg", "status", "pending")}

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(top, text="Dashboard", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="↻ Refresh", command=self.refresh).pack(side="right")
        self.picker = HouseholdPicker(top, width=26)
        self.picker.pack(side="right", padx=8)
        self.picker.bind("<<ComboboxSelected>>", lambda _e: self.load_household())
        ttk.Label(top, textvariable=self.updated, style="Muted.TLabel").pack(side="right", padx=8)

        cards = ttk.Frame(self)
        cards.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.status_label = None
        for i, (key, caption) in enumerate((("latest", "Latest usage (m³)"),
                                            ("avg", "Avg litres / person / day"),
                                            ("status", "Status vs. target"),
                                            ("pending", "Pending reminders"))):
            card = ttk.Frame(cards, style="Card.TFrame", padding=12)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1)
            ttk.Label(card, text=caption, style="Card.TLabel", foreground=COLORS["muted"]).pack(anchor="w")
            lbl = ttk.Label(card, textvariable=self.stat[key], style="Big.TLabel")
            lbl.pack(anchor="w")
            if key == "status":
                self.status_label = lbl

        left = ttk.LabelFrame(self, text="Daily use per person (last 6 periods)", padding=8)
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        self.chart = tk.Canvas(left, width=self.CHART_W, height=self.CHART_H,
                               bg="white", highlightthickness=0)
        self.chart.pack()
        ttk.Label(left, text="Tips for your household", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.tips = tk.Message(left, width=self.CHART_W - 30, bg=COLORS["bg"], fg=COLORS["text"],
                               font=("Segoe UI", 10), anchor="w", justify="left")
        self.tips.pack(fill="x", anchor="w")

        right = ttk.Frame(self)
        right.grid(row=2, column=1, sticky="nsew")
        up = ttk.LabelFrame(right, text="Upcoming reminders", padding=6)
        up.pack(fill="x")
        self.upcoming = DataTable(up, [("due_at", "Due", 115), ("title", "Title", 230),
                                       ("reminder_type", "Type", 100)], height=4)
        self.upcoming.pack(fill="x")

        wx = ttk.LabelFrame(right, text="Weather advice (Open-Meteo REST API)", padding=8)
        wx.pack(fill="both", expand=True, pady=(10, 0))
        row = ttk.Frame(wx)
        row.pack(fill="x")
        self.fetch_btn = ttk.Button(row, text="☁ Refresh forecast", style="Accent.TButton",
                                    command=self.fetch_weather)
        self.fetch_btn.pack(side="left")
        self.wx_status = tk.StringVar(value="Forecast loads automatically for the selected household.")
        ttk.Label(row, textvariable=self.wx_status, style="Muted.TLabel", wraplength=330).pack(side="left", padx=8)
        self.forecast = DataTable(wx, [("date", "Date", 90), ("hi", "Max °C", 60), ("lo", "Min °C", 60),
                                       ("rain", "Rain mm", 65), ("prob", "Rain %", 60)], height=3)
        self.forecast.pack(fill="x", pady=6)
        self.advice = tk.Listbox(wx, height=3, activestyle="none")
        self.advice.pack(fill="x")
        self.advice.bind("<<ListboxSelect>>", self._show_reason)
        self.reason = tk.StringVar()
        ttk.Label(wx, textvariable=self.reason, style="Muted.TLabel", wraplength=420).pack(anchor="w", pady=(4, 0))
        ttk.Button(wx, text="＋ Create reminder from selected advice",
                   command=self.create_from_advice).pack(anchor="w", pady=(6, 0))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

    # ---- data ---------------------------------------------------------------
    def _run(self, fn, quiet):
        """Normal runs show error dialogs; the silent auto-refresh only updates the status bar."""
        if not quiet:
            return guarded(fn)
        try:
            fn()
        except AppError as exc:
            self.app.set_status(f"Dashboard refresh failed: {exc}")

    def refresh(self, quiet=False):
        def run():
            self.picker.load(self.app.services.households.list())
            self.load_household(quiet=quiet)
        self._run(run, quiet)

    def load_household(self, quiet=False):
        hid = self.picker.selected_id()
        if hid is None:
            self.stat["latest"].set("-")
            self.stat["avg"].set("-")
            self.stat["status"].set("No household")
            self.stat["pending"].set("0")
            self._draw_chart([], 100)
            self.tips.config(text="Add a household first (Households screen).")
            self.upcoming.set_rows([])
            return

        def run():
            periods, hh = self.app.services.readings.periods_for(hid)
            s = consumption.summarize(periods, hh["members"], hh["daily_target_liters"])
            self.stat["latest"].set(f"{s['latest'].used_m3:.2f}" if s["latest"] else "-")
            self.stat["avg"].set(f"{s['avg_liters_per_person_day']:.0f}" if periods else "-")
            self.stat["status"].set(s["status"] if periods else "No data")
            self.status_label.configure(foreground=STATUS_COLORS.get(s["status"], COLORS["text"]))
            self.stat["pending"].set(str(len(self.app.services.reminders.list("Pending", "", hid))))
            self._draw_chart(periods, hh["daily_target_liters"])
            self.tips.config(text="\n".join("• " + t for t in consumption.tips_for(s["status"])))
            self.upcoming.set_rows(self.app.services.reminders.upcoming(hid, 4))
            self.updated.set(f"Auto-updating · last {datetime.now():%H:%M:%S}")
            self.maybe_fetch_weather(hid, hh["city"])
        self._run(run, quiet)

    def _draw_chart(self, periods, target):
        c, w, h = self.chart, self.CHART_W, self.CHART_H
        c.delete("all")
        if not periods:
            c.create_text(w / 2, h / 2, text="No usage data yet.\nAdd at least two meter readings.",
                          fill=COLORS["muted"], justify="center")
            return
        data = periods[-6:]
        top = max(max(p.liters_per_person_day for p in data), target) * 1.25
        left, bottom, head = 40, h - 28, 20
        slot = (w - left - 10) / len(data)
        scale = (bottom - head) / top
        for i, p in enumerate(data):
            x0, x1 = left + i * slot + 10, left + (i + 1) * slot - 10
            y = bottom - p.liters_per_person_day * scale
            c.create_rectangle(x0, y, x1, bottom, fill=STATUS_COLORS[p.status], outline="")
            c.create_text((x0 + x1) / 2, y - 8, text=f"{p.liters_per_person_day:.0f}", font=("Segoe UI", 9))
            c.create_text((x0 + x1) / 2, bottom + 12, text=p.end.strftime("%b %d"), font=("Segoe UI", 8),
                          fill=COLORS["muted"])
        ty = bottom - target * scale
        c.create_line(left, ty, w - 8, ty, dash=(4, 3), fill=COLORS["bad"])
        c.create_text(left - 4, ty, text=f"{target}", anchor="e", fill=COLORS["bad"], font=("Segoe UI", 8))
        c.create_line(left, bottom, w - 8, bottom, fill=COLORS["muted"])

    # ---- REST API (background thread keeps the window responsive) -------------
    def fetch_weather(self):
        """Manual button: always fetch now and report problems in a dialog."""
        hid = self.picker.selected_id()
        if hid is None:
            return messagebox.showwarning("Select a household", "Choose a household first.")
        hh = self.app.services.households.get(hid)
        self.maybe_fetch_weather(hid, hh["city"], force=True, interactive=True)

    def maybe_fetch_weather(self, hid, city, force=False, interactive=False):
        """Called by every dashboard refresh: shows the cached forecast instantly and only
        contacts the API when the cache is empty or older than WEATHER_REFRESH_SECONDS."""
        key = (hid, city)
        if not force:
            forecast, when = self.cache.get(hid, city)
            if forecast and self._rendered != key:
                self._render_forecast(forecast, when)
                self._rendered = key
            if not self.cache.should_fetch(hid, city):
                return
        if self._wx_busy:
            return
        self._wx_busy = True
        self.fetch_btn.state(["disabled"])
        self.wx_status.set("Updating forecast…")

        def done(kind, payload):
            self._wx_busy = False
            self.fetch_btn.state(["!disabled"])
            if kind == "ok":
                self.cache.store(hid, city, payload)
                if self.picker.selected_id() == hid:          # user may have switched household
                    self._render_forecast(payload, datetime.now())
                    self._rendered = key
                return
            self.cache.mark_failed(hid, city)
            if self.picker.selected_id() == hid:
                self.wx_status.set(f"⚠ {payload} (will retry automatically)")
            if interactive:
                messagebox.showerror("Weather unavailable", payload)

        self.app.run_background(lambda: self.app.services.weather.forecast_for_household(hid), done)

    def _render_forecast(self, f, when):
        stamp = f" · updated {when:%H:%M}" if when else ""
        self.wx_status.set(f"{f.place}: now {f.current_temp:.0f}°C, humidity {f.humidity}%{stamp}")
        self.forecast.set_rows([{"id": i, "date": d.date, "hi": f"{d.temp_max:.0f}",
                                 "lo": f"{d.temp_min:.0f}", "rain": f"{d.rain_mm:.1f}",
                                 "prob": d.rain_probability} for i, d in enumerate(f.days)])
        self.suggestions = advisor.weather_suggestions(f)
        self.advice.delete(0, "end")
        self.reason.set("")
        for sug in self.suggestions:
            self.advice.insert("end", sug.title)
        if not self.suggestions:
            self.advice.insert("end", "No weather-based action needed in the next few days.")

    def _show_reason(self, _event=None):
        sel = self.advice.curselection()
        if sel and sel[0] < len(self.suggestions):
            self.reason.set(self.suggestions[sel[0]].reason)

    def create_from_advice(self):
        sel = self.advice.curselection()
        if not sel or sel[0] >= len(self.suggestions):
            return messagebox.showwarning("Select advice", "Select a suggestion in the list first.")
        sug = self.suggestions[sel[0]]
        self.app.show("reminders")
        self.app.views["reminders"].prefill(self.picker.selected_id(), sug.title,
                                            sug.reminder_type, sug.due_at)
        self.app.set_status("Suggestion copied into the reminder form - review it and click Add.")
