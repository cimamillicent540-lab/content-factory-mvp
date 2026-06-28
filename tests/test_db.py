import unittest

from content_factory.db import connect, init_db, table_names


class DatabaseTests(unittest.TestCase):
    def test_init_db_creates_required_tables(self):
        conn = connect(":memory:")
        init_db(conn)
        expected = {
            "products",
            "product_facts",
            "product_assets",
            "demand_intakes",
            "benchmark_videos",
            "benchmark_deconstructions",
            "material_assets",
            "content_generations",
            "material_audits",
            "evaluation_reports",
            "ad_performance_logs",
            "performance_reports",
            "reusable_patterns",
        }
        self.assertTrue(expected.issubset(table_names(conn)))

    def test_products_can_be_inserted_with_timestamps(self):
        conn = connect(":memory:")
        init_db(conn)
        conn.execute(
            """
            INSERT INTO products
            (name, product_url, country, category, platform, selling_points, campaign_rules, forbidden_claims, compliance_redlines, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "测试产品",
                "https://example.com",
                "巴西",
                "工具",
                "TikTok",
                "快",
                "首单优惠",
                "绝对第一",
                "不得虚构收益",
                "备注",
            ),
        )
        row = conn.execute("SELECT id, name, created_at, updated_at FROM products").fetchone()
        self.assertEqual(row["name"], "测试产品")
        self.assertIsNotNone(row["created_at"])
        self.assertIsNotNone(row["updated_at"])
