"""Reusable Tkinter building blocks and the shared error-dialog helper."""
import tkinter as tk
from tkinter import messagebox, ttk

from hydrohome.errors import AppError, ValidationError

COLORS = {"bg": "#F2F8FC", "nav": "#0B4F6C", "nav_active": "#1B7BA3", "accent": "#1B98C9",
          "card": "#FFFFFF", "text": "#16324F", "muted": "#6B7F90",
          "ok": "#2E9E5B", "warn": "#E0A100", "bad": "#D64545"}
STATUS_COLORS = {"Within target": COLORS["ok"], "Near limit": COLORS["warn"],
                 "Over target": COLORS["bad"]}


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=COLORS["bg"])
    style.configure(".", font=("Segoe UI", 10), background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Card.TFrame", background=COLORS["card"], relief="solid", borderwidth=1)
    style.configure("TLabel", background=COLORS["bg"])
    style.configure("Card.TLabel", background=COLORS["card"])
    style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
    style.configure("Muted.TLabel", foreground=COLORS["muted"])
    style.configure("Big.TLabel", font=("Segoe UI", 18, "bold"), background=COLORS["card"])
    style.configure("TLabelframe", background=COLORS["bg"])
    style.configure("TLabelframe.Label", background=COLORS["bg"], font=("Segoe UI", 10, "bold"))
    style.configure("TButton", padding=6)
    style.configure("Accent.TButton", background=COLORS["accent"], foreground="white")
    style.map("Accent.TButton", background=[("active", COLORS["nav_active"])])
    style.configure("Danger.TButton", foreground=COLORS["bad"])
    style.configure("Nav.TButton", background=COLORS["nav"], foreground="white",
                    padding=(14, 10), anchor="w", borderwidth=0, font=("Segoe UI", 11))
    style.map("Nav.TButton", background=[("active", COLORS["nav_active"])])
    style.configure("NavActive.TButton", background=COLORS["nav_active"], foreground="white",
                    padding=(14, 10), anchor="w", borderwidth=0, font=("Segoe UI", 11, "bold"))
    style.configure("Treeview", rowheight=26, background="white", fieldbackground="white")
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))


def guarded(action):
    """Run action(); show a friendly dialog for expected errors. Returns True on success."""
    try:
        action()
        return True
    except ValidationError as exc:
        messagebox.showwarning("Please check your input",
                               "\n".join(f"• {e}" for e in exc.errors))
    except AppError as exc:
        messagebox.showerror("Something went wrong", str(exc))
    return False


class DataTable(ttk.Frame):
    """Treeview with scrollbar. columns = [(key, heading, width)]."""

    def __init__(self, parent, columns, height=14):
        super().__init__(parent)
        self.keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.keys, show="headings",
                                 height=height, selectmode="browse")
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.tag_configure("bad", foreground=COLORS["bad"])
        self.tree.tag_configure("ok", foreground=COLORS["ok"])
        self.tree.tag_configure("muted", foreground=COLORS["muted"])

    def set_rows(self, rows):
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = ["" if row.get(k) is None else row.get(k) for k in self.keys]
            self.tree.insert("", "end", iid=str(row["id"]), values=values,
                             tags=(row.get("_tag", ""),))

    def selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def on_select(self, callback):
        self.tree.bind("<<TreeviewSelect>>", lambda _e: callback())

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())


class HouseholdPicker(ttk.Combobox):
    """Combobox showing household names while exposing their ids."""

    def __init__(self, parent, include_all=False, width=28, **kw):
        super().__init__(parent, state="readonly", width=width, **kw)
        self.include_all = include_all
        self._ids = {}

    def load(self, households):
        keep = self.get()
        self._ids = {h["name"]: h["id"] for h in households}
        names = list(self._ids)
        if self.include_all:
            names.insert(0, "All households")
        self["values"] = names
        if keep in names:
            self.set(keep)
        elif names:
            self.current(0)
        else:
            self.set("")

    def selected_id(self):
        return self._ids.get(self.get())

    def select_id(self, household_id):
        for name, hid in self._ids.items():
            if hid == household_id:
                self.set(name)
                return


def form_row(parent, row, label, widget):
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
    widget.grid(row=row, column=1, sticky="ew", pady=4)
    parent.columnconfigure(1, weight=1)
    return widget
