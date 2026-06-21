import os
import tempfile
import unittest

from content_factory.api import create_app


class WebUiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.app = create_app(os.path.join(self.tmpdir.name, "web.sqlite3"))

    def test_homepage_returns_minimal_html_form(self):
        status, headers, body = self.app.handle("GET", "/")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("海外投流素材内容工厂", body)
        self.assertIn('name="industry"', body)
        self.assertIn('name="product"', body)
        self.assertIn('name="platform"', body)
        self.assertIn('name="country"', body)
        self.assertIn('name="language"', body)
        self.assertIn('name="audience"', body)
        self.assertIn('name="selling_points"', body)
        self.assertIn('name="duration"', body)
        self.assertIn('name="restrictions"', body)
        self.assertNotIn("加密货币跟单产品", body)
        self.assertIn('name="product" value="Spikex"', body)
        self.assertIn('name="industry" value="crypto exchange"', body)
        self.assertIn('name="platform" value="Facebook Ads"', body)
        self.assertIn('name="country" value="Brazil"', body)
        self.assertIn('name="language" value="Brazilian Portuguese"', body)
        self.assertIn("Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools", body)
        self.assertIn("AI copy trading, crypto trading, US stocks trading, fast onboarding, beginner-friendly trading experience", body)
        self.assertIn("Avoid unrealistic financial promises, avoid exaggerated claims, follow platform ad policy, include risk-aware language", body)
        self.assertIn('name="forbidden_claims" value="guaranteed profit, risk-free, no loss"', body)
        self.assertIn("Generate 5 short video ad concepts with hooks, scripts, voiceover, captions and Runway prompts", body)

    def test_homepage_calls_existing_generate_api(self):
        _status, _headers, body = self.app.handle("GET", "/")

        self.assertIn("fetch('/generate'", body)
        self.assertIn('"行业": form.industry.value', body)
        self.assertIn('"限制词": form.restrictions.value', body)
        self.assertIn('"语言": form.language.value', body)
        self.assertIn("BLOCKED", body)
        self.assertIn("generation_id", body)
        self.assertIn("素材内容", body)
        self.assertIn("JSON.stringify", body)

    def test_homepage_renders_generated_creative_sections(self):
        _status, _headers, body = self.app.handle("GET", "/")

        self.assertIn("Content Factory MVP", body)
        self.assertIn("Overseas Ad Creative Generator", body)
        self.assertIn('name="campaign_rules"', body)
        self.assertIn('name="forbidden_claims"', body)
        self.assertIn("renderGenerated", body)
        self.assertIn("creative-card", body)
        self.assertIn("video_ad_concepts", body)
        self.assertIn("runway_prompt", body)
        self.assertIn("elevenlabs_prompt", body)
        self.assertIn("facebook_primary_text", body)
        self.assertIn("facebook_headline", body)
        self.assertIn("facebook_description", body)
        self.assertNotIn("field('compliance_notes'", body)
        self.assertIn("scoring_report", body)
        self.assertIn("launch_plan", body)
        self.assertIn("forbidden_claims_check", body)
        self.assertIn("JSON.stringify(result, null, 2)", body)

    def test_homepage_renders_blocked_state_without_creative_cards(self):
        _status, _headers, body = self.app.handle("GET", "/")

        self.assertIn("renderBlocked", body)
        self.assertIn("阻断原因", body)
        self.assertIn("替代表达建议", body)
        self.assertIn("BLOCKED 状态不展示素材卡片", body)
