import unittest

from content_factory.ai_provider import MockAIProvider, OpenAIProvider
from content_factory.provider_factory import ProviderConfigurationError, create_provider


class ProviderFactoryTests(unittest.TestCase):
    def test_default_provider_is_mock(self):
        self.assertIsInstance(create_provider({}), MockAIProvider)

    def test_mock_provider_can_be_selected_explicitly(self):
        self.assertIsInstance(create_provider({"CONTENT_FACTORY_PROVIDER": "mock"}), MockAIProvider)

    def test_openai_provider_requires_api_key(self):
        with self.assertRaisesRegex(ProviderConfigurationError, "OPENAI_API_KEY"):
            create_provider({"CONTENT_FACTORY_PROVIDER": "openai"})

    def test_openai_provider_uses_environment_model(self):
        provider = create_provider(
            {
                "CONTENT_FACTORY_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "gpt-test",
            },
            client=object(),
        )
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.model, "gpt-test")
