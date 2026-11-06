"""Meter readings screen: CRUD, filtering, CSV export/import, usage report."""
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from hydrohome import config
from hydrohome.ui.widgets import STATUS_COLORS, DataTable, HouseholdPicker, form_row, guarded


class ReadingsView(ttk.Frame):
    title = "Meter Readings"

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.v_date, self.v_meter, self.v_notes = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.search = tk.StringVar()
        ttk.Label(self, text="Meter Readings", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        form = ttk.LabelFrame(self, text="Reading details", padding=12)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self.form_picker = form_row(form, 0, "Household *", HouseholdPicker(form))
        form_row(form, 1, "Date (YYYY-MM-DD) *", ttk.Entry(form, textvariable=self.v_date))
        form_row(form, 2, "Meter reading (m³) *", ttk.Entry(form, textvariable=self.v_meter))
        form_row(form, 3, "Notes", ttk.Entry(form, textvariable=self.v_notes))
        ttk.Label(form, text="Read the number on your water meter. It should\nnever be lower than the previous reading.",
                  style="Muted.TLabel").grid(row=4, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(form)
        btns.grid(row=5, column=0, columnspan=2, pady=(12, 0), sticky="w")
        ttk.Button(btns, text="Add", style="Accent.TButton", command=self.add).pack(side="left", padx=2)
        ttk.Button(btns, text="Update", command=self.update).pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=2)
        files = ttk.LabelFrame(form, text="Files & reports", padding=8)
        files.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Button(files, text="Export readings (CSV)", command=self.export_csv).pack(fill="x", pady=2)
        ttk.Button(files, text="Import readings (CSV)", command=self.import_csv).pack(fill="x", pady=2)
        ttk.Button(files, text="Save usage report (TXT)", command=self.save_report).pack(fill="x", pady=2)

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(0, 6))
        self.filter_picker = HouseholdPicker(bar, include_all=True, width=22)
        self.filter_picker.pack(side="left")
        self.filter_picker.bind("<<ComboboxSelected>>", lambda _e: self.load_table())
        entry = ttk.Entry(bar, textvariable=self.search, width=22)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.load_table())
        ttk.Button(bar, text="Search", command=self.load_table).pack(side="left")
        ttk.Button(bar, text="Show all", command=self.reset_search).pack(side="left", padx=4)
        self.table = DataTable(right, [("reading_date", "Date", 90), ("household_name", "Household", 120),
                                       ("meter_reading", "Meter m³", 80), ("used_m3", "Used m³", 70),
                                       ("liters_per_person_day", "L/person/day", 95),
                                       ("status", "Status", 100), ("notes", "Notes", 140)])
        self.table.pack(fill="both", expand=True)
        self.table.on_select(self.on_select)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.clear()

    # ---- data -----------------------------------------------------------
    def refresh(self):
        def run():
            households = self.app.services.households.list()
            self.form_picker.load(households)
            self.filter_picker.load(households)
            self.load_table()
        guarded(run)

    def load_table(self):
        def run():
            rows = self.app.services.readings.list_with_usage(
                self.filter_picker.selected_id(), self.search.get())
            for r in rows:
                r["_tag"] = {"Over target": "bad", "Within target": "ok"}.get(r["status"], "")
            self.table.set_rows(rows)
        guarded(run)

    def reset_search(self):
        self.search.set("")
        if self.filter_picker["values"]:
            self.filter_picker.current(0)
        self.load_table()

    def _form(self):
        return {"household_id": self.form_picker.selected_id() or "", "reading_date": self.v_date.get(),
                "meter_reading": self.v_meter.get(), "notes": self.v_notes.get()}

    def clear(self):
        self.v_date.set(date.today().strftime(config.DATE_FMT))
        self.v_meter.set("")
        self.v_notes.set("")
        if hasattr(self, "table"):
            self.table.clear_selection()

    def on_select(self):
        rid = self.table.selected_id()
        row = next((r for r in self.app.services.readings.readings.list_filtered()
                    if r["id"] == rid), None) if rid else None
        if row:
            self.form_picker.select_id(row["household_id"])
            self.v_date.set(row["reading_date"])
            self.v_meter.set(str(row["meter_reading"]))
            self.v_notes.set(row["notes"])

    # ---- CRUD ------------------------------------------------------------
    def add(self):
        def run():
            self.app.services.readings.add(self._form())
            self.load_table()
            self.clear()
            self.app.set_status("Reading saved.")
            messagebox.showinfo("Saved", "Meter reading added successfully.")
        guarded(run)

    def update(self):
        rid = self.table.selected_id()
        if rid is None:
            return messagebox.showwarning("Select a record", "Select a reading in the table first.")

        def run():
            self.app.services.readings.update(rid, self._form())
            self.load_table()
            self.app.set_status("Reading updated.")
            messagebox.showinfo("Saved", "Meter reading updated successfully.")
        guarded(run)

    def delete(self):
        rid = self.table.selected_id()
        if rid is None:
            return messagebox.showwarning("Select a record", "Select a reading in the table first.")
        if not messagebox.askyesno("Confirm delete", "Delete the selected reading?"):
            return

        def run():
            self.app.services.readings.delete(rid)
            self.load_table()
            self.clear()
            self.app.set_status("Reading deleted.")
        guarded(run)

    # ---- files -----------------------------------------------------------
    def _save_dialog(self, default, ext, label):
        config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        return filedialog.asksaveasfilename(initialdir=config.EXPORT_DIR, initialfile=default,
                                            defaultextension=ext, filetypes=[(label, f"*{ext}")])

    def export_csv(self):
        path = self._save_dialog("water_readings.csv", ".csv", "CSV files")
        if not path:
            return

        def run():
            n = self.app.services.reports.export_readings(
                path, self.filter_picker.selected_id(), self.search.get())
            self.app.set_status(f"Exported {n} readings.")
            messagebox.showinfo("Export complete", f"{n} reading(s) saved to:\n{path}")
        guarded(run)

    def import_csv(self):
        hid = self.form_picker.selected_id()
        if hid is None:
            return messagebox.showwarning("Choose a household",
                                          "Pick the household (left form) to import readings into.")
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return

        def run():
            added, errors = self.app.services.reports.import_readings(path, hid)
            self.load_table()
            msg = f"Imported {added} reading(s)."
            if errors:
                msg += f"\n\n{len(errors)} row(s) skipped:\n" + "\n".join(errors[:8])
                if len(errors) > 8:
                    msg += f"\n…and {len(errors) - 8} more."
            (messagebox.showwarning if errors else messagebox.showinfo)("Import result", msg)
            self.app.set_status(f"Imported {added} reading(s).")
        guarded(run)

    def save_report(self):
        hid = self.filter_picker.selected_id() or self.form_picker.selected_id()
        if hid is None:
            return messagebox.showwarning("Choose a household", "Select a household first.")
        path = self._save_dialog("usage_report.txt", ".txt", "Text files")
        if not path:
            return

        def run():
            self.app.services.reports.save_usage_report(path, hid)
            self.app.set_status("Report saved.")
            messagebox.showinfo("Report saved", f"Usage report saved to:\n{path}")
        guarded(run)
