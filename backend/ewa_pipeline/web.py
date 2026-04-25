from __future__ import annotations

import json
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ewa_pipeline.services.jobs import JobManager

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
UPLOAD_TMP = BASE_DIR / "output" / "uploads"
JOBS_DIR = BASE_DIR / "output" / "jobs"

UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

job_manager = JobManager(root_dir=JOBS_DIR)

app = FastAPI(title="EWA Analyzer Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".zip"}:
        raise HTTPException(status_code=400, detail="Only .pdf and .zip files are supported.")

    upload_path = UPLOAD_TMP / f"{uuid.uuid4().hex[:12]}_{Path(file.filename).name}"
    upload_path.write_bytes(await file.read())
    record = job_manager.create_job(upload_path)
    job_manager.start_job(record.job_id)
    return record.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return job_manager.get_job(job_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/jobs/{job_id}/events")
def stream_job(job_id: str):
    try:
        job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    def event_stream():
        q = job_manager.stream(job_id)
        try:
            while True:
                try:
                    payload = q.get(timeout=15)
                    yield f"data: {json.dumps(payload)}\n\n"
                except Exception:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"
        finally:
            job_manager.remove_stream(job_id, q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
def download_job_output(job_id: str):
    try:
        job = job_manager.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc

    if not job.output_file:
        raise HTTPException(status_code=409, detail="Report not ready yet")

    report_path = job.base_dir / job.output_file
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file missing")
    return FileResponse(report_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=report_path.name)


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Frontend build not found")
