"""Lifecycle helpers for local video production jobs."""

from datetime import datetime
import json
import os
from uuid import uuid4

from content_factory.db import loads_json
from content_factory.ffmpeg_composer import compose_video, write_subtitles
from content_factory.video_generation import FakeVideoProvider, RunwayVideoProvider
from content_factory.voice_generation import ElevenLabsVoiceProvider


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


def update_video_job_request(conn, job_id, request_data):
    conn.execute(
        "UPDATE video_generation_jobs SET request_json = ?, reference_image_path = ?, updated_at = ? WHERE job_id = ?",
        (
            json.dumps(request_data or {}, ensure_ascii=False),
            (request_data or {}).get("reference_image_path"),
            _now(),
            job_id,
        ),
    )
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


def run_real_video_job(
    conn,
    generation_id,
    creative_id,
    request_data=None,
    output_root="outputs/video_jobs",
    video_provider=None,
    voice_provider=None,
    composer=compose_video,
    existing_job_id=None,
):
    request_data = request_data or {}
    if existing_job_id:
        job = get_video_job(conn, existing_job_id)
        if job is None:
            raise ValueError("Video job not found")
    else:
        job = create_video_job(conn, generation_id, creative_id, request_data)
        if job.get("duplicate"):
            return job

    provider = video_provider or RunwayVideoProvider()
    voice = voice_provider or ElevenLabsVoiceProvider(voice_id=request_data.get("voice_id") or None)
    job_dir = os.path.join(output_root, job["job_id"])
    os.makedirs(job_dir, exist_ok=True)

    try:
        _require_reference_image(request_data)
        request_data["production_mode"] = "REAL"
        update_video_job_request(conn, job["job_id"], request_data)

        job = update_video_job_status(conn, job["job_id"], "GENERATING_VIDEO", reference_image_path=request_data.get("reference_image_path"))
        video_task = provider.create_video(
            request_data.get("runway_prompt") or request_data.get("prompt") or "",
            reference_image_path=request_data.get("reference_image_path"),
            aspect_ratio=request_data.get("aspect_ratio") or "9:16",
            duration=request_data.get("runway_duration") or 5,
        )
        task_id = video_task.get("task_id")
        if video_task.get("status") == "FAILED":
            return mark_video_job_failed(conn, job["job_id"], video_task.get("error_message", "Runway generation failed."))
        job = update_video_job_status(conn, job["job_id"], "GENERATING_VIDEO", runway_task_id=task_id)

        completed_status = provider.wait_for_completion(task_id)
        if completed_status.get("status") == "FAILED":
            return mark_video_job_failed(conn, job["job_id"], completed_status.get("error_message", "Runway generation failed."))

        video_path = os.path.join(job_dir, "runway.mp4")
        provider.download(task_id, video_path, status_payload=completed_status)

        job = update_video_job_status(conn, job["job_id"], "GENERATING_VOICE", video_path=video_path)
        audio_path = os.path.join(job_dir, "voiceover.mp3")
        voice.generate_voice(
            request_data.get("voiceover") or "",
            audio_path,
            voice_id=request_data.get("voice_id") or None,
            style_prompt=request_data.get("elevenlabs_prompt"),
        )

        duration = _duration_seconds(request_data)
        subtitle_path = os.path.join(job_dir, "subtitles.srt")
        write_subtitles(request_data.get("captions", []), subtitle_path, duration_seconds=duration)

        job = update_video_job_status(conn, job["job_id"], "COMPOSITING", audio_path=audio_path, subtitle_path=subtitle_path)
        final_mp4_path = os.path.join(job_dir, f"{creative_id}-V1.mp4")
        composer(
            video_path,
            audio_path,
            subtitle_path,
            final_mp4_path,
            cta=request_data.get("cta") or "Learn More",
            compliance_text=request_data.get("compliance_footer") or "Terms and Conditions Apply",
        )
        return update_video_job_status(conn, job["job_id"], "COMPLETED", final_mp4_path=final_mp4_path)
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


def _require_reference_image(request_data):
    path = request_data.get("reference_image_path")
    if not path or not os.path.isfile(path):
        raise ValueError("A verified reference image is required for real video generation.")


def _duration_seconds(request_data):
    try:
        return max(float(request_data.get("duration") or 15), 1.0)
    except (TypeError, ValueError):
        return 15.0
