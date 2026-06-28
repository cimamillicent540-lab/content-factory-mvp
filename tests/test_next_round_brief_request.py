import unittest

from content_factory.next_round_brief_request import build_next_round_brief_request


class NextRoundBriefRequestTests(unittest.TestCase):
    def test_returns_markdown_text(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIsInstance(result["markdown"], str)
        self.assertTrue(result["markdown"].startswith("# Next Round Creative Brief Request"))

    def test_markdown_includes_required_sections(self):
        markdown = build_next_round_brief_request(self._performance_report(), self._recommendations())["markdown"]

        self.assertIn("## Next Round Objective", markdown)
        self.assertIn("## Source Performance Report", markdown)
        self.assertIn("## Priority Creative Actions", markdown)
        self.assertIn("## Next Round Generation Requests", markdown)
        self.assertIn("## Do Not Repeat", markdown)
        self.assertIn("## Internal Production Notes", markdown)
        self.assertIn("## Suggested Naming", markdown)

    def test_scale_candidate_produces_variant_generation_request(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIn("Generate 3 new variants based on SPK-BR-FB-20260628-C001", result["markdown"])
        self.assertIn("SPK-BR-FB-20260628-C001-V2A", result["markdown"])
        self.assertIn("SPK-BR-FB-20260628-C001-V2B", result["markdown"])

    def test_needs_recut_produces_recut_request(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIn("Recut SPK-BR-FB-20260628-C002", result["markdown"])
        self.assertIn("first 3 seconds", result["markdown"])
        self.assertIn("SPK-BR-FB-20260628-C002-RECUT-V2A", result["markdown"])

    def test_landing_page_check_produces_message_match_request(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIn("message match", result["markdown"])
        self.assertIn("onboarding", result["markdown"])
        self.assertIn("trust", result["markdown"])

    def test_paused_creative_appears_in_do_not_repeat(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIn("Do not scale paused creatives", result["markdown"])
        self.assertIn("SPK-BR-FB-20260628-C004", result["markdown"])

    def test_returns_structured_priority_actions_and_suggested_naming(self):
        result = build_next_round_brief_request(self._performance_report(), self._recommendations())

        self.assertIn("structured", result)
        self.assertTrue(result["structured"]["priority_actions"]["High"])
        self.assertIn("SPK-BR-FB-20260628-C001-V2A", result["structured"]["suggested_naming"])

    def _performance_report(self):
        return {
            "report_id": "perf-test",
            "created_at": "2026-06-28 13:00:00",
            "summary": {"total_creatives_matched": 4, "total_spend": 120},
            "aggregated": {
                "summary": {
                    "total_impressions": 18000,
                    "total_clicks": 260,
                    "total_registrations": 8,
                    "total_deposits": 2,
                }
            },
        }

    def _recommendations(self):
        return {
            "scale_candidates": [
                {
                    "creative_id": "SPK-BR-FB-20260628-C001",
                    "current_recommendation": "SCALE_CANDIDATE",
                    "reason": "Strong CTR and at least one deposit.",
                    "next_action": "Create 2-3 controlled variations before increasing budget.",
                    "suggested_variation": "Keep same angle and test stronger first 3-second hook.",
                    "priority": "High",
                }
            ],
            "needs_recut": [
                {
                    "creative_id": "SPK-BR-FB-20260628-C002",
                    "current_recommendation": "NEEDS_RECUT",
                    "reason": "Low first 3 seconds retention.",
                    "next_action": "Recut the hook before relaunch.",
                    "suggested_variation": "Focus on first 3 seconds, subtitle pacing, and clearer product context.",
                    "priority": "High",
                }
            ],
            "landing_page_checks": [
                {
                    "creative_id": "SPK-BR-FB-20260628-C003",
                    "current_recommendation": "CHECK_LANDING_PAGE",
                    "reason": "High CTR but low registration.",
                    "next_action": "Review landing page message match and trust signals.",
                    "suggested_variation": "Create a message-match and onboarding trust version.",
                    "priority": "High",
                }
            ],
            "pause": [
                {
                    "creative_id": "SPK-BR-FB-20260628-C004",
                    "current_recommendation": "PAUSE",
                    "reason": "Weak response after spend.",
                    "next_action": "Pause for now.",
                    "suggested_variation": "Rework the core angle before relaunch.",
                    "priority": "High",
                }
            ],
            "keep_testing": [],
            "copy_or_cta_tests": [],
            "creative_brief_requests": [
                "Create 2-3 controlled variants based on SPK-BR-FB-20260628-C001.",
                "Recut SPK-BR-FB-20260628-C002 with stronger first 3 seconds.",
            ],
        }
