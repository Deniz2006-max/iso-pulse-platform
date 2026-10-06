from __future__ import annotations

import unittest

from config.llm import (
    OPENAI_KEY_HINT,
    MissingOpenAIKeyError,
    llm_runtime_label,
    openai_key_configured,
    require_openai_api_key,
)
from config.settings import _resolve_chat_model


class OpenAIConfigTests(unittest.TestCase):
    def test_missing_key_raises_clear_message(self):
        with self.assertRaises(MissingOpenAIKeyError) as ctx:
            require_openai_api_key("")
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))
        self.assertIn(".env", str(ctx.exception))
        self.assertIn("OPENAI_API_KEY", OPENAI_KEY_HINT)

    def test_empty_key_is_not_configured(self):
        self.assertFalse(openai_key_configured("  "))
        self.assertTrue(openai_key_configured("sk-test"))

    def test_runtime_label_openai(self):
        self.assertEqual(llm_runtime_label(mock=True), "mock (fast)")
        self.assertIn("ChatOpenAI", llm_runtime_label(mock=False))


class ModelResolveTests(unittest.TestCase):
    def test_ollama_tag_falls_back_to_mini(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"MODEL_NAME": "qwen2.5:7b", "ISO_PULSE_MODEL": "", "OPENAI_MODEL": ""}, clear=False):
            os.environ.pop("ISO_PULSE_MODEL", None)
            os.environ.pop("OPENAI_MODEL", None)
            os.environ["MODEL_NAME"] = "qwen2.5:7b"
            self.assertEqual(_resolve_chat_model(), "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
