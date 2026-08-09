"""Video provider interfaces for the local video production pipeline."""

import os


class VideoProvider:
    def create_video(self, prompt, reference_image_path=None):
        raise NotImplementedError

    def get_status(self, task_id):
        raise NotImplementedError

    def download(self, task_id, destination_path):
        raise NotImplementedError


class FakeVideoProvider(VideoProvider):
    """Deterministic provider used by tests and local workflow validation."""

    def __init__(self, task_id="fake-video-task-001", fail=False):
        self.task_id = task_id
        self.fail = fail
        self.calls = {"create_video": 0, "get_status": 0, "download": 0}

    def create_video(self, prompt, reference_image_path=None):
        self.calls["create_video"] += 1
        if self.fail:
            return {"task_id": self.task_id, "status": "FAILED", "error_message": "Fake video generation failed"}
        return {"task_id": self.task_id, "status": "GENERATING_VIDEO"}

    def get_status(self, task_id):
        self.calls["get_status"] += 1
        if self.fail:
            return {"task_id": task_id, "status": "FAILED", "error_message": "Fake video task failed"}
        return {"task_id": task_id, "status": "COMPLETED"}

    def download(self, task_id, destination_path):
        self.calls["download"] += 1
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "w", encoding="utf-8") as handle:
            handle.write(f"fake video placeholder for {task_id}\n")
        return {"task_id": task_id, "path": destination_path}
