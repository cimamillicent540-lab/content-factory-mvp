import unittest

from content_factory.performance_analysis import (
    build_performance_summary,
    calculate_performance_metrics,
    classify_creative_performance,
    extract_creative_id,
    parse_performance_csv,
)


SAMPLE_CSV = """creative_id,spend,impressions,clicks,link_clicks,registrations,deposits,video_3s_views,video_50_views,video_95_views
SPK-BR-FB-20260628-C001,30,5000,80,65,5,1,1200,500,220
SPK-BR-FB-20260628-C002,25,4500,35,28,1,0,600,180,60
SPK-BR-FB-20260628-C003,20,3000,70,60,0,0,1000,650,300
"""


class PerformanceAnalysisTests(unittest.TestCase):
    def test_parse_performance_csv_parses_basic_csv(self):
        rows = parse_performance_csv(SAMPLE_CSV)

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["creative_id"], "SPK-BR-FB-20260628-C001")
        self.assertEqual(rows[0]["spend"], "30")

    def test_extract_creative_id_reads_creative_id_column(self):
        self.assertEqual(
            extract_creative_id({"Creative ID": "SPK-BR-FB-20260628-C001"}),
            "SPK-BR-FB-20260628-C001",
        )

    def test_extract_creative_id_from_ad_name(self):
        self.assertEqual(
            extract_creative_id({"Ad Name": "SPK-BR-FB-20260628-C001_ai_copy_trading_v1"}),
            "SPK-BR-FB-20260628-C001",
        )

    def test_metrics_aggregation_groups_by_creative_id(self):
        rows = parse_performance_csv(SAMPLE_CSV)
        result = calculate_performance_metrics(rows)

        self.assertEqual(result["summary"]["matched_creative_count"], 3)
        self.assertEqual(result["summary"]["unmatched_row_count"], 0)
        self.assertEqual(result["creatives"]["SPK-BR-FB-20260628-C001"]["total_spend"], 30)

    def test_rate_and_cost_calculations_are_correct(self):
        rows = parse_performance_csv(SAMPLE_CSV)
        metrics = calculate_performance_metrics(rows)["creatives"]["SPK-BR-FB-20260628-C001"]

        self.assertAlmostEqual(metrics["ctr"], 80 / 5000)
        self.assertAlmostEqual(metrics["link_ctr"], 65 / 5000)
        self.assertAlmostEqual(metrics["cpc"], 30 / 80)
        self.assertAlmostEqual(metrics["cpm"], 30 / 5000 * 1000)
        self.assertAlmostEqual(metrics["cpa_registration"], 30 / 5)
        self.assertAlmostEqual(metrics["cpa_deposit"], 30 / 1)
        self.assertAlmostEqual(metrics["video_3s_rate"], 1200 / 5000)
        self.assertAlmostEqual(metrics["video_50_retention"], 500 / 1200)
        self.assertAlmostEqual(metrics["video_95_retention"], 220 / 1200)

    def test_zero_division_does_not_crash(self):
        rows = parse_performance_csv("creative_id,spend,impressions,clicks\nSPK-BR-FB-20260628-C001,0,0,0\n")
        metrics = calculate_performance_metrics(rows)["creatives"]["SPK-BR-FB-20260628-C001"]

        self.assertIsNone(metrics["ctr"])
        self.assertIsNone(metrics["cpc"])
        self.assertIsNone(metrics["cpm"])

    def test_unmatched_rows_are_counted(self):
        rows = parse_performance_csv("ad_name,spend,impressions\nno_id_here,10,1000\n")
        result = calculate_performance_metrics(rows)

        self.assertEqual(result["summary"]["matched_creative_count"], 0)
        self.assertEqual(result["summary"]["unmatched_row_count"], 1)
        self.assertEqual(result["unmatched_rows"][0]["ad_name"], "no_id_here")

    def test_classify_needs_recut_for_low_ctr_and_low_3s_rate(self):
        classification = classify_creative_performance({"total_spend": 30, "impressions": 5000, "ctr": 0.002, "video_3s_rate": 0.04})

        self.assertEqual(classification["recommendation"], "NEEDS_RECUT")
        self.assertIn("first 3 seconds", classification["reason"])

    def test_classify_check_landing_page_for_high_ctr_low_registration(self):
        classification = classify_creative_performance({"total_spend": 40, "impressions": 5000, "ctr": 0.025, "registrations": 0, "deposits": 0})

        self.assertEqual(classification["recommendation"], "CHECK_LANDING_PAGE")

    def test_classify_scale_candidate_for_good_registration_and_deposit(self):
        classification = classify_creative_performance({"total_spend": 60, "impressions": 5000, "ctr": 0.025, "registrations": 8, "deposits": 2})

        self.assertEqual(classification["recommendation"], "SCALE_CANDIDATE")

    def test_build_performance_summary_identifies_best_and_actions(self):
        result = calculate_performance_metrics(parse_performance_csv(SAMPLE_CSV))
        summary = build_performance_summary(result)

        self.assertEqual(summary["total_creatives_matched"], 3)
        self.assertIn("best_creative_by_ctr", summary)
        self.assertIn("creatives_to_keep_testing", summary)
