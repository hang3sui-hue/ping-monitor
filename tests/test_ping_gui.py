import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import ping_gui


class PingLogicTests(unittest.TestCase):
    def test_both_languages_have_the_same_keys(self):
        self.assertTrue(all(len(pair) == 2 and all(pair) for pair in ping_gui.WORDS.values()))

    def test_numeric_fields_reject_letters(self):
        self.assertTrue(ping_gui.digits_only(""))
        self.assertTrue(ping_gui.digits_only("1000"))
        self.assertFalse(ping_gui.digits_only("10a"))
        self.assertFalse(ping_gui.digits_only("100000"))

    def test_host_requires_a_name_or_ip_not_a_url(self):
        self.assertTrue(ping_gui.valid_host("google.com"))
        self.assertTrue(ping_gui.valid_host("127.0.0.1"))
        self.assertFalse(ping_gui.valid_host("https://google.com"))
        self.assertFalse(ping_gui.valid_host("-t"))

    def test_latency_parser_handles_english_and_chinese(self):
        self.assertEqual(ping_gui.parse_latency("Reply: time=12ms TTL=128"), 12)
        self.assertEqual(ping_gui.parse_latency("回复: 时间<1ms TTL=128"), 0.5)
        self.assertIsNone(ping_gui.parse_latency("Request timed out."))

    def test_no_reply_is_not_counted_as_success(self):
        self.assertEqual(ping_gui.ping_result(0, "Destination host unreachable."), (False, None))
        self.assertEqual(ping_gui.ping_result(1, "Reply: time=12ms TTL=128"), (False, None))
        self.assertEqual(ping_gui.ping_result(0, "Reply: time=12ms TTL=128"), (True, 12))

    def test_last_target_is_saved_and_loaded(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path = Path(folder) / "settings.json"
            with patch.object(ping_gui, "settings_file", return_value=path):
                self.assertEqual(ping_gui.load_last_host(), "")
                ping_gui.save_last_host("bing.com")
                self.assertEqual(ping_gui.load_last_host(), "bing.com")


if __name__ == "__main__":
    unittest.main()
