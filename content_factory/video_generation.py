"""Video provider interfaces for the local video production pipeline."""

import base64
import json
import mimetypes
import os
import time
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


class VideoProvider:
    def create_video(self, prompt, reference_image_path=None, aspect_ratio=None, duration=None):
        raise NotImplementedError

    def get_status(self, task_id):
        raise NotImplementedError

    def download(self, task_id, destination_path, status_payload=None):
        raise NotImplementedError


class VideoProviderError(RuntimeError):
    pass


class FakeVideoProvider(VideoProvider):
    """Deterministic provider used by tests and local workflow validation."""

    def __init__(self, task_id="fake-video-task-001", fail=False):
        self.task_id = task_id
        self.fail = fail
        self.calls = {"create_video": 0, "get_status": 0, "download": 0}

    def create_video(self, prompt, reference_image_path=None, aspect_ratio=None, duration=None):
        self.calls["create_video"] += 1
        if self.fail:
            return {"task_id": self.task_id, "status": "FAILED", "error_message": "Fake video generation failed"}
        return {"task_id": self.task_id, "status": "GENERATING_VIDEO"}

    def get_status(self, task_id):
        self.calls["get_status"] += 1
        if self.fail:
            return {"task_id": task_id, "status": "FAILED", "error_message": "Fake video task failed"}
        return {"task_id": task_id, "status": "COMPLETED"}

    def wait_for_completion(self, task_id):
        return self.get_status(task_id)

    def download(self, task_id, destination_path, status_payload=None):
        self.calls["download"] += 1
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "w", encoding="utf-8") as handle:
            handle.write(f"fake video placeholder for {task_id}\n")
        return {"task_id": task_id, "path": destination_path}


class RunwayVideoProvider(VideoProvider):
    """Runway image-to-video provider.

    Tests inject a fake http_client. The default client uses Python stdlib HTTP
    and is only used when VIDEO_PRODUCTION_PROVIDER=real is explicitly enabled.
    """

    def __init__(
        self,
        api_key=None,
        model=None,
        timeout_seconds=None,
        poll_interval_seconds=None,
        max_poll_seconds=None,
        http_client=None,
        sleep_func=None,
        base_url="https://api.dev.runwayml.com/v1",
    ):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY")
        if not self.api_key:
            raise VideoProviderError("RUNWAY_API_KEY is required when VIDEO_PRODUCTION_PROVIDER=real.")
        self.model = model or os.environ.get("RUNWAY_MODEL") or "gen4_turbo"
        self.timeout_seconds = int(_configured_value(timeout_seconds, "RUNWAY_TIMEOUT_SECONDS", 60))
        self.poll_interval_seconds = float(_configured_value(poll_interval_seconds, "RUNWAY_POLL_INTERVAL_SECONDS", 5))
        self.max_poll_seconds = float(_configured_value(max_poll_seconds, "RUNWAY_MAX_POLL_SECONDS", 300))
        self.http_client = http_client or _StdlibHttpClient()
        self.sleep_func = sleep_func or time.sleep
        self.base_url = base_url.rstrip("/")

    def create_video(self, prompt, reference_image_path=None, aspect_ratio="9:16", duration=5):
        if not reference_image_path:
            raise VideoProviderError("A verified reference image is required for real video generation.")
        payload = {
            "model": self.model,
            "promptText": prompt or "",
            "promptImage": _image_to_data_uri(reference_image_path),
            "ratio": _runway_ratio(aspect_ratio or "9:16"),
            "duration": int(duration or 5),
        }
        data = self.http_client.post_json(
            f"{self.base_url}/image_to_video",
            payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        task_id = data.get("id") or data.get("task_id")
        if not task_id:
            raise VideoProviderError("Runway did not return a task id.")
        return {"task_id": task_id, "status": data.get("status") or "GENERATING_VIDEO", "raw": data}

    def get_status(self, task_id):
        data = self.http_client.get_json(
            f"{self.base_url}/tasks/{task_id}",
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        status = _normalize_runway_status(data.get("status"))
        if status == "FAILED":
            return {"task_id": task_id, "status": "FAILED", "error_message": data.get("failure") or data.get("error") or "Runway generation failed.", "raw": data}
        return {"task_id": task_id, "status": status, "output": data.get("output"), "raw": data}

    def wait_for_completion(self, task_id):
        started_at = time.monotonic()
        while True:
            status = self.get_status(task_id)
            if status.get("status") in {"COMPLETED", "FAILED"}:
                return status
            if time.monotonic() - started_at >= self.max_poll_seconds:
                raise VideoProviderError("Runway generation timed out.")
            self.sleep_func(self.poll_interval_seconds)

    def download(self, task_id, destination_path, status_payload=None):
        status_payload = status_payload or self.get_status(task_id)
        output = status_payload.get("output") or status_payload.get("raw", {}).get("output")
        video_url = _first_output_url(output)
        if not video_url:
            raise VideoProviderError("Runway completed but did not provide a downloadable video URL.")
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        self.http_client.download_file(video_url, destination_path, headers={}, timeout=self.timeout_seconds)
        return {"task_id": task_id, "path": destination_path}

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }


class _StdlibHttpClient:
    def post_json(self, url, payload, headers=None, timeout=60):
        return self._json_request("POST", url, payload, headers or {}, timeout)

    def get_json(self, url, headers=None, timeout=60):
        return self._json_request("GET", url, None, headers or {}, timeout)

    def download_file(self, url, destination_path, headers=None, timeout=60):
        request = urllib_request.Request(url, headers=headers or {})
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                with open(destination_path, "wb") as handle:
                    handle.write(response.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            raise VideoProviderError(f"Runway download failed: {_safe_error(exc)}") from exc

    def _json_request(self, method, url, payload, headers, timeout):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib_request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise VideoProviderError(f"Runway API request failed: {_safe_error(exc)}") from exc
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise VideoProviderError("Runway returned non-JSON response.") from exc


def _image_to_data_uri(path):
    mime_type = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_runway_status(status):
    value = str(status or "").upper()
    if value in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
        return "COMPLETED"
    if value in {"FAILED", "CANCELLED", "CANCELED"}:
        return "FAILED"
    return "GENERATING_VIDEO"


def _runway_ratio(aspect_ratio):
    value = str(aspect_ratio or "").strip()
    if value == "9:16":
        return "768:1280"
    if value == "16:9":
        return "1280:768"
    return value or "768:1280"


def _first_output_url(output):
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("uri")
    if isinstance(output, dict):
        return output.get("url") or output.get("video_url") or output.get("uri")
    return None


def _safe_error(exc):
    message = str(exc)
    return message.replace(os.environ.get("RUNWAY_API_KEY", ""), "[redacted]") if os.environ.get("RUNWAY_API_KEY") else message


def _configured_value(value, env_name, default):
    if value is not None:
        return value
    return os.environ.get(env_name) or default
