"""Low-level file operations (CSV export/import, text reports) with friendly errors."""
import csv
from pathlib import Path

from hydrohome.errors import FileServiceError

REQUIRED_IMPORT_COLUMNS = {"reading_date", "meter_reading"}


def _wrap_os_error(exc, path):
    if isinstance(exc, PermissionError):
        return FileServiceError(f"Permission denied for '{path}'. Choose another location "
                                "or close the file if it is open in another program.")
    if isinstance(exc, FileNotFoundError):
        return FileServiceError(f"File or folder not found: '{path}'.")
    return FileServiceError(f"File error for '{path}': {exc}")


def export_csv(path, fields, headers, rows):
    """Write `rows` (list of dicts) to CSV using `fields` as keys and `headers` as titles."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(["" if row.get(f) is None else row.get(f) for f in fields])
    except OSError as exc:
        raise _wrap_os_error(exc, path) from exc
    return len(rows)


def read_readings_csv(path):
    """Return [(line_number, {column: value})]. Raises FileServiceError for bad files."""
    path = Path(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            columns = {(c or "").strip().lower() for c in (reader.fieldnames or [])}
            missing = REQUIRED_IMPORT_COLUMNS - columns
            if missing:
                raise FileServiceError("CSV is missing required column(s): "
                                       + ", ".join(sorted(missing)))
            rows = []
            for line, raw in enumerate(reader, start=2):
                rows.append((line, {(k or "").strip().lower(): (v or "").strip()
                                    for k, v in raw.items()}))
    except FileServiceError:
        raise
    except UnicodeDecodeError as exc:
        raise FileServiceError("The file is not a valid UTF-8 text/CSV file.") from exc
    except csv.Error as exc:
        raise FileServiceError(f"The CSV file is malformed: {exc}") from exc
    except OSError as exc:
        raise _wrap_os_error(exc, path) from exc
    if not rows:
        raise FileServiceError("The CSV file has no data rows.")
    return rows


def write_text(path, text):
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise _wrap_os_error(exc, path) from exc
