"""Smart Meter screen: configure where each household's meter data comes from,
test it with 'Sync now', and see the result of the automatic background syncs."""
import tkinter as tk
from tkinter import messagebox, ttk

from hydrohome import config
from hydrohome.ui.widgets import DataTable, HouseholdPicker, form_row, guarded


class MeterView(ttk.Frame):
    title = "Smart Meter"

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.v = {k: tk.StringVar() for k in ("source_type", "location", "api_key",
                                              "reading_path", "unit", "interval_minutes")}
        self.enabled = tk.BooleanVar(value=True)
        ttk.Label(self, text="Smart Meter Auto-Sync", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(self, style="Muted.TLabel", wraplength=900, text=(
            "Connect a smart water meter so readings arrive automatically. Point HydroHome at the "
            "meter's JSON endpoint (or a JSON file) and tell it which field holds the cumulative "
            "meter value. Synced values are saved as normal readings.")).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        form = ttk.LabelFrame(self, text="Meter source", padding=12)
        form.grid(row=2, column=0, sticky="nsew", padx=(0, 14))
        self.picker = form_row(form, 0, "Household *", HouseholdPicker(form))
        form_row(form, 1, "Source type *", ttk.Combobox(form, textvariable=self.v["source_type"],
                 values=config.METER_SOURCE_TYPES, state="readonly"))
        form_row(form, 2, "URL or file path *", ttk.Entry(form, textvariable=self.v["location"], width=28))
        form_row(form, 3, "API key (optional)", ttk.Entry(form, textvariable=self.v["api_key"], show="•"))
        form_row(form, 4, "JSON path of value *", ttk.Entry(form, textvariable=self.v["reading_path"]))
        form_row(form, 5, "Value unit", ttk.Combobox(form, textvariable=self.v["unit"],
                 values=config.METER_UNITS, state="readonly"))
        form_row(form, 6, "Sync every (minutes)", ttk.Spinbox(form, from_=1, to=1440,
                 textvariable=self.v["interval_minutes"]))
        ttk.Checkbutton(form, text="Automatic sync enabled", variable=self.enabled).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(form, style="Muted.TLabel", text="Example path: data.total_m3\nThe API key is stored in the local database.").grid(
            row=8, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(form)
        btns.grid(row=9, column=0, columnspan=2, pady=(12, 0), sticky="w")
        ttk.Button(btns, text="Save", style="Accent.TButton", command=self.save).pack(side="left", padx=2)
        self.sync_btn = ttk.Button(btns, text="⟳ Sync now", command=self.sync_now)
        self.sync_btn.pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=2)

        right = ttk.Frame(self)
        right.grid(row=2, column=1, sticky="nsew")
        ttk.Label(right, text="Configured meters (updates automatically)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.table = DataTable(right, [("household_name", "Household", 95), ("enabled_text", "Auto", 42),
                                       ("last_sync_at", "Last sync", 112), ("last_status", "Last result", 230)])
        self.table.pack(fill="both", expand=True)
        self.table.on_select(self.on_select)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.clear()

    def refresh(self):
        def run():
            self.picker.load(self.app.services.households.list())
            rows = self.app.services.meters.list_sources()
            for r in rows:
                r["enabled_text"] = "On" if r["enabled"] else "Off"
                r["_tag"] = "bad" if r["last_status"].startswith("Failed") else (
                    "ok" if r["last_status"].startswith("OK") else "")
            self.table.set_rows(rows)
        guarded(run)

    def _form(self):
        data = {k: v.get() for k, v in self.v.items()}
        data["household_id"] = self.picker.selected_id() or ""
        data["enabled"] = self.enabled.get()
        return data

    def clear(self):
        for var in self.v.values():
            var.set("")
        self.v["source_type"].set("URL")
        self.v["unit"].set("m3")
        self.v["interval_minutes"].set("60")
        self.enabled.set(True)
        if hasattr(self, "table"):
            self.table.clear_selection()

    def on_select(self):
        sid = self.table.selected_id()
        src = next((s for s in self.app.services.meters.list_sources() if s["id"] == sid), None)
        if src:
            self.picker.select_id(src["household_id"])
            for key in self.v:
                self.v[key].set(str(src[key]))
            self.enabled.set(bool(src["enabled"]))

    def save(self):
        def run():
            self.app.services.meters.save(self._form())
            self.refresh()
            self.app.set_status("Smart meter source saved.")
            messagebox.showinfo("Saved", "Smart meter source saved. Use 'Sync now' to test it.")
        guarded(run)

    def delete(self):
        sid = self.table.selected_id()
        if sid is None:
            return messagebox.showwarning("Select a record", "Select a meter source in the table first.")
        if not messagebox.askyesno("Confirm delete", "Remove this smart meter source?\n"
                                   "(Readings already saved are kept.)"):
            return

        def run():
            self.app.services.meters.delete(sid)
            self.refresh()
            self.clear()
            self.app.set_status("Smart meter source removed.")
        guarded(run)

    def sync_now(self):
        hid = self.picker.selected_id()
        if hid is None:
            return messagebox.showwarning("Choose a household", "Select a household first.")
        if guarded(lambda: self.app.services.meters.save(self._form())) is False:
            return                                   # form invalid: warning already shown
        self.sync_btn.state(["disabled"])
        self.app.set_status("Contacting smart meter…")

        def done(kind, payload):
            self.sync_btn.state(["!disabled"])
            self.refresh()
            if kind == "ok":
                self.app.set_status(payload)
                messagebox.showinfo("Sync complete", payload)
            else:
                self.app.set_status("Smart meter sync failed.")
                messagebox.showerror("Sync failed", payload)
        self.app.run_background(lambda: self.app.services.meters.sync_household(hid), done)
