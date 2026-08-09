import tempfile
import unittest
from pathlib import Path

from content_factory.file_storage import FileValidationError, safe_job_file, save_reference_image


class FileStorageTests(unittest.TestCase):
    def test_valid_png_and_jpg_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            png = save_reference_image({"filename": "ref.png", "content": b"\x89PNG\r\n\x1a\nfake"}, "video-20260809000000-abc12345", tmpdir)
            jpg = save_reference_image({"filename": "ref.jpg", "content": b"\xff\xd8\xfffake"}, "video-20260809000000-def67890", tmpdir)

            self.assertTrue(Path(png).exists())
            self.assertTrue(Path(jpg).exists())
            self.assertTrue(png.endswith("reference.png"))
            self.assertTrue(jpg.endswith("reference.jpg"))

    def test_invalid_extension_signature_traversal_and_oversize_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(FileValidationError, "PNG, JPG"):
                save_reference_image({"filename": "ref.html", "content": b"<script>"}, "video-20260809000000-abc12345", tmpdir)
            with self.assertRaisesRegex(FileValidationError, "signature"):
                save_reference_image({"filename": "ref.png", "content": b"<html>"}, "video-20260809000000-abc12345", tmpdir)
            with self.assertRaisesRegex(FileValidationError, "not safe"):
                save_reference_image({"filename": "../ref.png", "content": b"\x89PNG\r\n\x1a\nfake"}, "video-20260809000000-abc12345", tmpdir)
            with self.assertRaisesRegex(FileValidationError, "10MB"):
                save_reference_image({"filename": "ref.png", "content": b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 + 1)}, "video-20260809000000-abc12345", tmpdir)

    def test_safe_job_file_rejects_paths_outside_job_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            job = {"job_id": "video-20260809000000-abc12345", "final_mp4_path": "/etc/passwd"}

            with self.assertRaisesRegex(FileValidationError, "outside"):
                safe_job_file(job, "final_mp4_path", tmpdir)


if __name__ == "__main__":
    unittest.main()
