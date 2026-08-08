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
    update_video_job_status,
)


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


if __name__ == "__main__":
    unittest.main()
