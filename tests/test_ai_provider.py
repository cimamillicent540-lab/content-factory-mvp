import unittest

from content_factory.ai_provider import MockAIProvider


class MockAIProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockAIProvider()
        self.product = {
            "name": "测试钱包",
            "country": "巴西",
            "platform": "TikTok",
            "selling_points": "到账快，界面清晰，新人活动",
            "campaign_rules": "新人完成注册可参与活动",
            "forbidden_claims": "稳赚，保证收益，官方背书",
            "compliance_redlines": "必须使用真实logo、真实界面、真实活动规则",
        }
        self.demand = {
            "raw_input": "给巴西新用户做一条15秒注册转化素材，场景是下班后用手机",
            "structured": {
                "平台": "TikTok",
                "国家": "巴西",
                "人群": "新用户",
                "场景": "下班后用手机",
                "目标": "注册转化",
                "时长": "15秒",
                "输出物": ["脚本", "分镜", "广告文案"],
                "缺失信息": [],
            },
        }

    def test_structure_demand_returns_chinese_fields(self):
        result = self.provider.structure_demand("给TikTok巴西用户做15秒注册广告", self.product)
        self.assertEqual(result["平台"], "TikTok")
        self.assertEqual(result["国家"], "巴西")
        self.assertIn("人群", result)
        self.assertIn("缺失信息", result)
        self.assertIsInstance(result["输出物"], list)

    def test_audit_requires_human_when_redline_material_is_missing(self):
        result = self.provider.audit_materials(self.product, self.demand, [])
        self.assertEqual(result["status"], "HUMAN_REQUIRED")
        self.assertIn("真实logo", " ".join(result["missing_materials"]))

    def test_audit_fails_when_demand_contains_forbidden_claim(self):
        demand = {"raw_input": "做一条保证收益稳赚的广告", "structured": {}}
        materials = [{"grade": "必须人工补充的红线素材", "name": "真实logo", "compliant": 1}]
        result = self.provider.audit_materials(self.product, demand, materials)
        self.assertEqual(result["status"], "FATAL_FAILED")
        self.assertIn("保证收益", " ".join(result["risks"]))

    def test_generate_content_returns_required_chinese_outputs(self):
        audit = {"status": "PASS", "summary": "素材足够"}
        materials = [{"name": "真实logo", "grade": "必须人工补充的红线素材", "compliant": 1}]
        result = self.provider.generate_content(self.product, self.demand, materials, [], audit)
        self.assertIn("素材方向", result)
        self.assertIn("10秒脚本", result["脚本"])
        self.assertIn("15秒脚本", result["脚本"])
        self.assertIn("30秒脚本", result["脚本"])
        self.assertIn("Runway Prompt", result)
        self.assertIn("HeyGen Prompt", result)
        self.assertIn("ElevenLabs Prompt", result)
        self.assertIn("Facebook广告文案", result)
        self.assertIn("TikTok广告文案", result)

    def test_generate_content_uses_pt_br_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="bônus de cadastro, copy trading, início rápido")
        demand = {"raw_input": "Facebook Brasil 15s", "structured": {"语言": "pt-BR", "场景": "uso no celular", "目标": "cadastro"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        official_text = " ".join([result["旁白"], result["脚本"]["15秒脚本"], result["Facebook广告文案"], result["Runway Prompt"]])
        self.assertIn("Confira", official_text)
        self.assertIn("Comece", official_text)
        self.assertNotIn("真实", official_text)

    def test_generate_content_uses_spanish_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="bono de registro, copy trading, inicio rápido")
        demand = {"raw_input": "Facebook México 15s", "structured": {"语言": "es", "场景": "uso móvil", "目标": "registro"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        official_text = " ".join([result["旁白"], result["脚本"]["15秒脚本"], result["TikTok广告文案"], result["HeyGen Prompt"]])
        self.assertIn("Consulta", official_text)
        self.assertIn("Comienza", official_text)
        self.assertNotIn("真实", official_text)

    def test_generate_content_uses_english_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="signup reward, copy trading, quick start")
        demand = {"raw_input": "Facebook US 15s", "structured": {"语言": "en", "场景": "mobile browsing", "目标": "signup"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        official_text = " ".join([result["旁白"], result["脚本"]["15秒脚本"], result["Facebook广告文案"], result["ElevenLabs Prompt"]])
        self.assertIn("Check", official_text)
        self.assertIn("Get started", official_text)
        self.assertNotIn("真实", official_text)

    def test_evaluate_generation_returns_100_point_report(self):
        generation = self.provider.generate_content(self.product, self.demand, [], [], {"status": "PASS"})
        result = self.provider.evaluate_generation(self.product, self.demand, generation, {"status": "PASS"})
        self.assertGreaterEqual(result["总分"], 80)
        self.assertEqual(
            set(result["维度得分"].keys()),
            {
                "产品事实准确性",
                "真实性与红线素材",
                "场景与人群匹配",
                "脚本与分镜质量",
                "视频brief可执行性",
                "合规与风险",
                "复用价值",
            },
        )

    def test_analyze_performance_recommends_next_step(self):
        result = self.provider.analyze_performance(
            {"素材方向": "注册转化"},
            {"ctr": 0.8, "cpa": 20, "play_50": 200, "play_3s": 1000},
        )
        self.assertIn("表现判断", result)
        self.assertIn("下一轮动作", result)
