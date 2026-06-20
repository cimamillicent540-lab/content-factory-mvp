import unittest

from content_factory.ai_provider import MockAIProvider
from content_factory.db import connect, init_db, loads_json
from content_factory.services import (
    get_generation_result,
    record_performance_feedback,
    run_content_pipeline,
)


class ServicePipelineTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.provider = MockAIProvider()

    def test_pipeline_generates_chinese_content_and_saves_records(self):
        request = {
            "行业": "金融工具",
            "产品": "测试钱包",
            "目标人群": "巴西新用户",
            "投放平台": "TikTok",
            "语言": "中文",
            "国家": "巴西",
            "卖点": "到账快，界面清晰，新人活动",
            "活动规则": "新人完成注册可参与活动",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "给TikTok巴西新用户做一条15秒注册转化素材，场景是下班后用手机",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

        result = run_content_pipeline(self.conn, self.provider, request)

        self.assertEqual(result["状态"], "GENERATED")
        self.assertIsNotNone(result["generation_id"])
        self.assertEqual(result["素材审核"]["status"], "PASS")
        self.assertIn("campaign_summary", result["素材内容"])
        self.assertEqual(len(result["素材内容"]["video_ad_concepts"]), 5)
        self.assertIn("总分", result["评分报告"])

        saved = get_generation_result(self.conn, result["generation_id"])
        self.assertEqual(saved["product"]["name"], "测试钱包")
        self.assertEqual(saved["audit"]["status"], "PASS")
        self.assertIn("15s_script", saved["generation"]["video_ad_concepts"][0])
        structured = loads_json(self.conn.execute("SELECT structured_json FROM demand_intakes").fetchone()["structured_json"])
        self.assertEqual(structured["平台"], "TikTok")
        self.assertEqual(structured["国家"], "巴西")
        self.assertEqual(structured["语言"], "中文")

    def test_pipeline_uses_requested_language_for_official_material_content(self):
        request = {
            "行业": "交易所",
            "产品": "CopyTrade Pro",
            "目标人群": "巴西新用户",
            "投放平台": "Facebook",
            "语言": "pt-BR",
            "国家": "巴西",
            "卖点": "bônus de cadastro, copy trading, início rápido",
            "活动规则": "novos usuários podem participar após o cadastro",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "给Facebook巴西新用户做一条15秒注册转化素材",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

        result = run_content_pipeline(self.conn, self.provider, request)
        content = result["素材内容"]

        self.assertEqual(result["状态"], "GENERATED")
        self.assertEqual(get_generation_result(self.conn, result["generation_id"])["demand"]["structured"]["语言"], "pt-BR")
        concept = content["video_ad_concepts"][0]
        self.assertIn("Confira", concept["hook"])
        self.assertIn("Comece", concept["facebook_primary_text"])
        self.assertNotIn("真实", concept["voiceover"])

    def test_pipeline_preserves_requested_audience_in_mock_generation(self):
        request = {
            "行业": "交易所",
            "产品": "CopyTrade Pro",
            "目标人群": "Brazilian first-time crypto users aged 25-40",
            "投放平台": "Facebook",
            "语言": "pt-BR",
            "国家": "巴西",
            "卖点": "fast deposits, clean interface, new user campaign",
            "活动规则": "new users must complete KYC before campaign eligibility",
            "限制词": "稳赚，保证收益，官方背书",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

        result = run_content_pipeline(self.conn, self.provider, request)
        content = result["素材内容"]
        concept = content["video_ad_concepts"][0]

        self.assertEqual(content["campaign_summary"]["目标人群"], "Brazilian first-time crypto users aged 25-40")
        self.assertIn("Brazilian first-time crypto users aged 25-40", concept["target_angle"])

    def test_blocked_pipeline_preserves_requested_audience_in_structured_demand(self):
        request = {
            "行业": "金融工具",
            "产品": "测试钱包",
            "目标人群": "Brazilian first-time crypto users aged 25-40",
            "投放平台": "TikTok",
            "语言": "中文",
            "国家": "巴西",
            "卖点": "到账快，界面清晰，新人活动",
            "活动规则": "新人完成注册可参与活动",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "做一条 guaranteed profit 广告",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

        result = run_content_pipeline(self.conn, self.provider, request)
        structured = loads_json(self.conn.execute("SELECT structured_json FROM demand_intakes").fetchone()["structured_json"])

        self.assertEqual(result["状态"], "BLOCKED")
        self.assertEqual(result["结构化需求"]["人群"], "Brazilian first-time crypto users aged 25-40")
        self.assertEqual(structured["人群"], "Brazilian first-time crypto users aged 25-40")

    def test_pipeline_saves_block_reason_without_generation_when_redline_hit(self):
        request = {
            "行业": "金融工具",
            "产品": "测试钱包",
            "目标人群": "巴西新用户",
            "投放平台": "TikTok",
            "语言": "中文",
            "国家": "巴西",
            "卖点": "到账快，界面清晰，新人活动",
            "活动规则": "新人完成注册可参与活动",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "做一条保证收益稳赚的广告",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }

        result = run_content_pipeline(self.conn, self.provider, request)

        self.assertEqual(result["状态"], "BLOCKED")
        self.assertIsNone(result["generation_id"])
        self.assertEqual(result["素材审核"]["status"], "FATAL_FAILED")
        self.assertIn("保证收益", " ".join(result["阻断原因"]))
        self.assertNotIn("素材内容", result)
        self.assertIn("替代表达建议", result["素材审核"])
        count = self.conn.execute("SELECT COUNT(*) AS count FROM content_generations").fetchone()["count"]
        self.assertEqual(count, 0)

    def test_performance_feedback_is_saved_and_readable(self):
        request = {
            "行业": "金融工具",
            "产品": "测试钱包",
            "目标人群": "巴西新用户",
            "投放平台": "TikTok",
            "语言": "中文",
            "国家": "巴西",
            "卖点": "到账快，界面清晰，新人活动",
            "活动规则": "新人完成注册可参与活动",
            "限制词": "稳赚，保证收益，官方背书",
            "需求": "给TikTok巴西新用户做一条15秒注册转化素材",
            "素材": [
                {"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实界面", "grade": "必须人工补充的红线素材", "compliant": 1},
                {"name": "真实活动规则", "grade": "必须人工补充的红线素材", "compliant": 1},
            ],
        }
        pipeline = run_content_pipeline(self.conn, self.provider, request)

        feedback = record_performance_feedback(
            self.conn,
            self.provider,
            pipeline["generation_id"],
            {"ctr": 0.8, "cpa": 20, "play_3s": 1000, "play_50": 200},
        )

        self.assertIn("表现判断", feedback["投放分析建议"])
        saved = get_generation_result(self.conn, pipeline["generation_id"])
        self.assertEqual(len(saved["performance_logs"]), 1)
        self.assertIn("下一轮动作", saved["performance_logs"][0]["analysis"])
