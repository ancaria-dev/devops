import unittest

import train

GRAPH = {
    "repos": ["mappings", "agent", "coderpack", "protocol", "build", "idea", "launcher"],
    "edges": [
        {"from": "mappings", "to": "agent", "input": "mappings"},
        {"from": "coderpack", "to": "build", "input": "api", "paths": ["api/**", "api-kotlin/**"]},
        {"from": "build", "to": "idea", "input": "templates"},
    ],
}


def run(graph, explicit=None, released=None, propagate=True, own=None):
    asked = []

    def propagates(edge, version):
        asked.append((edge["from"], edge["to"], version))
        return propagate

    steps = list(train.walk(graph, explicit or {}, released, propagates, lambda r: (own or {}).get(r, "9.9.9")))
    return steps, asked


class GraphTest(unittest.TestCase):
    def test_topo_order_keeps_repo_order(self):
        self.assertEqual(train.topo_order(GRAPH),
                         ["mappings", "agent", "coderpack", "protocol", "build", "idea", "launcher"])

    def test_upstream_listed_later_still_comes_first(self):
        graph = {"repos": ["b", "a"], "edges": [{"from": "a", "to": "b"}]}
        self.assertEqual(train.topo_order(graph), ["a", "b"])

    def test_cycle(self):
        graph = {"repos": ["a", "b"], "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]}
        with self.assertRaises(train.Failure):
            train.topo_order(graph)

    def test_unknown_edge_end(self):
        with self.assertRaises(train.Failure):
            train.validate_graph({"repos": ["a"], "edges": [{"from": "a", "to": "zzz"}]})

    def test_real_graph_loads(self):
        graph = train.load_graph()
        self.assertIn("coderpack", graph["repos"])
        self.assertIn("api", graph["meta"]["components"])


class GlobTest(unittest.TestCase):
    def test_double_star(self):
        self.assertTrue(train.matches_any("api/src/main/Api.java", ["api/**"]))
        self.assertTrue(train.matches_any("api-kotlin/build.gradle.kts", ["api/**", "api-kotlin/**"]))
        self.assertFalse(train.matches_any("api-compose/x.kt", ["api/**"]))
        self.assertFalse(train.matches_any("zygote/api/x.java", ["api/**"]))
        self.assertTrue(train.matches_any("zygote/api/x.java", ["**/api/**"]))
        self.assertTrue(train.matches_any("api/x.java", ["**/api/**"]))
        self.assertTrue(train.matches_any("README.md", ["*.md"]))
        self.assertFalse(train.matches_any("docs/README.md", ["*.md"]))


class ParseTest(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(train.parse_versions("coderpack=2.1.0 protocol=v2.0.1", GRAPH["repos"]),
                         {"coderpack": "2.1.0", "protocol": "2.0.1"})
        everything = train.parse_versions("all=2.0.0, idea=2.0.1", GRAPH["repos"])
        self.assertEqual(len(everything), len(GRAPH["repos"]))
        self.assertEqual(everything["idea"], "2.0.1")
        self.assertEqual(train.parse_versions("idea=2.0.1 all=2.0.0", GRAPH["repos"])["idea"], "2.0.1")
        self.assertEqual(train.parse_versions("", GRAPH["repos"]), {})
        for bad in ["coderpack", "coderpack=2.1", "nope=1.0.0"]:
            with self.assertRaises(train.Failure, msg=bad):
                train.parse_versions(bad, GRAPH["repos"])

    def test_released(self):
        self.assertEqual(train.parse_released("mappings@v1.2.3"), ("mappings", "1.2.3"))
        self.assertIsNone(train.parse_released(""))
        with self.assertRaises(train.Failure):
            train.parse_released("mappings")

    def test_run_title(self):
        runs = [{"displayTitle": "Release 1.0.1 · train 1234"}, {"displayTitle": "Release 1.0.2 · train 123"}]
        self.assertEqual(train.train_run_version(runs, "123"), "1.0.2")
        self.assertIsNone(train.train_run_version(runs, "12"))


class WalkTest(unittest.TestCase):
    def test_released_upstream_cascades(self):
        steps, _ = run(GRAPH, released=("mappings", "1.1.0"), own={"agent": "0.3.1"})
        self.assertEqual([(s.repo, s.version, s.inputs) for s in steps],
                         [("agent", "0.3.1", {"mappings": "1.1.0"})])

    def test_paths_stop_propagation(self):
        steps, asked = run(GRAPH, explicit={"coderpack": "2.1.0"}, propagate=False)
        self.assertEqual([s.repo for s in steps], ["coderpack"])
        self.assertEqual(asked, [("coderpack", "build", "2.1.0")])

    def test_chain_passes_inputs(self):
        steps, _ = run(GRAPH, explicit={"coderpack": "2.1.0"}, own={"build": "2.0.5", "idea": "2.0.7"})
        self.assertEqual([(s.repo, s.version, s.inputs) for s in steps], [
            ("coderpack", "2.1.0", {}),
            ("build", "2.0.5", {"api": "2.1.0"}),
            ("idea", "2.0.7", {"templates": "2.0.5"}),
        ])

    def test_explicit_wins_over_bump_and_keeps_order(self):
        steps, _ = run(GRAPH, explicit={"idea": "3.0.0", "coderpack": "2.1.0", "build": "2.2.0"})
        self.assertEqual([(s.repo, s.version) for s in steps],
                         [("coderpack", "2.1.0"), ("build", "2.2.0"), ("idea", "3.0.0")])
        self.assertEqual(steps[1].inputs, {"api": "2.1.0"})
        self.assertEqual(steps[2].reason, "requested")

    def test_once_after_all_upstreams(self):
        graph = {"repos": ["a", "b", "c"], "edges": [{"from": "a", "to": "c", "input": "a"},
                                                     {"from": "b", "to": "c", "input": "b"}]}
        steps, _ = run(graph, explicit={"a": "1.0.0", "b": "2.0.0"}, own={"c": "0.1.1"})
        self.assertEqual([s.repo for s in steps], ["a", "b", "c"])
        self.assertEqual(steps[2].inputs, {"a": "1.0.0", "b": "2.0.0"})

    def test_lazy(self):
        order = []

        def propagates(edge, version):
            order.append("ask " + edge["to"])
            return True

        for step in train.walk(GRAPH, {"coderpack": "2.1.0"}, None, propagates, lambda r: "1.0.0"):
            order.append("release " + step.repo)
        self.assertEqual(order, ["release coderpack", "ask build", "release build", "ask idea", "release idea"])

    def test_nothing(self):
        self.assertEqual(run(GRAPH)[0], [])
        self.assertEqual(run(GRAPH, released=("launcher", "1.0.0"))[0], [])


class PreviewTest(unittest.TestCase):
    def test_rows(self):
        rows = train.preview(GRAPH, {"coderpack": "2.1.0"}, ("mappings", "1.0.0"))
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [("mappings", "released"), ("agent", "release"), ("coderpack", "release"),
                          ("build", "maybe"), ("idea", "maybe")])


if __name__ == "__main__":
    unittest.main()
