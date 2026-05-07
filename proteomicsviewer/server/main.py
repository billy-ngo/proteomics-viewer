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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from proteomicsviewer.server.state import state
from proteomicsviewer.server.parser import parse_protein_groups, parse_transcriptomics

app = FastAPI(title="Pro-ker Proteomics Viewer API", version="2.0.0")

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


@app.get("/proker-charts.js", include_in_schema=False)
def serve_charts_js():
    return FileResponse(str(_templates_dir / "proker-charts.js"), media_type="application/javascript")


# ── API routes ────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), mode: str = Form("proteomics")):
    """Upload and parse a data file.

    ``mode`` controls which parser is used:
      - ``proteomics`` (default): MaxQuant proteinGroups.txt or variant.
      - ``transcriptomics``: tab-delimited RNA-seq output with a Locustag/
        Gene/Description/FeatureType header convention plus per-sample count
        columns. The values are taken as already-normalised — the frontend's
        normalisation step is bypassed for these uploads.
    """
    if not file.filename:
        raise HTTPException(400, "No file provided")

    suffix = Path(file.filename).suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if mode == "transcriptomics":
            data = parse_transcriptomics(tmp_path)
        else:
            data = parse_protein_groups(tmp_path)
        data["filename"] = file.filename
        # Tag every protein and sample with the source filename so the frontend
        # can detect multi-file mixing and reject incompatible comparisons.
        for p in data.get("proteins", []):
            p["source_file"] = file.filename
        data["sample_source"] = {s: file.filename for s in data.get("samples", [])}
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
    """Return currently loaded data (without bulky raw_rows)."""
    if not state.data:
        return JSONResponse({"error": "No data loaded"}, status_code=404)
    # Strip raw_rows to keep this endpoint fast — only /api/upload returns them.
    out = {k: v for k, v in state.data.items() if k not in ("raw_rows", "raw_headers")}
    return out


@app.get("/health")
def health():
    from proteomicsviewer import __version__
    return {"status": "ok", "version": __version__}


# ── Auto-load from CLI argument ──────────────────────────────────
@app.on_event("startup")
async def _autoload():
    filepath = os.environ.get("PROTVIEW_AUTOLOAD")
    if filepath and Path(filepath).exists():
        try:
            data = parse_protein_groups(filepath)
            fname = Path(filepath).name
            data["filename"] = fname
            for p in data.get("proteins", []):
                p["source_file"] = fname
            data["sample_source"] = {s: fname for s in data.get("samples", [])}
            state.data = data
            state.filename = fname
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
            lock_file = Path.home() / ".proker" / "server.lock"
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass
            os._exit(0)


if os.environ.get("PROTVIEW_AUTO_SHUTDOWN") == "1":
    threading.Thread(target=_auto_shutdown_watchdog, daemon=True).start()
