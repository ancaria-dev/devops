import unittest

import semver


class SemverTest(unittest.TestCase):
    def test_valid(self):
        for v in ["0.0.1", "1.2.3", "v1.2.3", "1.0.0-rc.1", "1.0.0-alpha.beta-2"]:
            self.assertTrue(semver.is_valid(v), v)
        for v in ["1.2", "01.2.3", "1.2.3.4", "1.2.3-", "1.2.3-01", "x", ""]:
            self.assertFalse(semver.is_valid(v), v)

    def test_normalize(self):
        self.assertEqual(semver.normalize("v2.1.0"), "2.1.0")
        with self.assertRaises(ValueError):
            semver.normalize("2.1")

    def test_order(self):
        ordered = ["0.9.9", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                   "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.10.0"]
        for a, b in zip(ordered, ordered[1:]):
            self.assertEqual(semver.compare(a, b), -1, (a, b))
            self.assertEqual(semver.compare(b, a), 1, (b, a))
        self.assertEqual(semver.compare("v1.0.0", "1.0.0"), 0)

    def test_highest_and_previous(self):
        tags = ["0.200.0", "0.99.0", "1.0.0-rc.1", "junk"]
        self.assertEqual(semver.highest(tags), "1.0.0-rc.1")
        self.assertEqual(semver.highest(tags + ["1.0.0"]), "1.0.0")
        self.assertIsNone(semver.highest(["junk"]))
        self.assertEqual(semver.previous(tags, "1.0.0-rc.1"), "0.200.0")
        self.assertEqual(semver.previous(tags, "0.200.0"), "0.99.0")
        self.assertIsNone(semver.previous(tags, "0.1.0"))

    def test_next_patch(self):
        self.assertEqual(semver.next_patch("0.200.0"), "0.200.1")
        self.assertEqual(semver.next_patch("1.3.0-rc.1"), "1.3.0")

    def test_cli(self):
        self.assertEqual(semver._main(["lt", "1.0.0-rc.1", "1.0.0"]), 0)
        self.assertEqual(semver._main(["lt", "1.0.0", "1.0.0"]), 1)
        self.assertEqual(semver._main(["check", "1.2"]), 1)


if __name__ == "__main__":
    unittest.main()
