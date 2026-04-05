"""
ProteomicsViewer — FastAPI application entry point.

Serves the REST API for data upload/retrieval and the single-page frontend.
Auto-shutdown when browser tabs close (heartbeat-based, CLI mode only).
"""

import os
import time
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from proteomicsviewer.server.state import state
from proteomicsviewer.server.parser import parse_protein_groups

app = FastAPI(title="ProteomicsViewer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_templates_dir = Path(__file__).parent / "templates"


# ── Frontend serving ──────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(_templates_dir / "index.html"))


# ── API routes ────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse a proteinGroups.txt file."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    suffix = Path(file.filename).suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        data = parse_protein_groups(tmp_path)
        data["filename"] = file.filename
        state.data = data
        state.filename = file.filename
        return data
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.get("/api/data")
def get_data():
    """Return currently loaded data."""
    if not state.data:
        return JSONResponse({"error": "No data loaded"}, status_code=404)
    return state.data


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Auto-load from CLI argument ──────────────────────────────────
@app.on_event("startup")
async def _autoload():
    filepath = os.environ.get("PROTVIEW_AUTOLOAD")
    if filepath and Path(filepath).exists():
        try:
            data = parse_protein_groups(filepath)
            data["filename"] = Path(filepath).name
            state.data = data
            state.filename = Path(filepath).name
        except Exception:
            pass  # Silently skip — user can upload manually


# ── Auto-shutdown heartbeat ──────────────────────────────────────
_last_heartbeat = 0.0
_HEARTBEAT_TIMEOUT = 30


@app.get("/api/heartbeat")
def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return {"status": "ok"}


def _auto_shutdown_watchdog():
    global _last_heartbeat
    while True:
        time.sleep(10)
        if _last_heartbeat > 0 and (time.time() - _last_heartbeat) > _HEARTBEAT_TIMEOUT:
            lock_file = Path.home() / ".proteomicsviewer" / "server.lock"
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass
            os._exit(0)


if os.environ.get("PROTVIEW_AUTO_SHUTDOWN") == "1":
    threading.Thread(target=_auto_shutdown_watchdog, daemon=True).start()
