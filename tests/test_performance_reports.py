import unittest

from content_factory.db import connect, init_db
from content_factory.performance_reports import (
    get_performance_report,
    list_performance_reports,
    save_performance_report,
)


SAMPLE_CSV = """creative_id,spend,impressions,clicks,link_clicks,registrations,deposits,video_3s_views,video_50_views,video_95_views
SPK-BR-FB-20260628-C001,30,5000,80,65,5,1,1200,500,220
SPK-BR-FB-20260628-C002,25,4500,35,28,1,0,600,180,60
"""


class PerformanceReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)

    def test_save_performance_report_persists_analysis_payload(self):
        report = save_performance_report(self.conn, SAMPLE_CSV)

        self.assertTrue(report["report_id"].startswith("perf-"))
        self.assertIn("created_at", report)
        self.assertEqual(report["summary"]["total_creatives_matched"], 2)
        self.assertIn("SPK-BR-FB-20260628-C001", report["aggregated"]["creatives"])
        self.assertIn("# Performance Summary", report["summary_markdown"])
        self.assertIn("raw_csv_preview", report)

    def test_list_performance_reports_returns_recent_report_cards(self):
        saved = save_performance_report(self.conn, SAMPLE_CSV)

        reports = list_performance_reports(self.conn)

        self.assertEqual(reports[0]["report_id"], saved["report_id"])
        self.assertEqual(reports[0]["matched_creative_count"], 2)
        self.assertEqual(reports[0]["unmatched_row_count"], 0)
        self.assertIn("scale_candidate_count", reports[0])

    def test_get_performance_report_returns_full_saved_payload(self):
        saved = save_performance_report(self.conn, SAMPLE_CSV)

        report = get_performance_report(self.conn, saved["report_id"])

        self.assertEqual(report["report_id"], saved["report_id"])
        self.assertEqual(report["raw_csv_text"], SAMPLE_CSV)
        self.assertIn("internal_action_notes", report["summary"])

    def test_get_missing_report_returns_none(self):
        self.assertIsNone(get_performance_report(self.conn, "perf-missing"))
