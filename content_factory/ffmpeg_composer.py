"""FFmpeg composition helpers for final MP4 production."""

import os
import subprocess


class FFmpegComposerError(RuntimeError):
    pass


def write_subtitles(captions, destination_path, duration_seconds=15.0):
    captions = _normalize_captions(captions)
    if not captions:
        captions = ["Learn more before you start."]
    duration_seconds = max(float(duration_seconds or 15.0), 1.0)
    segment = duration_seconds / len(captions)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    with open(destination_path, "w", encoding="utf-8") as handle:
        for index, caption in enumerate(captions, start=1):
            start = (index - 1) * segment
            end = duration_seconds if index == len(captions) else min(index * segment, duration_seconds)
            handle.write(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{caption}\n\n")
    return destination_path


def compose_video(
    runway_video_path,
    voiceover_path,
    subtitles_path,
    output_path,
    cta="Learn More",
    compliance_text="Terms and Conditions Apply",
    ffmpeg_path=None,
    runner=None,
):
    ffmpeg_path = ffmpeg_path or os.environ.get("FFMPEG_PATH") or "/opt/homebrew/bin/ffmpeg"
    runner = runner or subprocess.run
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    vf = _video_filter(subtitles_path, cta, compliance_text)
    command = [
        ffmpeg_path,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        runway_video_path,
        "-i",
        voiceover_path,
        "-vf",
        vf,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-shortest",
        output_path,
    ]
    result = runner(command, capture_output=True, text=True, check=False)
    if getattr(result, "returncode", 0) != 0:
        stderr = getattr(result, "stderr", "") or "FFmpeg composition failed."
        raise FFmpegComposerError(stderr)
    return {"path": output_path, "command": command}


def build_ffmpeg_command(runway_video_path, voiceover_path, subtitles_path, output_path, cta, compliance_text, ffmpeg_path="/opt/homebrew/bin/ffmpeg"):
    return [
        ffmpeg_path,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        runway_video_path,
        "-i",
        voiceover_path,
        "-vf",
        _video_filter(subtitles_path, cta, compliance_text),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-shortest",
        output_path,
    ]


def _video_filter(subtitles_path, cta, compliance_text):
    subtitle_path = _escape_filter_path(subtitles_path)
    return ",".join(
        [
            "scale=1080:1920:force_original_aspect_ratio=increase",
            "crop=1080:1920",
            f"subtitles='{subtitle_path}':force_style='FontSize=46,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=3,Shadow=1,MarginV=230'",
            f"drawtext=text='{_escape_drawtext(cta)}':x=(w-text_w)/2:y=h-360:fontsize=68:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=28:enable='gte(t,12)'",
            f"drawtext=text='{_escape_drawtext(compliance_text)}':x=(w-text_w)/2:y=h-82:fontsize=30:fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=16",
        ]
    )


def _normalize_captions(captions):
    if isinstance(captions, str):
        return [line.strip() for line in captions.splitlines() if line.strip()]
    if isinstance(captions, list):
        return [str(item).strip() for item in captions if str(item).strip()]
    return []


def _srt_time(seconds):
    milliseconds = int(round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _escape_drawtext(value):
    return str(value or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _escape_filter_path(path):
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
