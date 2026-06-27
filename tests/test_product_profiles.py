import unittest

from content_factory.product_profiles import (
    get_product_profile,
    list_product_profiles,
    profile_to_generation_request,
)


class ProductProfileTests(unittest.TestCase):
    def test_list_product_profiles_returns_spikex_brazil_profile(self):
        profiles = list_product_profiles()

        self.assertTrue(any(profile["profile_id"] == "spikex_brazil" for profile in profiles))
        spikex = next(profile for profile in profiles if profile["profile_id"] == "spikex_brazil")
        self.assertEqual(spikex["client_name"], "Spikex")
        self.assertEqual(spikex["product"], "Spikex")
        self.assertEqual(spikex["country"], "Brazil")

    def test_get_product_profile_returns_expected_fields(self):
        profile = get_product_profile("spikex_brazil")

        self.assertIsNotNone(profile)
        self.assertEqual(profile["industry"], "crypto exchange")
        self.assertEqual(profile["platform"], "Facebook Ads")
        self.assertEqual(profile["language"], "Brazilian Portuguese")
        self.assertIn("AI copy trading", profile["selling_points"])
        self.assertIn("Campaign rules are for compliance context only and should not be copied directly into ad scripts", profile["campaign_rules"])
        self.assertIn("Do not claim guaranteed results", profile["product_facts"])

    def test_get_product_profile_missing_returns_none(self):
        self.assertIsNone(get_product_profile("missing"))

    def test_profile_to_generation_request_returns_usable_generation_input(self):
        request = profile_to_generation_request("spikex_brazil")

        self.assertEqual(request["行业"], "crypto exchange")
        self.assertEqual(request["产品"], "Spikex")
        self.assertEqual(request["投放平台"], "Facebook Ads")
        self.assertEqual(request["国家"], "Brazil")
        self.assertEqual(request["语言"], "Brazilian Portuguese")
        self.assertIn("AI copy trading", request["卖点"])
        self.assertIn("guaranteed profit", request["限制词"])
        self.assertIn("Spikex is positioned as a trading platform", request["product_facts"])
        self.assertEqual(request["profile_id"], "spikex_brazil")
