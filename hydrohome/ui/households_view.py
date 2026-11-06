"""Households screen: full CRUD + search."""
import tkinter as tk
from tkinter import messagebox, ttk

from hydrohome import config
from hydrohome.ui.widgets import DataTable, form_row, guarded


class HouseholdsView(ttk.Frame):
    title = "Households"

    def __init__(self, parent, app):
        super().__init__(parent, padding=16)
        self.app = app
        self.vars = {k: tk.StringVar() for k in
                     ("name", "address", "city", "members", "daily_target_liters")}
        self.search = tk.StringVar()
        ttk.Label(self, text="Households", style="Title.TLabel").grid(row=0, column=0, columnspan=2,
                                                                       sticky="w", pady=(0, 10))
        form = ttk.LabelFrame(self, text="Household details", padding=12)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        form_row(form, 0, "Name *", ttk.Entry(form, textvariable=self.vars["name"], width=28))
        form_row(form, 1, "Address", ttk.Entry(form, textvariable=self.vars["address"]))
        form_row(form, 2, "City *", ttk.Entry(form, textvariable=self.vars["city"]))
        form_row(form, 3, "Members *", ttk.Spinbox(form, from_=1, to=30,
                                                   textvariable=self.vars["members"]))
        form_row(form, 4, "Target (L/person/day) *",
                 ttk.Spinbox(form, from_=20, to=500, increment=5,
                             textvariable=self.vars["daily_target_liters"]))
        ttk.Label(form, text="City is used to fetch the weather forecast.",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(form)
        btns.grid(row=6, column=0, columnspan=2, pady=(12, 0), sticky="w")
        ttk.Button(btns, text="Add", style="Accent.TButton", command=self.add).pack(side="left", padx=2)
        ttk.Button(btns, text="Update", command=self.update).pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=2)
        ttk.Button(btns, text="Clear", command=self.clear).pack(side="left", padx=2)

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        entry = ttk.Entry(bar, textvariable=self.search, width=30)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Show all", command=self.reset_search).pack(side="left", padx=4)
        self.table = DataTable(right, [("name", "Name", 150), ("city", "City", 110),
                                       ("members", "Members", 70),
                                       ("daily_target_liters", "Target L/p/day", 100),
                                       ("address", "Address", 190)])
        self.table.pack(fill="both", expand=True)
        self.table.on_select(self.on_select)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.clear()

    def refresh(self):
        guarded(lambda: self.table.set_rows(self.app.services.households.list(self.search.get())))

    def reset_search(self):
        self.search.set("")
        self.refresh()

    def _form(self):
        return {k: v.get() for k, v in self.vars.items()}

    def clear(self):
        for key, var in self.vars.items():
            var.set("")
        self.vars["members"].set("4")
        self.vars["daily_target_liters"].set(str(config.DEFAULT_TARGET_LITERS))
        if hasattr(self, "table"):
            self.table.clear_selection()

    def on_select(self):
        hid = self.table.selected_id()
        hh = self.app.services.households.get(hid) if hid else None
        if hh:
            for key, var in self.vars.items():
                var.set(str(hh[key]))

    def add(self):
        def run():
            self.app.services.households.add(self._form())
            self.refresh()
            self.clear()
            self.app.set_status("Household added.")
            messagebox.showinfo("Saved", "Household added successfully.")
        guarded(run)

    def update(self):
        hid = self.table.selected_id()
        if hid is None:
            return messagebox.showwarning("Select a record", "Select a household in the table first.")

        def run():
            self.app.services.households.update(hid, self._form())
            self.refresh()
            self.app.set_status("Household updated.")
            messagebox.showinfo("Saved", "Household updated successfully.")
        guarded(run)

    def delete(self):
        hid = self.table.selected_id()
        if hid is None:
            return messagebox.showwarning("Select a record", "Select a household in the table first.")
        if not messagebox.askyesno("Confirm delete",
                                   "Delete this household AND all of its readings and reminders?"):
            return

        def run():
            self.app.services.households.delete(hid)
            self.refresh()
            self.clear()
            self.app.set_status("Household deleted.")
        guarded(run)
