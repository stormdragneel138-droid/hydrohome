"""Start the web dashboard + REST API:   python run_api.py

Then open http://127.0.0.1:8000  (interactive API docs: http://127.0.0.1:8000/docs).
The Tkinter desktop app (python main.py) keeps working and shares the same database.

Options:
    python run_api.py --db data/demo.db     use a different database file (e.g. the demo data)
    python run_api.py --port 8080           use another port
"""
import argparse
import os

import uvicorn

from hydrohome.api.app import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HydroHome web dashboard + REST API")
    parser.add_argument("--db", default=None, help="SQLite file (default: data/hydrohome.db)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()
    uvicorn.run(create_app(args.db), host=args.host, port=args.port)
