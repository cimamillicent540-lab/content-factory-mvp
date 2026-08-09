"""Voice provider interfaces for video production."""

import json
import os
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


class VoiceProvider:
    def generate_voice(self, text, destination_path, voice_id=None, style_prompt=None):
        raise NotImplementedError


class VoiceProviderError(RuntimeError):
    pass


class FakeVoiceProvider(VoiceProvider):
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = {"generate_voice": 0}

    def generate_voice(self, text, destination_path, voice_id=None, style_prompt=None):
        self.calls["generate_voice"] += 1
        if self.fail:
            raise VoiceProviderError("Fake ElevenLabs failure")
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "wb") as handle:
            handle.write(b"fake mp3 placeholder")
        return {"path": destination_path, "voice_id": voice_id or "fake-voice", "character_count": len(text or "")}


class ElevenLabsVoiceProvider(VoiceProvider):
    def __init__(
        self,
        api_key=None,
        voice_id=None,
        model_id=None,
        timeout_seconds=None,
        http_client=None,
        base_url="https://api.elevenlabs.io/v1",
    ):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise VoiceProviderError("ELEVENLABS_API_KEY is required when VIDEO_PRODUCTION_PROVIDER=real.")
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
        if not self.voice_id:
            raise VoiceProviderError("ELEVENLABS_VOICE_ID is required when VIDEO_PRODUCTION_PROVIDER=real.")
        self.model_id = model_id or os.environ.get("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2"
        self.timeout_seconds = int(timeout_seconds or os.environ.get("ELEVENLABS_TIMEOUT_SECONDS") or 60)
        self.http_client = http_client or _StdlibElevenLabsClient()
        self.base_url = base_url.rstrip("/")

    def generate_voice(self, text, destination_path, voice_id=None, style_prompt=None):
        voice_id = voice_id or self.voice_id
        if not voice_id:
            raise VoiceProviderError("ELEVENLABS_VOICE_ID is required when VIDEO_PRODUCTION_PROVIDER=real.")
        if not text:
            raise VoiceProviderError("Voiceover text is required for ElevenLabs.")
        payload = {
            "text": text,
            "model_id": self.model_id,
        }
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        metadata = self.http_client.post_audio(
            f"{self.base_url}/text-to-speech/{voice_id}",
            payload,
            destination_path,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            timeout=self.timeout_seconds,
        )
        return {
            "path": destination_path,
            "voice_id": voice_id,
            "model_id": self.model_id,
            "character_count": len(text),
            "metadata": metadata or {},
        }


class _StdlibElevenLabsClient:
    def post_audio(self, url, payload, destination_path, headers=None, timeout=60):
        request = urllib_request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers or {},
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                audio = response.read()
                request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise VoiceProviderError(f"ElevenLabs API request failed: {_safe_error(exc)}") from exc
        if not audio:
            raise VoiceProviderError("ElevenLabs returned empty audio.")
        with open(destination_path, "wb") as handle:
            handle.write(audio)
        return {"request_id": request_id} if request_id else {}


def _safe_error(exc):
    message = str(exc)
    secret = os.environ.get("ELEVENLABS_API_KEY")
    return message.replace(secret, "[redacted]") if secret else message
