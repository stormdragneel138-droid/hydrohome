# Web dashboard + API: beginner setup (Windows / VS Code)

## 1. Open the project
1. Open **VS Code** → **File → Open Folder…** → choose the folder that contains `run_api.py`
   (the inner `hydrohome` folder of your project).
2. Open the terminal: **Terminal → New Terminal**. It should start inside that folder.

## 2. Activate your virtual environment and install the new packages
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```
If PowerShell refuses to run `activate`, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 3. Check everything works (optional but recommended)
```powershell
python -m pytest
```
You should see all tests pass (your original tests plus the new API tests).

## 4. Start the app
```powershell
python run_api.py
```
Leave this terminal open: it *is* the server. Open **http://127.0.0.1:8000** in your browser.

* **First time:** click **Create an account**. The first account automatically becomes the owner of any
  households you already made in the desktop app.
* **Want sample data to explore first?** Stop the server (`Ctrl + C`) and run:
  ```powershell
  python scripts/seed_demo_data.py
  python run_api.py --db data/demo.db
  ```
  Sign in with `demo@hydrohome.local` / `demo-pass-123`. This uses a separate file, so your real data is untouched.

## 5. Try the API
Open **http://127.0.0.1:8000/docs**: click **Authorize**, paste the token from `/api/auth/login`, then
open any endpoint, press **Try it out** and **Execute**.

## 6. Daily use
| I want to… | Do this |
|---|---|
| Start the web dashboard | `python run_api.py` |
| Start the desktop app | `python main.py` (can run at the same time) |
| Stop the server | Click the terminal and press `Ctrl + C` |
| Use another port | `python run_api.py --port 8080` |
| Rebuild the API docs | `python scripts/generate_api_docs.py` |

## Troubleshooting
* **`ModuleNotFoundError: fastapi`**: the virtual environment is not active or step 2 was skipped.
* **`address already in use`**: another copy is running. Close it or use `--port 8080`.
* **Page says "Server not reachable"**: the terminal running `run_api.py` was closed.
* **Forgot your password**: create another account (or reset by deleting the `users` row in the database).
