"""Tests for the public text normalization helpers."""

from __future__ import annotations

import unittest

from my_toolkit import text as text_mod


class TestNormalizeText(unittest.TestCase):
    def test_normalize_text_is_public_and_normalize_remains_compatible(self):
        value = "  Hello,\n\tworld!  "

        self.assertEqual(text_mod.normalize_text(value), "Hello, world!")
        self.assertIs(text_mod.normalize, text_mod.normalize_text)
        self.assertEqual(text_mod.normalize(None), "")


class TestExtractHashtag(unittest.TestCase):
    def test_deduplication_preserves_first_seen_order(self):
        value = "#first #second #first #中文 #second #third"

        self.assertEqual(
            text_mod.extract_hashtag(value),
            ["first", "second", "中文", "third"],
        )
        self.assertEqual(
            text_mod.extract_hashtag(value, remove_duplicates=False),
            ["first", "second", "first", "中文", "second", "third"],
        )


class TestRemoveEmojiAndHashtag(unittest.TestCase):
    def test_removes_flags_variation_selectors_and_zwj_sequences(self):
        value = "出发 🇨🇳 ❤️ 👨‍👩‍👧‍👦 ✈️ #旅行 保留文字"

        cleaned = text_mod.remove_emoji_and_hashtag(value)

        self.assertEqual(text_mod.normalize_text(cleaned), "出发 保留文字")
        for residual in ("🇨", "🇳", "\ufe0f", "\u200d", "#旅行"):
            with self.subTest(residual=residual):
                self.assertNotIn(residual, cleaned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
