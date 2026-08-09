"""Safe local file helpers for video production assets."""

import os
from pathlib import Path


MAX_REFERENCE_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class FileValidationError(ValueError):
    pass


def save_reference_image(upload, job_id, output_root):
    if not upload:
        raise FileValidationError("A verified reference image is required for real video generation.")

    filename = str(upload.get("filename") or "")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise FileValidationError("Reference image filename is not safe.")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise FileValidationError("Reference Image must be PNG, JPG, JPEG, or WEBP.")

    content = upload.get("content")
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not isinstance(content, (bytes, bytearray)):
        raise FileValidationError("Reference Image upload is empty.")
    if len(content) > MAX_REFERENCE_IMAGE_BYTES:
        raise FileValidationError("Reference Image must be 10MB or smaller.")
    if not _has_valid_image_signature(bytes(content), extension):
        raise FileValidationError("Reference Image file signature is invalid.")

    job_dir = safe_job_dir(output_root, job_id)
    os.makedirs(job_dir, exist_ok=True)
    path = os.path.join(job_dir, f"reference{extension}")
    with open(path, "wb") as handle:
        handle.write(content)
    return path


def safe_job_dir(output_root, job_id):
    root = os.path.abspath(output_root)
    job_id = str(job_id)
    if not job_id.startswith("video-") or "/" in job_id or "\\" in job_id or ".." in job_id:
        raise FileValidationError("Video job id is not safe.")
    path = os.path.abspath(os.path.join(root, job_id))
    if not _is_within(path, root):
        raise FileValidationError("Video job path is not safe.")
    return path


def safe_job_file(job, field_name, output_root):
    path = job.get(field_name)
    if not path:
        raise FileValidationError("Requested video asset is not available.")
    job_dir = safe_job_dir(output_root, job.get("job_id"))
    abs_path = os.path.abspath(path)
    if not _is_within(abs_path, job_dir):
        raise FileValidationError("Requested video asset is outside this job directory.")
    if not os.path.isfile(abs_path):
        raise FileValidationError("Requested video asset file does not exist.")
    return abs_path


def _is_within(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _has_valid_image_signature(content, extension):
    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension == ".webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False
