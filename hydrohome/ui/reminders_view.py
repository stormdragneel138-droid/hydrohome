"""Reminders screen: CRUD, status filter, mark done (rolls repeats), CSV export."""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

from hydrohome import config
from hydrohome.ui.widgets import DataTable, HouseholdPicker, form_row, guarded


class RemindersView(ttk.Frame):
    title = "Reminders"

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.v = {k: tk.StringVar() for k in ("title", "reminder_type", "due_date", "due_time",
                                              "repeat_rule", "notes")}
        self.search, self.status = tk.StringVar(), tk.StringVar(value="All")
        ttk.Label(self, text="Reminders", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        form = ttk.LabelFrame(self, text="Reminder details", padding=12)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self.picker = form_row(form, 0, "Household *", HouseholdPicker(form))
        form_row(form, 1, "Title *", ttk.Entry(form, textvariable=self.v["title"], width=30))
        form_row(form, 2, "Type *", ttk.Combobox(form, textvariable=self.v["reminder_type"],
                                                 values=config.REMINDER_TYPES, state="readonly"))
        form_row(form, 3, "Due date *", ttk.Entry(form, textvariable=self.v["due_date"]))
        form_row(form, 4, "Due time (HH:MM) *", ttk.Entry(form, textvariable=self.v["due_time"]))
        form_row(form, 5, "Repeat", ttk.Combobox(form, textvariable=self.v["repeat_rule"],
                                                 values=config.REPEAT_RULES, state="readonly"))
        form_row(form, 6, "Notes", ttk.Entry(form, textvariable=self.v["notes"]))
        btns = ttk.Frame(form)
        btns.grid(row=7, column=0, columnspan=2, pady=(12, 0), sticky="w")
        ttk.Button(btns, text="Add", style="Accent.TButton", command=self.add).pack(side="left", padx=2)
        ttk.Button(btns, text="Update", command=self.update).pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=2)
        ttk.Button(form, text="✔ Mark selected as done", command=self.complete).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Export reminders (CSV)", command=self.export_csv).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(0, 6))
        status_box = ttk.Combobox(bar, textvariable=self.status, state="readonly", width=10,
                                  values=("All", config.STATUS_PENDING, config.STATUS_DONE))
        status_box.pack(side="left")
        status_box.bind("<<ComboboxSelected>>", lambda _e: self.load_table())
        entry = ttk.Entry(bar, textvariable=self.search, width=26)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.load_table())
        ttk.Button(bar, text="Search", command=self.load_table).pack(side="left")
        ttk.Button(bar, text="Show all", command=self.reset_search).pack(side="left", padx=4)
        ttk.Label(right, text="Red rows are overdue.", style="Muted.TLabel").pack(anchor="w")
        self.table = DataTable(right, [("due_at", "Due", 115), ("household_name", "Household", 110),
                                       ("title", "Title", 220), ("reminder_type", "Type", 105),
                                       ("repeat_rule", "Repeat", 65), ("status", "Status", 65)])
        self.table.pack(fill="both", expand=True)
        self.table.on_select(self.on_select)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.clear()

    def refresh(self):
        def run():
            self.picker.load(self.app.services.households.list())
            self.load_table()
        guarded(run)

    def load_table(self):
        def run():
            status = None if self.status.get() == "All" else self.status.get()
            rows = self.app.services.reminders.list(status, self.search.get())
            now = datetime.now().strftime(config.DATETIME_FMT)
            for r in rows:
                if r["status"] == config.STATUS_DONE:
                    r["_tag"] = "muted"
                elif r["due_at"] <= now:
                    r["_tag"] = "bad"
            self.table.set_rows(rows)
        guarded(run)

    def reset_search(self):
        self.search.set("")
        self.status.set("All")
        self.load_table()

    def prefill(self, household_id, title, rtype, due_at):
        """Used by the dashboard to hand over a weather suggestion."""
        self.picker.select_id(household_id)
        self.v["title"].set(title)
        self.v["reminder_type"].set(rtype)
        self.v["due_date"].set(due_at[:10])
        self.v["due_time"].set(due_at[11:16])

    def _form(self):
        data = {k: v.get() for k, v in self.v.items()}
        data["household_id"] = self.picker.selected_id() or ""
        return data

    def clear(self):
        for var in self.v.values():
            var.set("")
        soon = datetime.now() + timedelta(days=1)
        self.v["reminder_type"].set(config.REMINDER_TYPES[0])
        self.v["repeat_rule"].set("None")
        self.v["due_date"].set(soon.strftime(config.DATE_FMT))
        self.v["due_time"].set("08:00")
        if hasattr(self, "table"):
            self.table.clear_selection()

    def on_select(self):
        rid = self.table.selected_id()
        row = next((r for r in self.app.services.reminders.list() if r["id"] == rid), None) if rid else None
        if row:
            self.picker.select_id(row["household_id"])
            self.v["title"].set(row["title"])
            self.v["reminder_type"].set(row["reminder_type"])
            self.v["due_date"].set(row["due_at"][:10])
            self.v["due_time"].set(row["due_at"][11:16])
            self.v["repeat_rule"].set(row["repeat_rule"])
            self.v["notes"].set(row["notes"])

    def add(self):
        def run():
            self.app.services.reminders.add(self._form())
            self.load_table()
            self.clear()
            self.app.set_status("Reminder added.")
            messagebox.showinfo("Saved", "Reminder added successfully.")
        guarded(run)

    def update(self):
        rid = self.table.selected_id()
        if rid is None:
            return messagebox.showwarning("Select a record", "Select a reminder in the table first.")

        def run():
            self.app.services.reminders.update(rid, self._form())
            self.load_table()
            self.app.set_status("Reminder updated.")
            messagebox.showinfo("Saved", "Reminder updated successfully.")
        guarded(run)

    def delete(self):
        rid = self.table.selected_id()
        if rid is None:
            return messagebox.showwarning("Select a record", "Select a reminder in the table first.")
        if not messagebox.askyesno("Confirm delete", "Delete the selected reminder?"):
            return

        def run():
            self.app.services.reminders.delete(rid)
            self.load_table()
            self.clear()
            self.app.set_status("Reminder deleted.")
        guarded(run)

    def complete(self):
        rid = self.table.selected_id()
        if rid is None:
            return messagebox.showwarning("Select a record", "Select a reminder in the table first.")

        def run():
            msg = self.app.services.reminders.complete(rid)
            self.load_table()
            self.app.set_status(msg)
        guarded(run)

    def export_csv(self):
        config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=config.EXPORT_DIR, initialfile="reminders.csv",
                                            defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return

        def run():
            status = None if self.status.get() == "All" else self.status.get()
            n = self.app.services.reports.export_reminders(path, status, self.search.get())
            self.app.set_status(f"Exported {n} reminders.")
            messagebox.showinfo("Export complete", f"{n} reminder(s) saved to:\n{path}")
        guarded(run)
