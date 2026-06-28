import unittest

from content_factory.creative_workflow import (
    attach_creative_ids,
    build_country_code,
    build_creative_id,
    build_media_buyer_launch_brief,
    build_platform_code,
    build_product_code,
)


class CreativeWorkflowTests(unittest.TestCase):
    def test_build_creative_id_for_spikex_brazil_facebook(self):
        creative_id = build_creative_id(
            product="Spikex",
            country="Brazil",
            platform="Facebook Ads",
            date="2026-06-28",
            concept_index=1,
        )

        self.assertEqual(creative_id, "SPK-BR-FB-20260628-C001")

    def test_creative_id_generation_is_deterministic(self):
        first = build_creative_id("Spikex", "Brazil", "Facebook Ads", "2026-06-28", 3)
        second = build_creative_id("Spikex", "Brazil", "Facebook Ads", "2026-06-28", 3)

        self.assertEqual(first, second)
        self.assertEqual(first, "SPK-BR-FB-20260628-C003")

    def test_unknown_codes_have_safe_fallbacks(self):
        self.assertEqual(build_product_code("New Product 9"), "NEW")
        self.assertEqual(build_product_code("产品"), "XXX")
        self.assertEqual(build_country_code("Mexico"), "ME")
        self.assertEqual(build_platform_code("Pinterest"), "PI")

    def test_attach_creative_ids_adds_derived_ids_without_mutating_provider_shape(self):
        concepts = [{"concept_id": "C01", "concept_name": "Concept 1"}, {"concept_id": "C02", "concept_name": "Concept 2"}]
        result = attach_creative_ids(
            concepts,
            product="Spikex",
            country="Brazil",
            platform="Facebook Ads",
            date="2026-06-28",
        )

        self.assertEqual(result[0]["creative_id"], "SPK-BR-FB-20260628-C001")
        self.assertEqual(result[1]["creative_id"], "SPK-BR-FB-20260628-C002")
        self.assertNotIn("creative_id", concepts[0])

    def test_media_buyer_launch_brief_contains_internal_launch_fields(self):
        concepts = attach_creative_ids(
            [
                {
                    "concept_id": "C01",
                    "concept_name": "Demonstração da plataforma",
                    "target_angle": "risk-aware platform walkthrough",
                    "hook": "Veja como funciona antes de começar.",
                }
            ],
            product="Spikex",
            country="Brazil",
            platform="Facebook Ads",
            date="2026-06-28",
        )

        brief = build_media_buyer_launch_brief(
            {
                "product": "Spikex",
                "profile_id": "spikex_brazil",
                "platform": "Facebook Ads",
                "country": "Brazil",
                "language": "Brazilian Portuguese",
                "audience": "Brazilian retail traders",
                "campaign_rules": "Use risk-aware language",
            },
            concepts,
        )

        self.assertIn("Media Buyer Launch Brief", brief)
        self.assertIn("SPK-BR-FB-20260628-C001", brief)
        self.assertIn("target_angle", brief)
        self.assertIn("hook", brief)
        self.assertIn("primary metric to watch", brief)
        self.assertIn("Confirm product facts", brief)
        self.assertIn("Decision Rules", brief)
        self.assertNotIn("稳赚", brief)
