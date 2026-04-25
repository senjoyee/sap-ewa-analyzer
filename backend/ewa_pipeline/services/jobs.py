from __future__ import annotations

import json
import queue
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ewa_pipeline.config import Config, load_config
from .pipeline import PipelineArtifacts, run_pipeline
from .progress import ProgressEvent


def _serialize_event(event: ProgressEvent) -> dict[str, Any]:
    return event.to_dict()


@dataclass
class JobRecord:
    job_id: str
    base_dir: Path
    input_name: str
    input_type: str
    status: str = "queued"
    created_at: str = ""
    updated_at: str = ""
    stages: list[dict[str, Any]] = field(default_factory=list)
    output_file: str | None = None
    result_file: str | None = None
    cost_file: str | None = None
    tree_file: str | None = None
    error: str | None = None

    @property
    def metadata_path(self) -> Path:
        return self.base_dir / "job.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input_name": self.input_name,
            "input_type": self.input_type,
            "stages": self.stages,
            "output_file": self.output_file,
            "result_file": self.result_file,
            "cost_file": self.cost_file,
            "tree_file": self.tree_file,
            "error": self.error,
            "download_url": f"/api/jobs/{self.job_id}/download" if self.output_file else None,
        }

    def save(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


class JobManager:
    def __init__(self, root_dir: Path, config_path: Path = Path("config.yaml")):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = Path(config_path)
        self._jobs: dict[str, JobRecord] = {}
        self._streams: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
        self._lock = threading.Lock()
        self._load_existing_jobs()

    def create_job(self, uploaded_file: Path) -> JobRecord:
        job_id = uuid.uuid4().hex[:12]
        input_type = uploaded_file.suffix.lower().lstrip(".")
        base_dir = self.root_dir / job_id
        input_dir = base_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        stored_input = input_dir / uploaded_file.name
        shutil.copy2(uploaded_file, stored_input)

        record = JobRecord(
            job_id=job_id,
            base_dir=base_dir,
            input_name=uploaded_file.name,
            input_type=input_type,
        )
        self._touch(record, status="queued")
        with self._lock:
            self._jobs[job_id] = record
        return record

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id]

    def stream(self, job_id: str) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._lock:
            self._streams.setdefault(job_id, []).append(q)
            job = self._jobs.get(job_id)
            if job:
                q.put({"type": "snapshot", "job": job.to_dict()})
        return q

    def remove_stream(self, job_id: str, q: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            streams = self._streams.get(job_id, [])
            if q in streams:
                streams.remove(q)

    def start_job(self, job_id: str) -> None:
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        thread.start()

    def _run_job(self, job_id: str) -> None:
        try:
            load_dotenv()
            config = load_config(self.config_path)
            record = self.get_job(job_id)
            input_dir = record.base_dir / "input"
            input_path = next(input_dir.iterdir())
            output_path = record.base_dir / "report.xlsx"

            self._touch(record, status="running")

            def _on_progress(event: ProgressEvent) -> None:
                payload = _serialize_event(event)
                self._append_stage(record, payload)

            _, _, artifacts = run_pipeline(
                config=config,
                output_path=output_path,
                pdf_path=input_path if record.input_type == "pdf" else None,
                zip_path=input_path if record.input_type == "zip" else None,
                skills_dir=Path("skills"),
                progress_callback=_on_progress,
            )
            self._complete(record, artifacts)
        except Exception as exc:  # pragma: no cover - failure path exercised manually
            record = self.get_job(job_id)
            self._touch(record, status="failed", error=str(exc))
            self._publish(job_id, {"type": "job", "job": record.to_dict()})

    def _complete(self, record: JobRecord, artifacts: PipelineArtifacts) -> None:
        record.output_file = artifacts.output_path.name
        record.result_file = artifacts.result_path.name
        record.cost_file = artifacts.cost_path.name
        record.tree_file = artifacts.tree_path.name
        self._touch(record, status="completed")
        self._publish(record.job_id, {"type": "job", "job": record.to_dict()})

    def _append_stage(self, record: JobRecord, payload: dict[str, Any]) -> None:
        replaced = False
        for index, stage in enumerate(record.stages):
            if stage["stage"] == payload["stage"]:
                record.stages[index] = payload
                replaced = True
                break
        if not replaced:
            record.stages.append(payload)
        self._touch(record, status=record.status)
        self._publish(record.job_id, {"type": "event", "event": payload, "job": record.to_dict()})

    def _touch(self, record: JobRecord, *, status: str, error: str | None = None) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        if not record.created_at:
            record.created_at = now
        record.updated_at = now
        record.status = status
        if error is not None:
            record.error = error
        record.save()

    def _publish(self, job_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            for stream in self._streams.get(job_id, []):
                stream.put(payload)

    def _load_existing_jobs(self) -> None:
        for metadata in self.root_dir.glob("*/job.json"):
            data = json.loads(metadata.read_text(encoding="utf-8"))
            job_id = data["job_id"]
            record = JobRecord(
                job_id=job_id,
                base_dir=metadata.parent,
                input_name=data.get("input_name", ""),
                input_type=data.get("input_type", ""),
                status=data.get("status", "queued"),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                stages=data.get("stages", []),
                output_file=data.get("output_file"),
                result_file=data.get("result_file"),
                cost_file=data.get("cost_file"),
                tree_file=data.get("tree_file"),
                error=data.get("error"),
            )
            self._jobs[job_id] = record
