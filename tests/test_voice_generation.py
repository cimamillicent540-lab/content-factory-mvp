import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_factory.voice_generation import ElevenLabsVoiceProvider, FakeVoiceProvider, VoiceProvider, VoiceProviderError


class VoiceGenerationTests(unittest.TestCase):
    def test_voice_provider_interface_is_abstract(self):
        provider = VoiceProvider()

        with self.assertRaises(NotImplementedError):
            provider.generate_voice("hello", "/tmp/voice.mp3")

    def test_fake_voice_provider_creates_mp3_without_network(self):
        provider = FakeVoiceProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "voiceover.mp3"

            result = provider.generate_voice("hello", str(path), voice_id="fake-voice")

            self.assertEqual(result["path"], str(path))
            self.assertEqual(result["voice_id"], "fake-voice")
            self.assertEqual(path.read_bytes(), b"fake mp3 placeholder")

    def test_elevenlabs_requires_api_key_and_voice_id(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(VoiceProviderError, "ELEVENLABS_API_KEY"):
                ElevenLabsVoiceProvider()
        with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
            with self.assertRaisesRegex(VoiceProviderError, "ELEVENLABS_VOICE_ID"):
                ElevenLabsVoiceProvider()

    def test_elevenlabs_voice_generation_success_and_mp3_saved(self):
        client = FakeElevenLabsClient()
        provider = ElevenLabsVoiceProvider(api_key="test-key", voice_id="voice-123", http_client=client)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "voiceover.mp3"

            result = provider.generate_voice("This is the actual voiceover.", str(path), style_prompt="warm")

            self.assertEqual(result["path"], str(path))
            self.assertEqual(result["voice_id"], "voice-123")
            self.assertEqual(path.read_bytes(), b"mp3-bytes")
            self.assertEqual(client.payload["text"], "This is the actual voiceover.")
            self.assertNotIn("warm", client.payload["text"])

    def test_elevenlabs_failure_is_clear(self):
        provider = ElevenLabsVoiceProvider(api_key="test-key", voice_id="voice-123", http_client=FakeElevenLabsClient(fail=True))
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(VoiceProviderError, "API failure"):
                provider.generate_voice("hello", str(Path(tmpdir) / "voiceover.mp3"))


class FakeElevenLabsClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.payload = None

    def post_audio(self, _url, payload, destination_path, headers=None, timeout=60):
        if self.fail:
            raise VoiceProviderError("API failure")
        self.payload = payload
        Path(destination_path).write_bytes(b"mp3-bytes")
        return {"request_id": "req-1"}


if __name__ == "__main__":
    unittest.main()
