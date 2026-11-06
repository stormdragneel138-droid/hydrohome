"""HydroHome entry point:  python main.py"""
import sys
from tkinter import Tk, messagebox

from hydrohome.container import build_services
from hydrohome.errors import AppError


def main():
    try:
        services = build_services()
    except AppError as exc:
        root = Tk()
        root.withdraw()
        messagebox.showerror("HydroHome cannot start", str(exc))
        sys.exit(1)
    from hydrohome.ui.app import HydroHomeApp
    HydroHomeApp(services).mainloop()


if __name__ == "__main__":
    main()
