import json
import os
import tempfile
import unittest
from pathlib import Path

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

    def test_homepage_includes_demo_fill_buttons(self):
        _status, _headers, body = self.app.handle("GET", "/")

        self.assertIn("Spikex Brazil Demo", body)
        self.assertIn("BLOCKED Risk Demo", body)
        self.assertIn("Clear Form", body)
        self.assertIn("fillDemo('spikex')", body)
        self.assertIn("fillDemo('blocked')", body)
        self.assertIn("clearForm()", body)
        self.assertIn("guaranteed profit, risk-free trading, no loss", body)

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
        self.assertIn("Saved to History", body)
        self.assertIn("View History", body)

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
        self.assertIn("copyBox(concept.facebook_primary_text)", body)
        self.assertIn("copyBox(concept.facebook_headline)", body)
        self.assertIn("copyBox(concept.facebook_description)", body)
        self.assertNotIn("field('compliance_notes'", body)
        self.assertIn("scoring_report", body)
        self.assertIn("launch_plan", body)
        self.assertIn("forbidden_claims_check", body)
        self.assertIn("JSON.stringify(result, null, 2)", body)

    def test_homepage_renders_copyable_creative_brief_markdown_for_generated_results(self):
        _status, _headers, body = self.app.handle("GET", "/")
        generated_segment = body[body.index("function renderGenerated") : body.index("function renderStatus")]

        self.assertIn("Creative Brief Markdown", generated_segment)
        self.assertIn("Copy Full Brief", generated_segment)
        self.assertIn("renderCreativeBriefMarkdown(content, result)", generated_segment)
        self.assertIn("brief-copy-box", body)
        self.assertIn("copyFullBrief", body)

    def test_creative_brief_markdown_includes_delivery_fields(self):
        _status, _headers, body = self.app.handle("GET", "/")

        self.assertIn("# Creative Brief", body)
        self.assertIn("## Campaign Summary", body)
        self.assertIn("## Creative Concepts", body)
        self.assertIn("## Scoring Report", body)
        self.assertIn("## Media Production Notes", body)
        self.assertIn("## Launch Plan", body)
        self.assertIn("## Forbidden Claims Check", body)
        self.assertIn("concepts.forEach", body)
        self.assertIn("scene_breakdown", body)
        self.assertIn("runway_prompt", body)
        self.assertIn("elevenlabs_prompt", body)
        self.assertIn("facebook_primary_text", body)
        self.assertIn("facebook_headline", body)
        self.assertIn("facebook_description", body)

    def test_homepage_renders_blocked_state_without_creative_cards(self):
        _status, _headers, body = self.app.handle("GET", "/")
        blocked_segment = body[body.index("function renderBlocked") : body.index("function renderRawJson")]

        self.assertIn("renderBlocked", body)
        self.assertIn("阻断原因", body)
        self.assertIn("替代表达建议", body)
        self.assertIn("BLOCKED 状态不展示素材卡片", body)
        self.assertNotIn("Creative Brief Markdown", blocked_segment)

    def test_history_page_exists_and_lists_generated_records(self):
        _status, _headers, body = self.app.handle("POST", "/generate", self._valid_request())
        generated = json.loads(body)

        status, headers, body = self.app.handle("GET", "/history")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("Generation History", body)
        self.assertIn(str(generated["generation_id"]), body)
        self.assertIn("GENERATED", body)
        self.assertIn("Spikex", body)
        self.assertIn("crypto exchange", body)
        self.assertIn("Facebook Ads", body)
        self.assertIn("Brazilian Portuguese", body)
        self.assertIn("concept count", body)
        self.assertIn(f'/history/{generated["generation_id"]}', body)

    def test_history_page_lists_blocked_records(self):
        status, _headers, _body = self.app.handle("POST", "/generate", self._blocked_request())
        self.assertEqual(status, 409)

        status, _headers, body = self.app.handle("GET", "/history")

        self.assertEqual(status, 200)
        self.assertIn("BLOCKED", body)
        self.assertIn("blocked-", body)
        self.assertIn("Spikex", body)
        self.assertIn("View", body)

    def test_history_detail_generated_shows_creative_brief_and_copy(self):
        _status, _headers, body = self.app.handle("POST", "/generate", self._valid_request())
        generated = json.loads(body)

        status, _headers, body = self.app.handle("GET", f'/history/{generated["generation_id"]}')

        self.assertEqual(status, 200)
        self.assertIn("Generation Detail", body)
        self.assertIn("GENERATED", body)
        self.assertIn("Creative Brief Markdown", body)
        self.assertIn("Copy Full Brief", body)
        self.assertIn("# Creative Brief", body)
        self.assertIn("runway_prompt", body)
        self.assertIn("Raw JSON", body)

    def test_history_detail_blocked_does_not_show_creative_brief(self):
        status, _headers, _body = self.app.handle("POST", "/generate", self._blocked_request())
        self.assertEqual(status, 409)
        status, _headers, history_body = self.app.handle("GET", "/history")
        marker = 'href="/history/blocked-'
        start = history_body.index(marker) + len('href="/history/')
        blocked_id = history_body[start : history_body.index('"', start)]

        status, _headers, body = self.app.handle("GET", f"/history/{blocked_id}")

        self.assertEqual(status, 200)
        self.assertIn("BLOCKED", body)
        self.assertIn("阻断原因", body)
        self.assertIn("risk_explanation", body)
        self.assertIn("Raw JSON", body)
        self.assertNotIn("Creative Brief Markdown", body)

    def test_history_detail_missing_returns_clear_404(self):
        status, headers, body = self.app.handle("GET", "/history/999999")

        self.assertEqual(status, 404)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("History record not found", body)

    def test_readme_documents_local_web_demo(self):
        readme = Path("README.md").read_text()

        self.assertIn("CONTENT_FACTORY_PROVIDER=mock python3 -m content_factory.api --host 127.0.0.1 --port 8000", readme)
        self.assertIn("http://127.0.0.1:8000", readme)
        self.assertIn("CONTENT_FACTORY_PROVIDER=mock python3 -m unittest discover -v", readme)
        self.assertIn("python3 -m compileall content_factory tests", readme)

    def _valid_request(self):
        return {
            "行业": "crypto exchange",
            "产品": "Spikex",
            "投放平台": "Facebook Ads",
            "国家": "Brazil",
            "语言": "Brazilian Portuguese",
            "目标人群": "Brazilian retail traders interested in crypto",
            "卖点": "AI copy trading, crypto trading, US stocks trading, fast onboarding",
            "活动规则": "Follow platform policy and use risk-aware language",
            "限制词": "guaranteed profit, risk-free, no loss",
            "需求": "Generate 5 short video ad concepts",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

    def _blocked_request(self):
        request = self._valid_request()
        request["卖点"] = "guaranteed profit, risk-free trading, no loss"
        request["限制词"] = "none"
        return request
