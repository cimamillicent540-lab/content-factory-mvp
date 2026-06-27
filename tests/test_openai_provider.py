import json
import unittest

from content_factory.ai_provider import OpenAIProvider, ProviderResponseError


class FakeResponses:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        if "response_format" in kwargs:
            raise TypeError("create() got an unexpected keyword argument 'response_format'")
        self.client.calls.append(kwargs)
        return self.client.response


class FakeClient:
    def __init__(self, payload):
        self.calls = []
        self.response = type("Response", (), {"output_text": json.dumps(payload, ensure_ascii=False)})()
        self.responses = FakeResponses(self)


class FailingResponses:
    def create(self, **kwargs):
        raise RuntimeError("network unavailable")


class FailingClient:
    def __init__(self):
        self.responses = FailingResponses()


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

    def test_crypto_exchange_template_guidance_is_included_in_generation_prompt(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)

        provider.generate_content(
            {
                "name": "Spikex",
                "category": "crypto exchange",
                "selling_points": "AI copy trading, crypto trading, US stocks trading, fast onboarding",
                "forbidden_claims": "guaranteed profit, risk-free, no loss",
            },
            {
                "raw_input": "Facebook Brazil 15s crypto exchange onboarding",
                "structured": {"语言": "pt-BR", "平台": "Facebook", "国家": "巴西"},
            },
            [],
            [],
            {"status": "PASS"},
        )

        prompt = client.calls[-1]["input"]
        self.assertIn("Crypto Exchange / Trading V1", prompt)
        self.assertIn("copy trading com IA", prompt)
        self.assertIn("guaranteed profit", prompt)
        self.assertIn("no guaranteed profit visuals", prompt)
        self.assertIn("forbidden_claims and campaign_rules are compliance references", prompt)

    def test_product_facts_are_included_in_generation_prompt(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)

        provider.generate_content(
            {
                "name": "Spikex",
                "category": "crypto exchange",
                "selling_points": "AI copy trading, crypto trading",
                "product_facts": [
                    "Spikex is positioned as a trading platform",
                    "Do not claim guaranteed results",
                ],
            },
            {
                "raw_input": "Facebook Brazil 15s",
                "structured": {"语言": "pt-BR", "平台": "Facebook", "国家": "Brazil"},
                "product_facts": ["The product may include AI copy trading messaging"],
            },
            [],
            [],
            {"status": "PASS"},
        )

        prompt = client.calls[-1]["input"]
        self.assertIn("Use product_facts as factual grounding", prompt)
        self.assertIn("Do not invent unsupported product features", prompt)
        self.assertIn("Do not copy campaign_rules directly into ad scripts", prompt)
        self.assertIn("Do not make profit promises", prompt)
        self.assertIn("Formal creative fields must follow requested language", prompt)
        self.assertIn("Spikex is positioned as a trading platform", prompt)
        self.assertIn("The product may include AI copy trading messaging", prompt)

    def test_generate_content_parses_required_json_fields(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        result = provider.generate_content({"name": "CopyTrade Pro"}, {"structured": {"语言": "en"}}, [], [], {"status": "PASS"})
        self.assertIn("campaign_summary", result)
        self.assertIn("scoring_report", result)
        self.assertIn("media_production_notes", result)
        self.assertIn("launch_plan", result)
        self.assertIn("forbidden_claims_check", result)
        self.assertEqual(len(result["video_ad_concepts"]), 5)
        self.assertEqual(result["video_ad_concepts"][0]["concept_id"], "C01")
        self.assertIn("15s_script", result["video_ad_concepts"][0])

    def test_blocked_generation_returns_controlled_blocked_payload_without_openai_call(self):
        client = FakeClient(self._generation_payload())
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        result = provider.generate_content(
            {"name": "CopyTrade Pro"},
            {"raw_input": "保证收益", "structured": {"语言": "en"}},
            [],
            [],
            {
                "status": "FATAL_FAILED",
                "risks": ["保证收益"],
                "risk_explanation": "命中禁用表达",
                "next_actions": ["删除禁用表达"],
            },
        )

        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn("video_ad_concepts", result)
        self.assertEqual(result["risks"], ["保证收益"])
        self.assertIn("risk_explanation", result)
        self.assertIn("safer_alternatives", result)
        self.assertIn("next_actions", result)
        self.assertIn("forbidden_claims_check", result)
        self.assertEqual(client.calls, [])

    def test_responses_create_uses_text_format_instead_of_response_format(self):
        client = FakeClient({"平台": "Facebook", "国家": "巴西", "人群": "新用户", "场景": "移动端", "目标": "注册转化", "时长": "15秒", "输出物": ["脚本"], "缺失信息": []})
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)

        provider.structure_demand("给Facebook巴西用户做广告", {"platform": "Facebook"})

        call = client.calls[-1]
        self.assertNotIn("response_format", call)
        self.assertIn("text", call)
        self.assertIn("format", call["text"])

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

    def test_empty_response_returns_readable_error(self):
        client = FakeClient({})
        client.response = type("Response", (), {"output_text": ""})()
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        with self.assertRaisesRegex(ProviderResponseError, "empty"):
            provider.structure_demand("demo", {})

    def test_openai_api_failure_returns_readable_error(self):
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=FailingClient())
        with self.assertRaisesRegex(ProviderResponseError, "OpenAI API call failed"):
            provider.structure_demand("demo", {})

    def test_missing_generation_fields_returns_readable_error(self):
        client = FakeClient({"campaign_summary": {}, "video_ad_concepts": []})
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        with self.assertRaisesRegex(ProviderResponseError, "素材内容 JSON missing required fields"):
            provider.generate_content({"name": "CopyTrade Pro"}, {"structured": {"语言": "en"}}, [], [], {"status": "PASS"})

    def test_missing_concept_fields_returns_readable_error(self):
        payload = self._generation_payload()
        del payload["video_ad_concepts"][0]["runway_prompt"]
        client = FakeClient(payload)
        provider = OpenAIProvider(api_key="test-key", model="gpt-test", client=client)
        with self.assertRaisesRegex(ProviderResponseError, "video_ad_concepts\\[0\\] JSON missing required fields"):
            provider.generate_content({"name": "CopyTrade Pro"}, {"structured": {"语言": "en"}}, [], [], {"status": "PASS"})

    def _generation_payload(self):
        return {
            "campaign_summary": {"产品": "CopyTrade Pro", "投放语言": "en"},
            "video_ad_concepts": [
                {
                    "concept_id": f"C{index:02d}",
                    "concept_name": f"Concept {index}",
                    "target_angle": "New users",
                    "hook": "Check the product rules first.",
                    "scene_breakdown": "Open with mobile UI, show product facts, close with CTA.",
                    "15s_script": "Check CopyTrade Pro, review the real rules, then decide.",
                    "voiceover": "Review the real interface and rules before you start.",
                    "captions": ["Check the rules", "Review the interface"],
                    "visual_style": "Clean mobile UI",
                    "runway_prompt": "English mobile ad with real UI.",
                    "elevenlabs_prompt": "English voiceover, calm and credible.",
                    "facebook_primary_text": "Check CopyTrade Pro before joining.",
                    "facebook_headline": "Check CopyTrade Pro",
                    "facebook_description": "Review the rules first.",
                    "compliance_notes": "No guaranteed returns.",
                }
                for index in range(1, 6)
            ],
            "scoring_report": {"total_score": 90},
            "media_production_notes": {"Runway 生成建议": "Use real UI screenshots."},
            "launch_plan": {"推荐优先测试": ["C01"]},
            "forbidden_claims_check": {"是否命中禁用词": False, "命中的词": []},
        }
