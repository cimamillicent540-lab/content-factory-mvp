import tempfile
import unittest
from pathlib import Path

from content_factory.ffmpeg_composer import FFmpegComposerError, build_ffmpeg_command, compose_video, write_subtitles


class FFmpegComposerTests(unittest.TestCase):
    def test_write_subtitles_allocates_non_overlapping_times(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subtitles.srt"

            write_subtitles(["Hook", "CTA"], str(path), duration_seconds=10)

            body = path.read_text()
            self.assertIn("00:00:00,000 --> 00:00:05,000", body)
            self.assertIn("00:00:05,000 --> 00:00:10,000", body)
            self.assertIn("Hook", body)

    def test_command_includes_vertical_h264_aac_subtitle_cta_and_compliance(self):
        command = build_ffmpeg_command(
            "runway.mp4",
            "voiceover.mp3",
            "subtitles.srt",
            "final.mp4",
            "Learn More",
            "21+ Play Responsibly",
        )
        command_text = " ".join(command)

        self.assertIn("-stream_loop -1", command_text)
        self.assertIn("scale=1080:1920", command_text)
        self.assertIn("crop=1080:1920", command_text)
        self.assertIn("libx264", command)
        self.assertIn("aac", command)
        self.assertIn("subtitles=", command_text)
        self.assertIn("Learn More", command_text)
        self.assertIn("21+ Play Responsibly", command_text)
        self.assertIn("+faststart", command)

    def test_compose_video_uses_fake_subprocess_success(self):
        calls = []

        def runner(command, capture_output=True, text=True, check=False):
            calls.append(command)
            Path(command[-1]).write_bytes(b"mp4")
            return Result(0, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "final.mp4"

            result = compose_video("runway.mp4", "voiceover.mp3", "subtitles.srt", str(output), runner=runner)

            self.assertEqual(result["path"], str(output))
            self.assertTrue(output.exists())
            self.assertEqual(calls[0][-1], str(output))

    def test_compose_video_failure_is_clear(self):
        def runner(_command, capture_output=True, text=True, check=False):
            return Result(1, "ffmpeg failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(FFmpegComposerError, "ffmpeg failed"):
                compose_video("runway.mp4", "voiceover.mp3", "subtitles.srt", str(Path(tmpdir) / "final.mp4"), runner=runner)


class Result:
    def __init__(self, returncode, stderr):
        self.returncode = returncode
        self.stderr = stderr


if __name__ == "__main__":
    unittest.main()
