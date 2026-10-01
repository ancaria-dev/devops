import unittest

import cloc


class ShortTest(unittest.TestCase):
    def test_short(self):
        cases = {0: "0", 950: "950", 999: "999", 1000: "1k", 1049: "1k", 1050: "1.1k", 12345: "12.3k",
                 12000: "12k", 999949: "999.9k", 999950: "1M", 1234567: "1.2M", 10_000_000: "10M"}
        for n, text in cases.items():
            self.assertEqual(cloc.short(n), text, n)

    def test_badge(self):
        self.assertEqual(cloc.badge(12345),
                         {"schemaVersion": 1, "label": "lines of code", "message": "12.3k", "color": "blue"})


if __name__ == "__main__":
    unittest.main()
