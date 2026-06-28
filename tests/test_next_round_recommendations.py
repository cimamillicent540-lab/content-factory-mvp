import unittest

from content_factory.next_round_recommendations import build_next_round_recommendations


class NextRoundRecommendationTests(unittest.TestCase):
    def test_returns_scale_candidates_for_scale_rows(self):
        result = build_next_round_recommendations(self._report_with({"C001": self._metrics("SCALE_CANDIDATE")}))

        self.assertEqual(result["scale_candidates"][0]["creative_id"], "C001")
        self.assertEqual(result["scale_candidates"][0]["priority"], "High")

    def test_returns_needs_recut_for_recut_rows(self):
        result = build_next_round_recommendations(self._report_with({"C002": self._metrics("NEEDS_RECUT")}))

        self.assertEqual(result["needs_recut"][0]["creative_id"], "C002")
        self.assertIn("first 3 seconds", result["needs_recut"][0]["suggested_variation"])

    def test_returns_landing_page_checks_for_landing_page_rows(self):
        result = build_next_round_recommendations(self._report_with({"C003": self._metrics("CHECK_LANDING_PAGE")}))

        self.assertEqual(result["landing_page_checks"][0]["creative_id"], "C003")
        self.assertIn("message match", result["landing_page_checks"][0]["next_action"])

    def test_returns_pause_for_pause_rows(self):
        result = build_next_round_recommendations(self._report_with({"C004": self._metrics("PAUSE")}))

        self.assertEqual(result["pause"][0]["creative_id"], "C004")
        self.assertIn("Pause", result["pause"][0]["next_action"])

    def test_returns_keep_testing_for_keep_testing_rows(self):
        result = build_next_round_recommendations(self._report_with({"C005": self._metrics("KEEP_TESTING")}))

        self.assertEqual(result["keep_testing"][0]["creative_id"], "C005")
        self.assertEqual(result["keep_testing"][0]["priority"], "Medium")

    def test_returns_next_round_angles_and_creative_brief_requests(self):
        result = build_next_round_recommendations(
            self._report_with(
                {
                    "C001": self._metrics("SCALE_CANDIDATE"),
                    "C002": self._metrics("NEEDS_RECUT"),
                }
            )
        )

        self.assertTrue(result["next_round_angles"])
        self.assertTrue(result["creative_brief_requests"])
        self.assertIn("Create 2-3 controlled variants", " ".join(result["creative_brief_requests"]))

    def test_low_3s_view_and_low_ctr_recommends_recut_hook(self):
        metrics = self._metrics("KEEP_TESTING", ctr=0.003, video_3s_rate=0.04)
        result = build_next_round_recommendations(self._report_with({"C006": metrics}))

        self.assertEqual(result["needs_recut"][0]["creative_id"], "C006")
        self.assertIn("hook", result["needs_recut"][0]["next_action"])

    def test_high_ctr_low_registration_recommends_landing_page_check(self):
        metrics = self._metrics("KEEP_TESTING", ctr=0.03, registrations=0, deposits=0)
        result = build_next_round_recommendations(self._report_with({"C007": metrics}))

        self.assertEqual(result["landing_page_checks"][0]["creative_id"], "C007")
        self.assertIn("landing page", result["landing_page_checks"][0]["suggested_variation"])

    def test_scale_candidate_recommends_controlled_variations(self):
        result = build_next_round_recommendations(self._report_with({"C008": self._metrics("SCALE_CANDIDATE")}))

        item = result["scale_candidates"][0]
        self.assertIn("controlled variations", item["next_action"])
        self.assertIn("same angle", item["suggested_variation"])

    def _report_with(self, creatives):
        return {
            "report_id": "perf-test",
            "summary": {"total_creatives_matched": len(creatives)},
            "aggregated": {"creatives": creatives},
        }

    def _metrics(self, recommendation, ctr=0.018, video_3s_rate=0.18, registrations=3, deposits=1):
        return {
            "creative_id": "unused",
            "recommendation": recommendation,
            "reason": f"{recommendation} reason",
            "action": f"{recommendation} action",
            "ctr": ctr,
            "video_3s_rate": video_3s_rate,
            "registrations": registrations,
            "deposits": deposits,
        }
