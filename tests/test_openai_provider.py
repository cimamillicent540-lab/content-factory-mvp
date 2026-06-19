import json
import unittest

from content_factory.ai_provider import OpenAIProvider, ProviderResponseError


class FakeResponses:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        self.client.calls.append(kwargs)
        return self.client.response


class FakeClient:
    def __init__(self, payload):
        self.calls = []
        self.response = type("Response", (), {"output_text": json.dumps(payload, ensure_ascii=False)})()
        self.responses = FakeResponses(self)


class OpenAIProviderTests(unittest.TestCase):
    def test_structure_demand_parses_structured_json(self):
        client = FakeClient({"平台": "Facebook", "国家": "巴西", "人群": "新用户", "场景": "移动端", "目标": "注册转化", "时长": "15秒", "输出物": ["脚本"], "缺失信息": []})
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        result = provider.structure_demand("给Facebook巴西用户做广告", {"platform": "Facebook"})
        self.assertEqual(result["平台"], "Facebook")
        self.assertEqual(result["缺失信息"], [])

    def test_language_parameter_is_included_in_generation_prompt_for_supported_languages(self):
        for language in ("pt-BR", "es", "en", "zh"):
            client = FakeClient(self._generation_payload())
            provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
            provider.generate_content(
                {"name": "CopyTrade Pro", "selling_points": "signup reward"},
                {"raw_input": "demo", "structured": {"语言": language, "平台": "Facebook"}},
                [],
                [],
                {"status": "PASS"},
            )
            prompt = client.calls[-1]["input"]
            self.assertIn(language, prompt)

    def test_generate_content_parses_required_json_fields(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        result = provider.generate_content({"name": "CopyTrade Pro"}, {"structured": {"语言": "en"}}, [], [], {"status": "PASS"})
        self.assertEqual(result["素材方向"], "Direction")
        self.assertIn("15秒脚本", result["脚本"])

    def test_blocked_audit_still_prevents_generation_without_openai_call(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        result = provider.audit_materials(
            {"forbidden_claims": "保证收益"},
            {"raw_input": "请生成保证收益广告", "structured": {}},
            [{"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1}],
        )
        self.assertEqual(result["status"], "FATAL_FAILED")
        self.assertEqual(client.calls, [])

    def test_invalid_json_returns_readable_error(self):
        client = FakeClient({})
        client.response = type("Response", (), {"output_text": "not-json"})()
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        with self.assertRaisesRegex(ProviderResponseError, "JSON"):
            provider.structure_demand("demo", {})

    def _generation_payload(self):
        return {
            "素材方向": "Direction",
            "脚本": {"10秒脚本": "A", "15秒脚本": "B", "30秒脚本": "C"},
            "旁白": "Voice",
            "字幕": ["Caption"],
            "分镜": [{"镜头": 1}],
            "Runway Prompt": "Runway",
            "HeyGen Prompt": "HeyGen",
            "ElevenLabs Prompt": "ElevenLabs",
            "Facebook广告文案": "Facebook",
            "TikTok广告文案": "TikTok",
            "合规提醒": "Safe",
        }
