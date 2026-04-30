import unittest

from server import extract_text, map_language, mime_type_to_suffix


class FunASRAdapterHelpersTest(unittest.TestCase):
    def test_mime_type_to_suffix(self):
        self.assertEqual(mime_type_to_suffix("audio/wav"), ".wav")
        self.assertEqual(mime_type_to_suffix("audio/m4a"), ".m4a")
        self.assertEqual(mime_type_to_suffix("audio/webm"), ".webm")
        self.assertEqual(mime_type_to_suffix("application/octet-stream"), ".wav")

    def test_map_language(self):
        self.assertEqual(map_language("zh-CN"), "中文")
        self.assertEqual(map_language("en-US"), "英文")
        self.assertEqual(map_language("zh-HK"), "中文")
        self.assertEqual(map_language("auto"), "")
        self.assertEqual(map_language(""), "")

    def test_extract_text(self):
        self.assertEqual(extract_text({"text": "hello"}), "hello")
        self.assertEqual(extract_text([{"text": "hello"}]), "hello")
        self.assertEqual(extract_text([{"foo": "bar"}, {"text": " world "}]), "world")
        self.assertEqual(extract_text({"foo": "bar"}), "")


if __name__ == "__main__":
    unittest.main()
