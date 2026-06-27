import unittest

from content_factory.ai_provider import MockAIProvider
from content_factory.industry_templates import detect_industry_template


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


    def _official_concept_text(self, concept):
        official_fields = [
            "concept_name",
            "target_angle",
            "hook",
            "scene_breakdown",
            "15s_script",
            "voiceover",
            "visual_style",
            "runway_prompt",
            "elevenlabs_prompt",
            "facebook_primary_text",
            "facebook_headline",
            "facebook_description",
        ]
        parts = []
        for field in official_fields:
            value = concept[field]
            if isinstance(value, list):
                parts.extend(value)
            else:
                parts.append(value)
        parts.extend(concept["captions"])
        return " ".join(parts)

    def _assert_no_chinese_characters(self, text):
        self.assertNotRegex(text, r"[一-鿿]")

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
        self.assertIn("替代表达建议", result)

    def test_audit_ignores_forbidden_words_inside_rule_fields(self):
        product = dict(
            self.product,
            selling_points="到账快，界面清晰，新人活动",
            campaign_rules="规则说明：不得使用 guaranteed profit、risk-free、no loss 等表达。",
            forbidden_claims="guaranteed profit,risk-free,no loss",
            compliance_redlines="素材审核规则：禁止 guaranteed profit。",
        )
        demand = {"raw_input": "给巴西新用户做一条真实功能介绍广告", "structured": {}}
        materials = [
            {"grade": "必须人工补充的红线素材", "name": "真实logo", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实界面", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实活动规则", "compliant": 1},
        ]

        result = self.provider.audit_materials(product, demand, materials)

        self.assertEqual(result["status"], "PASS")

    def test_audit_blocks_forbidden_words_in_formal_demand_or_selling_points(self):
        materials = [
            {"grade": "必须人工补充的红线素材", "name": "真实logo", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实界面", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实活动规则", "compliant": 1},
        ]
        selling_point_result = self.provider.audit_materials(
            dict(self.product, selling_points="guaranteed profit for new users"),
            {"raw_input": "给巴西新用户做一条真实功能介绍广告", "structured": {}},
            materials,
        )
        demand_result = self.provider.audit_materials(
            self.product,
            {"raw_input": "Create a risk-free signup ad", "structured": {}},
            materials,
        )

        self.assertEqual(selling_point_result["status"], "FATAL_FAILED")
        self.assertIn("guaranteed profit", selling_point_result["risks"])
        self.assertEqual(demand_result["status"], "FATAL_FAILED")
        self.assertIn("risk-free", demand_result["risks"])

    def test_crypto_exchange_template_is_selected_from_industry(self):
        template = detect_industry_template(
            {"category": "crypto exchange", "name": "Spikex"},
            {"raw_input": "Facebook Brazil 15s", "structured": {}},
        )

        self.assertIsNotNone(template)
        self.assertEqual(template["name"], "Crypto Exchange / Trading V1")
        self.assertIn("AI copy trading discovery angle", template["approved_angles"])
        self.assertIn("negociação de criptomoedas", template["brazilian_portuguese_terms"].values())

    def test_generate_content_returns_upgraded_mock_outputs(self):
        result = self.provider.generate_content(self.product, self.demand, [], [], {"status": "PASS", "summary": "素材足够"})
        self.assertIn("campaign_summary", result)
        self.assertIn("video_ad_concepts", result)
        self.assertEqual(len(result["video_ad_concepts"]), 5)
        self.assertIn("scoring_report", result)
        self.assertIn("media_production_notes", result)
        self.assertIn("launch_plan", result)
        self.assertIn("forbidden_claims_check", result)
        for concept in result["video_ad_concepts"]:
            self.assertIn("runway_prompt", concept)
            self.assertIn("elevenlabs_prompt", concept)
            self.assertIn("facebook_primary_text", concept)
            self.assertIn("facebook_headline", concept)
            self.assertIn("facebook_description", concept)
            self.assertIn("15s_script", concept)
        self.assertEqual(result["scoring_report"]["total_score"], 90)

    def test_generate_content_uses_pt_br_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="bônus de cadastro, copy trading, início rápido")
        demand = {"raw_input": "Facebook Brasil 15s", "structured": {"语言": "pt-BR", "场景": "uso no celular", "目标": "cadastro"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        concept = result["video_ad_concepts"][0]
        official_text = " ".join([concept["hook"], concept["15s_script"], concept["voiceover"], concept["facebook_primary_text"], concept["runway_prompt"]])
        self.assertIn("Confira", official_text)
        self.assertIn("Comece", official_text)
        self.assertNotIn("真实", official_text)

    def test_generate_content_localizes_raw_english_points_for_pt_br(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="fast deposits, clean interface, new user campaign")
        demand = {
            "raw_input": "Facebook Brasil 15s",
            "structured": {
                "语言": "pt-BR",
                "人群": "Brazilian first-time crypto users aged 25-40",
                "场景": "uso no celular",
                "目标": "cadastro",
            },
        }
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        concept = result["video_ad_concepts"][0]
        official_text = " ".join(
            [
                result["campaign_summary"]["核心卖点"],
                concept["hook"],
                concept["15s_script"],
                concept["voiceover"],
                " ".join(concept["captions"]),
                concept["facebook_primary_text"],
            ]
        )

        self.assertEqual(result["campaign_summary"]["目标人群"], "Brazilian first-time crypto users aged 25-40")
        self.assertIn("Brazilian first-time crypto users aged 25-40", concept["target_angle"])
        self.assertNotIn("fast deposits, clean interface, new user campaign", official_text)
        self.assertIn("depósitos rápidos", official_text)

    def test_generate_content_localizes_spikex_points_for_pt_br_without_chinese_copy(self):
        product = dict(
            self.product,
            name="Spikex",
            category="crypto exchange",
            selling_points="AI copy trading, crypto and US stocks trading, fast onboarding, beginner-friendly trading experience",
        )
        demand = {
            "raw_input": "Facebook Brazil 15s",
            "structured": {
                "语言": "Brazilian Portuguese",
                "人群": "Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools",
                "场景": "mobile browsing",
                "目标": "signup",
            },
        }

        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        all_official_text = " ".join(self._official_concept_text(concept) for concept in result["video_ad_concepts"])

        self._assert_no_chinese_characters(all_official_text)
        self.assertIn("copy trading com IA", all_official_text)
        self.assertIn("criptomoedas", all_official_text)
        self.assertIn("ações dos EUA", all_official_text)
        self.assertIn("cadastro rápido", all_official_text)
        self.assertIn("experiência simples para iniciantes", all_official_text)

    def test_spikex_brazil_crypto_template_generates_exchange_specific_angles(self):
        product = dict(
            self.product,
            name="Spikex",
            category="crypto exchange",
            selling_points="AI copy trading, crypto trading, US stocks trading, fast onboarding, beginner-friendly trading experience",
            forbidden_claims="guaranteed profit, risk-free, no loss",
        )
        demand = {
            "raw_input": "Facebook Brazil 15s crypto exchange onboarding",
            "structured": {
                "语言": "pt-BR",
                "平台": "Facebook",
                "国家": "巴西",
                "人群": "Brazilian retail traders interested in crypto, stocks, copy trading and AI trading tools",
                "场景": "mobile browsing",
                "目标": "signup",
            },
        }

        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        official_text = " ".join(self._official_concept_text(concept) for concept in result["video_ad_concepts"])

        self.assertEqual(len(result["video_ad_concepts"]), 5)
        self._assert_no_chinese_characters(official_text)
        for expected in (
            "demonstração da plataforma",
            "copy trading com IA",
            "conteúdo educativo",
            "acesso ao mercado",
            "consciência de risco",
            "ferramentas de negociação",
        ):
            self.assertIn(expected, official_text)

    def test_crypto_high_risk_selling_point_blocks_generation(self):
        materials = [
            {"grade": "必须人工补充的红线素材", "name": "真实logo", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实界面", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实活动规则", "compliant": 1},
        ]
        product = dict(self.product, category="crypto exchange", selling_points="AI copy trading with profit promise")

        result = self.provider.audit_materials(
            product,
            {"raw_input": "Facebook Brazil 15s", "structured": {"语言": "pt-BR"}},
            materials,
        )

        self.assertEqual(result["status"], "FATAL_FAILED")
        self.assertIn("profit promise", result["risks"])

    def test_crypto_forbidden_claims_reference_does_not_block_by_itself(self):
        materials = [
            {"grade": "必须人工补充的红线素材", "name": "真实logo", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实界面", "compliant": 1},
            {"grade": "必须人工补充的红线素材", "name": "真实活动规则", "compliant": 1},
        ]
        product = dict(
            self.product,
            category="crypto exchange",
            selling_points="AI copy trading, trading tools, market access",
            campaign_rules="Review campaign rules and avoid financial freedom guaranteed wording.",
            forbidden_claims="financial freedom guaranteed, easy money, win every trade",
        )

        result = self.provider.audit_materials(
            product,
            {"raw_input": "Facebook Brazil 15s platform walkthrough", "structured": {"语言": "pt-BR"}},
            materials,
        )

        self.assertEqual(result["status"], "PASS")

    def test_non_chinese_official_mock_fields_do_not_contain_chinese_characters(self):
        cases = {
            "pt-BR": "copy trading com IA",
            "es": "copy trading con IA",
            "en": "AI copy trading",
        }
        for language, expected_phrase in cases.items():
            with self.subTest(language=language):
                product = dict(
                    self.product,
                    name="Spikex",
                    selling_points="AI copy trading, crypto and US stocks trading, fast onboarding, beginner-friendly trading experience",
                )
                demand = {
                    "raw_input": "Facebook Brazil 15s",
                    "structured": {
                        "语言": language,
                        "人群": "Brazilian retail traders interested in crypto",
                        "场景": "移动端浏览场景",
                        "目标": "注册转化",
                    },
                }

                result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
                official_text = " ".join(self._official_concept_text(concept) for concept in result["video_ad_concepts"])

                self._assert_no_chinese_characters(official_text)
                self.assertIn(expected_phrase, official_text)
                self.assertRegex(result["video_ad_concepts"][0]["compliance_notes"], r"[一-鿿]")

    def test_chinese_official_mock_fields_can_contain_chinese_characters(self):
        result = self.provider.generate_content(self.product, self.demand, [], [], {"status": "PASS"})
        official_text = self._official_concept_text(result["video_ad_concepts"][0])

        self.assertRegex(official_text, r"[一-鿿]")

    def test_campaign_rules_stay_out_of_official_ad_content(self):
        product = dict(
            self.product,
            name="CopyTrade Pro",
            campaign_rules="new users must complete KYC and trade 100 USDT before campaign eligibility",
        )
        demand = {"raw_input": "Facebook US 15s", "structured": {"语言": "en", "人群": "risk-aware beginners", "场景": "mobile browsing", "目标": "signup"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        rule_text = product["campaign_rules"]

        for concept in result["video_ad_concepts"]:
            official_text = " ".join(
                [
                    concept["15s_script"],
                    concept["voiceover"],
                    " ".join(concept["captions"]),
                    concept["facebook_primary_text"],
                ]
            )
            self.assertNotIn(rule_text, official_text)
            self.assertIn(rule_text, concept["compliance_notes"])

    def test_mock_prompts_carry_requested_voice_and_text_language(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="fast deposits, clean interface, new user campaign")
        expected = {
            "pt-BR": "voiceover, captions, on-screen text should be Brazilian Portuguese",
            "es": "voiceover, captions, on-screen text should be Spanish",
            "en": "voiceover, captions, on-screen text should be English",
        }
        for language, runway_instruction in expected.items():
            with self.subTest(language=language):
                demand = {"raw_input": "Facebook 15s", "structured": {"语言": language, "场景": "mobile browsing", "目标": "signup"}}
                result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
                concept = result["video_ad_concepts"][0]

                self.assertIn(runway_instruction, concept["runway_prompt"])
                self.assertIn(self.provider._language_label(language), concept["elevenlabs_prompt"])

    def test_generate_content_uses_spanish_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="bono de registro, copy trading, inicio rápido")
        demand = {"raw_input": "Facebook México 15s", "structured": {"语言": "es", "场景": "uso móvil", "目标": "registro"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        concept = result["video_ad_concepts"][0]
        official_text = " ".join([concept["hook"], concept["15s_script"], concept["voiceover"], concept["facebook_primary_text"], concept["elevenlabs_prompt"]])
        self.assertIn("Consulta", official_text)
        self.assertIn("Comienza", official_text)
        self.assertNotIn("真实", official_text)

    def test_generate_content_uses_english_when_requested(self):
        product = dict(self.product, name="CopyTrade Pro", selling_points="signup reward, copy trading, quick start")
        demand = {"raw_input": "Facebook US 15s", "structured": {"语言": "en", "场景": "mobile browsing", "目标": "signup"}}
        result = self.provider.generate_content(product, demand, [], [], {"status": "PASS"})
        concept = result["video_ad_concepts"][0]
        official_text = " ".join([concept["hook"], concept["15s_script"], concept["voiceover"], concept["facebook_primary_text"], concept["elevenlabs_prompt"]])
        self.assertIn("Check", official_text)
        self.assertIn("Get started", official_text)
        self.assertNotIn("真实", official_text)

    def test_evaluate_generation_returns_100_point_report(self):
        generation = self.provider.generate_content(self.product, self.demand, [], [], {"status": "PASS"})
        result = self.provider.evaluate_generation(self.product, self.demand, generation, {"status": "PASS"})
        self.assertGreaterEqual(result["总分"], 80)
        self.assertEqual(
            set(result["维度得分"].keys()),
            {"产品事实准确性", "真实性与红线素材", "场景与人群匹配", "脚本与分镜质量", "视频brief可执行性", "合规与风险", "复用价值"},
        )

    def test_analyze_performance_recommends_next_step(self):
        result = self.provider.analyze_performance({"素材方向": "注册转化"}, {"ctr": 0.8, "cpa": 20, "play_50": 200, "play_3s": 1000})
        self.assertIn("表现判断", result)
        self.assertIn("下一轮动作", result)
