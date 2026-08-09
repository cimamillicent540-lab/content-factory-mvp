import tempfile
import unittest
from pathlib import Path

from content_factory.video_generation import FakeVideoProvider, VideoProvider


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


if __name__ == "__main__":
    unittest.main()
