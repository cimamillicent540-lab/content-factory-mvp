import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_factory.video_generation import FakeVideoProvider, RunwayVideoProvider, VideoProvider, VideoProviderError


class VideoGenerationTests(unittest.TestCase):
    def test_video_provider_interface_is_abstract(self):
        provider = VideoProvider()

        with self.assertRaises(NotImplementedError):
            provider.create_video("prompt")
        with self.assertRaises(NotImplementedError):
            provider.get_status("task-1")
        with self.assertRaises(NotImplementedError):
            provider.download("task-1", "/tmp/fake.mp4")

    def test_fake_video_provider_creates_task_without_network(self):
        provider = FakeVideoProvider(task_id="fake-video-task-001")

        result = provider.create_video("Generate a vertical ad", reference_image_path=None)

        self.assertEqual(result["task_id"], "fake-video-task-001")
        self.assertEqual(result["status"], "GENERATING_VIDEO")
        self.assertEqual(provider.calls["create_video"], 1)

    def test_fake_video_provider_status_and_download(self):
        provider = FakeVideoProvider(task_id="fake-video-task-001")
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "fake.mp4"

            status = provider.get_status("fake-video-task-001")
            downloaded = provider.download("fake-video-task-001", str(destination))

            self.assertEqual(status["status"], "COMPLETED")
            self.assertEqual(downloaded["path"], str(destination))
            self.assertTrue(destination.exists())
            self.assertIn("fake video placeholder", destination.read_text())

    def test_runway_provider_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(VideoProviderError, "RUNWAY_API_KEY"):
                RunwayVideoProvider()

    def test_runway_provider_create_video_success_and_saves_task_id(self):
        client = FakeRunwayClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            image = self._png(tmpdir)
            provider = RunwayVideoProvider(api_key="test-key", http_client=client, sleep_func=lambda _seconds: None)

            result = provider.create_video("A product walkthrough", reference_image_path=str(image), aspect_ratio="9:16", duration=5)

        self.assertEqual(result["task_id"], "task-123")
        self.assertEqual(client.posted_payload["ratio"], "768:1280")
        self.assertIn("data:image/png;base64,", client.posted_payload["promptImage"])
        self.assertNotIn("test-key", str(client.posted_payload))

    def test_runway_provider_polling_completed_and_download_success(self):
        client = FakeRunwayClient(statuses=[{"id": "task-123", "status": "RUNNING"}, {"id": "task-123", "status": "SUCCEEDED", "output": ["https://cdn.example/video.mp4"]}])
        provider = RunwayVideoProvider(api_key="test-key", http_client=client, sleep_func=lambda _seconds: None, max_poll_seconds=30)

        with tempfile.TemporaryDirectory() as tmpdir:
            status = provider.wait_for_completion("task-123")
            path = Path(tmpdir) / "runway.mp4"
            downloaded = provider.download("task-123", str(path), status_payload=status)

            self.assertEqual(status["status"], "COMPLETED")
            self.assertEqual(downloaded["path"], str(path))
            self.assertEqual(path.read_bytes(), b"video-bytes")

    def test_runway_provider_polling_timeout(self):
        client = FakeRunwayClient(statuses=[{"id": "task-123", "status": "RUNNING"}])
        provider = RunwayVideoProvider(api_key="test-key", http_client=client, sleep_func=lambda _seconds: None, max_poll_seconds=0)

        with self.assertRaisesRegex(VideoProviderError, "timed out"):
            provider.wait_for_completion("task-123")

    def test_runway_provider_failure(self):
        client = FakeRunwayClient(statuses=[{"id": "task-123", "status": "FAILED", "failure": "Runway rejected prompt"}])
        provider = RunwayVideoProvider(api_key="test-key", http_client=client)

        status = provider.get_status("task-123")

        self.assertEqual(status["status"], "FAILED")
        self.assertEqual(status["error_message"], "Runway rejected prompt")

    def _png(self, tmpdir):
        path = Path(tmpdir) / "reference.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return path


class FakeRunwayClient:
    def __init__(self, statuses=None):
        self.statuses = list(statuses or [{"id": "task-123", "status": "SUCCEEDED", "output": ["https://cdn.example/video.mp4"]}])
        self.posted_payload = None

    def post_json(self, _url, payload, headers=None, timeout=60):
        self.posted_payload = payload
        self.headers = headers or {}
        return {"id": "task-123", "status": "PENDING"}

    def get_json(self, _url, headers=None, timeout=60):
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def download_file(self, _url, destination_path, headers=None, timeout=60):
        Path(destination_path).write_bytes(b"video-bytes")


if __name__ == "__main__":
    unittest.main()
