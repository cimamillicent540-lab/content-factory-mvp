"""Lifecycle helpers for local video production jobs."""

from datetime import datetime
import json
import os
from uuid import uuid4

from content_factory.db import loads_json
from content_factory.video_generation import FakeVideoProvider


ACTIVE_STATUSES = {"PENDING", "GENERATING_VIDEO", "GENERATING_VOICE", "COMPOSITING", "COMPLETED"}
VALID_STATUSES = ACTIVE_STATUSES | {"FAILED"}


def create_video_job(conn, generation_id, creative_id, request_data=None):
    existing = find_existing_video_job(conn, generation_id, creative_id)
    if existing is not None:
        item = dict(existing)
        item["request"] = loads_json(item.get("request_json"), {})
        item["duplicate"] = True
        return item

    job_id = _new_job_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO video_generation_jobs (
            job_id, generation_id, creative_id, status, reference_image_path, request_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            generation_id,
            creative_id,
            "PENDING",
            (request_data or {}).get("reference_image_path"),
            json.dumps(request_data or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    item = get_video_job(conn, job_id)
    item["duplicate"] = False
    return item


def get_video_job(conn, job_id):
    row = conn.execute("SELECT * FROM video_generation_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["request"] = loads_json(item.get("request_json"), {})
    return item


def list_video_jobs(conn, limit=50):
    rows = conn.execute(
        "SELECT * FROM video_generation_jobs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [get_video_job(conn, row["job_id"]) for row in rows]


def update_video_job_status(conn, job_id, status, **fields):
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported video job status: {status}")
    allowed_fields = {
        "reference_image_path",
        "runway_task_id",
        "audio_path",
        "video_path",
        "subtitle_path",
        "final_mp4_path",
        "error_message",
    }
    updates = {"status": status, "updated_at": _now()}
    for key, value in fields.items():
        if key in allowed_fields:
            updates[key] = value
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [job_id]
    conn.execute(f"UPDATE video_generation_jobs SET {assignments} WHERE job_id = ?", values)
    conn.commit()
    return get_video_job(conn, job_id)


def find_existing_video_job(conn, generation_id, creative_id):
    row = conn.execute(
        """
        SELECT * FROM video_generation_jobs
        WHERE generation_id = ? AND creative_id = ? AND status IN (?, ?, ?, ?, ?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (generation_id, creative_id, "PENDING", "GENERATING_VIDEO", "GENERATING_VOICE", "COMPOSITING", "COMPLETED"),
    ).fetchone()
    if row is None:
        return None
    return get_video_job(conn, row["job_id"])


def mark_video_job_failed(conn, job_id, error_message):
    return update_video_job_status(conn, job_id, "FAILED", error_message=error_message)


def run_fake_video_job(conn, generation_id, creative_id, request_data=None, output_root="outputs/video_jobs", video_provider=None):
    job = create_video_job(conn, generation_id, creative_id, request_data or {})
    if job.get("duplicate"):
        return job

    provider = video_provider or FakeVideoProvider()
    job_dir = os.path.join(output_root, job["job_id"])
    os.makedirs(job_dir, exist_ok=True)

    try:
        job = update_video_job_status(conn, job["job_id"], "GENERATING_VIDEO")
        video_task = provider.create_video(
            (request_data or {}).get("runway_prompt") or (request_data or {}).get("prompt") or "",
            reference_image_path=(request_data or {}).get("reference_image_path"),
        )
        if video_task.get("status") == "FAILED":
            return mark_video_job_failed(conn, job["job_id"], video_task.get("error_message", "Video generation failed"))
        job = update_video_job_status(conn, job["job_id"], "GENERATING_VIDEO", runway_task_id=video_task.get("task_id"))

        status = provider.get_status(video_task.get("task_id"))
        if status.get("status") == "FAILED":
            return mark_video_job_failed(conn, job["job_id"], status.get("error_message", "Video task failed"))

        video_path = os.path.join(job_dir, "runway.mp4")
        provider.download(video_task.get("task_id"), video_path)

        job = update_video_job_status(conn, job["job_id"], "GENERATING_VOICE", video_path=video_path)
        audio_path = os.path.join(job_dir, "voiceover.mp3")
        _write_placeholder(audio_path, "fake audio placeholder\n")

        job = update_video_job_status(conn, job["job_id"], "COMPOSITING", audio_path=audio_path)
        subtitle_path = os.path.join(job_dir, "subtitles.srt")
        _write_placeholder(subtitle_path, _subtitle_placeholder(request_data or {}))
        final_mp4_path = os.path.join(job_dir, f"{creative_id}-V1.mp4")
        _write_placeholder(final_mp4_path, "fake final mp4 placeholder\n")

        return update_video_job_status(
            conn,
            job["job_id"],
            "COMPLETED",
            subtitle_path=subtitle_path,
            final_mp4_path=final_mp4_path,
        )
    except Exception as exc:
        return mark_video_job_failed(conn, job["job_id"], str(exc))


def _new_job_id():
    return f"video-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _write_placeholder(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _subtitle_placeholder(request_data):
    captions = request_data.get("captions") or []
    if not captions:
        captions = [request_data.get("hook") or "Fake video production preview"]
    return "\n\n".join(f"{index}\n00:00:0{index-1},000 --> 00:00:0{index},000\n{caption}" for index, caption in enumerate(captions[:5], start=1))
