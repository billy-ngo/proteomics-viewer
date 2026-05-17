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
# Cache-busting headers so a pip install --upgrade actually serves the
# new frontend instead of whatever the user's browser cached from the
# previous version. Without no-cache, users would update proker and
# still see old behaviour (e.g. an unfixed bug they reported) until
# they hard-refreshed — and most users don't know to do that.
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(_templates_dir / "index.html"), headers=_NO_CACHE_HEADERS)


@app.get("/proker-charts.js", include_in_schema=False)
def serve_charts_js():
    return FileResponse(
        str(_templates_dir / "proker-charts.js"),
        media_type="application/javascript",
        headers=_NO_CACHE_HEADERS,
    )


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


# ── Auto-shutdown ────────────────────────────────────────────────
# Two complementary signals tell the server when the browser has gone away:
#
#   1. HEARTBEAT timeout — the frontend pings /api/heartbeat every 10 s. If
#      we don't see a heartbeat for ``_HEARTBEAT_TIMEOUT`` seconds, the
#      browser is presumed closed/crashed/asleep and the server exits. This
#      is the catch-all that fires regardless of HOW the browser went away.
#
#   2. EXPLICIT shutdown via /api/shutdown — the frontend's pagehide event
#      handler fires ``navigator.sendBeacon('/api/shutdown')`` when the user
#      closes the tab. The server then arms a SHORT (``_SHUTDOWN_GRACE_S``)
#      countdown that any new heartbeat cancels. So a normal close shuts
#      the server down in ~3 s, but a reload (which re-establishes the
#      heartbeat within ~500 ms) keeps it running.
#
# Initialising ``_last_heartbeat`` to ``time.time()`` at module load (rather
# than 0.0) means the watchdog will fire even when the user opened the
# browser, never uploaded a file (so the old code's heartbeat-after-init
# never ran), and walked away. The previous behaviour left the server
# running forever in that case.
_last_heartbeat = time.time()
_HEARTBEAT_TIMEOUT = 15        # Seconds without heartbeat = browser gone
_SHUTDOWN_GRACE_S = 3          # Seconds between explicit shutdown signal
                               # and exit (cancelled by heartbeat in window)
_shutdown_armed_at = 0.0       # 0.0 = no explicit shutdown pending


@app.get("/api/heartbeat")
def heartbeat():
    """Frontend pings this every 10 s while the page is open. Receiving
    one cancels any pending explicit shutdown — covers the reload case
    where the old page sent /api/shutdown but the new page came back fast
    enough to take over before the grace window expired."""
    global _last_heartbeat, _shutdown_armed_at
    _last_heartbeat = time.time()
    if _shutdown_armed_at:
        _shutdown_armed_at = 0.0  # Reload caught us — keep running
    return {"status": "ok"}


@app.post("/api/shutdown")
@app.get("/api/shutdown")
def request_shutdown():
    """Explicit "I'm closing the tab" signal from the frontend's pagehide
    handler. Arms a short grace window during which any heartbeat will
    cancel the shutdown — so a reload (new heartbeat fires within ~500 ms)
    keeps the server alive while a real close (no new heartbeat) lets it
    die in ~3 s instead of waiting the full 15 s heartbeat timeout.

    Both POST and GET accepted because navigator.sendBeacon emits POST
    but a manual debug fetch defaults to GET — easier to test from a
    browser address bar."""
    global _shutdown_armed_at
    _shutdown_armed_at = time.time()
    return {"status": "shutdown_armed", "grace_seconds": _SHUTDOWN_GRACE_S}


def _shutdown_cleanup():
    """Tear down state shared with the CLI launcher (the server.lock file
    that prevents duplicate proker processes from binding the same port).
    Called from both shutdown paths so a stale lock never blocks the next
    invocation."""
    lock_file = Path.home() / ".proker" / "server.lock"
    try:
        lock_file.unlink(missing_ok=True)
    except Exception:
        pass


def _auto_shutdown_watchdog():
    """Background thread checking heartbeat freshness AND the explicit-
    shutdown grace window. Exits the process via os._exit() when either
    condition fires — uvicorn's own shutdown plumbing is too slow for the
    "browser closed" use case (it tries to drain pending requests, which
    nothing remains to drain since the client is gone)."""
    while True:
        time.sleep(2)  # Check every 2 s so the explicit-shutdown grace
                       # window resolves with ~2 s precision.
        now = time.time()
        # Path 1: explicit shutdown was requested. Wait the grace window
        # for a heartbeat to come in (which would zero `_shutdown_armed_at`).
        if _shutdown_armed_at and (now - _shutdown_armed_at) >= _SHUTDOWN_GRACE_S:
            _shutdown_cleanup()
            os._exit(0)
        # Path 2: silent timeout. No heartbeat in the window = browser gone.
        if (now - _last_heartbeat) > _HEARTBEAT_TIMEOUT:
            _shutdown_cleanup()
            os._exit(0)


if os.environ.get("PROTVIEW_AUTO_SHUTDOWN") == "1":
    threading.Thread(target=_auto_shutdown_watchdog, daemon=True).start()
