import os
import tempfile
import unittest

from content_factory.db import connect, init_db
from content_factory.video_generation import FakeVideoProvider
from content_factory.video_jobs import (
    create_video_job,
    find_existing_video_job,
    get_video_job,
    list_video_jobs,
    mark_video_job_failed,
    run_fake_video_job,
    run_real_video_job,
    update_video_job_status,
)
from content_factory.voice_generation import FakeVoiceProvider


class VideoJobTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.output_dir = os.path.join(self.tmpdir.name, "video_jobs")

    def test_create_video_job_saves_fields_and_unique_job_id(self):
        first = create_video_job(self.conn, 1, "SPK-BR-FB-20260808-C001", {"cta": "Start"})
        second = create_video_job(self.conn, 1, "SPK-BR-FB-20260808-C002", {"cta": "Learn"})

        self.assertNotEqual(first["job_id"], second["job_id"])
        self.assertEqual(first["status"], "PENDING")
        self.assertEqual(first["generation_id"], 1)
        self.assertEqual(first["creative_id"], "SPK-BR-FB-20260808-C001")
        self.assertEqual(first["request"]["cta"], "Start")

    def test_get_list_and_update_video_job(self):
        created = create_video_job(self.conn, 1, "C001")

        update_video_job_status(self.conn, created["job_id"], "GENERATING_VIDEO", runway_task_id="task-1")
        fetched = get_video_job(self.conn, created["job_id"])
        jobs = list_video_jobs(self.conn)

        self.assertEqual(fetched["status"], "GENERATING_VIDEO")
        self.assertEqual(fetched["runway_task_id"], "task-1")
        self.assertEqual(jobs[0]["job_id"], created["job_id"])

    def test_duplicate_submit_protection_returns_active_or_completed_job(self):
        created = create_video_job(self.conn, 1, "C001")

        existing = find_existing_video_job(self.conn, 1, "C001")
        duplicate = create_video_job(self.conn, 1, "C001")

        self.assertEqual(existing["job_id"], created["job_id"])
        self.assertEqual(duplicate["job_id"], created["job_id"])
        self.assertEqual(len(list_video_jobs(self.conn)), 1)

    def test_failed_job_can_be_recreated(self):
        created = create_video_job(self.conn, 1, "C001")
        mark_video_job_failed(self.conn, created["job_id"], "Runway failed")

        recreated = create_video_job(self.conn, 1, "C001")

        self.assertNotEqual(recreated["job_id"], created["job_id"])
        self.assertEqual(len(list_video_jobs(self.conn)), 2)

    def test_run_fake_video_job_transitions_to_completed_and_saves_paths(self):
        provider = FakeVideoProvider(task_id="fake-video-task-001")

        job = run_fake_video_job(
            self.conn,
            generation_id=1,
            creative_id="SPK-BR-FB-20260808-C001",
            request_data={"voiceover": "Olá", "cta": "Start"},
            output_root=self.output_dir,
            video_provider=provider,
        )

        self.assertEqual(job["status"], "COMPLETED")
        self.assertEqual(job["runway_task_id"], "fake-video-task-001")
        self.assertTrue(job["audio_path"].endswith("voiceover.mp3"))
        self.assertTrue(job["video_path"].endswith("runway.mp4"))
        self.assertTrue(job["subtitle_path"].endswith("subtitles.srt"))
        self.assertTrue(job["final_mp4_path"].endswith("SPK-BR-FB-20260808-C001-V1.mp4"))
        self.assertTrue(os.path.exists(job["final_mp4_path"]))

    def test_run_real_video_job_transitions_to_completed_and_saves_final_mp4(self):
        reference = self._reference_png()
        provider = FakeVideoProvider(task_id="real-task-001")
        voice = FakeVoiceProvider()

        job = run_real_video_job(
            self.conn,
            generation_id=1,
            creative_id="SPK-BR-FB-20260808-C001",
            request_data={
                "reference_image_path": reference,
                "runway_prompt": "vertical product walkthrough",
                "voiceover": "This is the voiceover.",
                "captions": ["This is the caption."],
                "cta": "Learn More",
                "compliance_footer": "21+ Play Responsibly",
                "voice_id": "voice-1",
            },
            output_root=self.output_dir,
            video_provider=provider,
            voice_provider=voice,
            composer=self._fake_composer,
        )

        self.assertEqual(job["status"], "COMPLETED")
        self.assertEqual(job["runway_task_id"], "real-task-001")
        self.assertTrue(os.path.exists(job["video_path"]))
        self.assertTrue(os.path.exists(job["audio_path"]))
        self.assertTrue(os.path.exists(job["subtitle_path"]))
        self.assertTrue(os.path.exists(job["final_mp4_path"]))
        self.assertEqual(job["request"]["production_mode"], "REAL")

    def test_run_real_video_job_failure_marks_failed_and_preserves_artifacts(self):
        reference = self._reference_png()

        def failing_composer(*_args, **_kwargs):
            raise RuntimeError("ffmpeg failed")

        job = run_real_video_job(
            self.conn,
            generation_id=1,
            creative_id="SPK-BR-FB-20260808-C001",
            request_data={"reference_image_path": reference, "voiceover": "hello", "captions": ["hello"], "voice_id": "voice-1"},
            output_root=self.output_dir,
            video_provider=FakeVideoProvider(task_id="task-1"),
            voice_provider=FakeVoiceProvider(),
            composer=failing_composer,
        )

        self.assertEqual(job["status"], "FAILED")
        self.assertIn("ffmpeg failed", job["error_message"])
        self.assertTrue(os.path.exists(job["video_path"]))
        self.assertTrue(os.path.exists(job["audio_path"]))
        self.assertTrue(os.path.exists(job["subtitle_path"]))

    def test_run_real_video_job_requires_reference_image(self):
        job = run_real_video_job(
            self.conn,
            generation_id=1,
            creative_id="SPK-BR-FB-20260808-C001",
            request_data={"voiceover": "hello", "voice_id": "voice-1"},
            output_root=self.output_dir,
            video_provider=FakeVideoProvider(),
            voice_provider=FakeVoiceProvider(),
            composer=self._fake_composer,
        )

        self.assertEqual(job["status"], "FAILED")
        self.assertIn("reference image", job["error_message"])

    def _reference_png(self):
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.tmpdir.name, "reference.png")
        with open(path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\nfake")
        return path

    def _fake_composer(self, _video_path, _audio_path, _subtitle_path, output_path, **_kwargs):
        with open(output_path, "wb") as handle:
            handle.write(b"mp4")
        return {"path": output_path}


if __name__ == "__main__":
    unittest.main()
