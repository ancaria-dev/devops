#!/usr/bin/env python3
"""Releases ancaria-dev repositories in dependency order (graph.yml).

Every repository named in --versions is released at that version. Then every
repository downstream of a released one is released at its own highest tag plus
a patch, once all its released upstreams are done, when an edge's `paths` match
a file that changed between the upstream's previous tag and its new one.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import semver  # noqa: E402

ORG = "ancaria-dev"
GRAPH = Path(__file__).resolve().parent.parent / "graph.yml"
FIND_RUN_SECONDS = 120


class Failure(Exception):
    pass


@dataclass
class Step:
    repo: str
    version: str
    reason: str
    inputs: dict = field(default_factory=dict)


def log(emoji, text):
    print(f"{emoji} {text}", flush=True)


# ---------------------------------------------------------------- graph

def load_graph(path=GRAPH):
    import yaml

    with open(path, encoding="utf-8") as f:
        graph = yaml.safe_load(f)
    validate_graph(graph)
    return graph


def validate_graph(graph):
    repos = graph.get("repos") or []
    if len(set(repos)) != len(repos):
        raise Failure("graph.yml lists a repository twice")
    for edge in graph.get("edges") or []:
        for end in ("from", "to"):
            if edge.get(end) not in repos:
                raise Failure(f"graph.yml edge {edge} names {edge.get(end)!r}, which is not in repos")
    topo_order(graph)


def topo_order(graph):
    """Repositories with every upstream first; ties keep the order of `repos`."""
    repos = list(graph.get("repos") or [])
    edges = graph.get("edges") or []
    indegree = {r: 0 for r in repos}
    for e in edges:
        indegree[e["to"]] += 1
    order = []
    ready = [r for r in repos if indegree[r] == 0]
    while ready:
        repo = ready.pop(0)
        order.append(repo)
        for e in edges:
            if e["from"] == repo:
                indegree[e["to"]] -= 1
                if indegree[e["to"]] == 0:
                    ready.append(e["to"])
        ready.sort(key=repos.index)
    if len(order) != len(repos):
        raise Failure("graph.yml has a cycle among: " + ", ".join(r for r in repos if r not in order))
    return order


def glob_regex(pattern):
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        out.append({"*": "[^/]*", "?": "[^/]"}.get(c, re.escape(c)))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches_any(path, patterns):
    return any(glob_regex(p).match(path) for p in patterns)


def parse_versions(text, repos):
    """'coderpack=2.1.0 protocol=2.0.1' or 'all=2.0.0' -> {repo: version}."""
    explicit = {}
    for item in re.split(r"[\s,]+", (text or "").strip()):
        if not item:
            continue
        name, sep, version = item.partition("=")
        if not sep:
            raise Failure(f"--versions: expected repo=version, got {item!r}")
        version = semver.normalize(version) if semver.is_valid(version) else None
        if version is None:
            raise Failure(f"--versions: {item!r} is not MAJOR.MINOR.PATCH[-pre]")
        if name == "all":
            explicit.update({r: version for r in repos if r not in explicit})
        elif name in repos:
            explicit[name] = version
        else:
            raise Failure(f"--versions: {name!r} is not in graph.yml (repos: {', '.join(repos)})")
    return explicit


def parse_released(text):
    if not text:
        return None
    repo, sep, version = text.partition("@")
    if not sep or not repo or not semver.is_valid(version):
        raise Failure(f"--released: expected repo@version, got {text!r}")
    return repo, semver.normalize(version)


def walk(graph, explicit, released, propagates, next_version):
    """Yields the steps in order, deciding each one only after its upstreams are released.

    `propagates(edge, upstream_version)` and `next_version(repo)` are asked lazily, so the
    caller can release a step before the generator looks at what follows it.
    """
    done = dict([released]) if released else {}
    for repo in topo_order(graph):
        if repo in done:
            continue
        incoming = [e for e in graph.get("edges") or [] if e["to"] == repo and e["from"] in done]
        if repo in explicit:
            version, reason = explicit[repo], "requested"
        else:
            triggers = [e for e in incoming if propagates(e, done[e["from"]])]
            if not triggers:
                continue
            version = next_version(repo)
            reason = "after " + ", ".join(f"{e['from']} {done[e['from']]}" for e in triggers)
        inputs = {e["input"]: done[e["from"]] for e in incoming if e.get("input")}
        yield Step(repo, version, reason, inputs)
        done[repo] = version


def preview(graph, explicit, released):
    """Rows (repo, action, version, why) of what the train may do, before any network call."""
    rows, sure, maybe = [], set(), set()
    if released:
        rows.append((released[0], "released", released[1], "trigger"))
        sure.add(released[0])
    for repo in topo_order(graph):
        if repo in sure:
            continue
        if repo in explicit:
            rows.append((repo, "release", explicit[repo], "requested"))
            sure.add(repo)
            continue
        incoming = [e for e in graph.get("edges") or [] if e["to"] == repo and e["from"] in sure | maybe]
        if not incoming:
            continue
        certain = [e for e in incoming if e["from"] in sure and not e.get("paths")]
        if certain:
            rows.append((repo, "release", "+patch", "after " + ", ".join(e["from"] for e in certain)))
            sure.add(repo)
        else:
            why = "; ".join(
                f"{e['from']} changes {', '.join(e['paths'])}" if e.get("paths") else f"{e['from']} releases"
                for e in incoming
            )
            rows.append((repo, "maybe", "+patch", "if " + why))
            maybe.add(repo)
    return rows


def table(rows, header=("repo", "action", "version", "why")):
    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    line = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, widths)).rstrip()  # noqa: E731
    return [line(header), line(["-" * w for w in widths])] + [line(r) for r in rows]


# ---------------------------------------------------------------- GitHub

def gh(*args, check=True):
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        raise Failure("the GitHub CLI `gh` is not installed or not on PATH")
    if proc.returncode != 0:
        if not check:
            return None
        message = (proc.stderr or proc.stdout).strip().splitlines()
        raise Failure(f"gh {' '.join(args)}: {message[-1] if message else f'exit {proc.returncode}'}")
    return proc.stdout


class GitHub:
    def __init__(self):
        self._tags = {}

    def tags(self, repo):
        if repo not in self._tags:
            out = gh("api", f"repos/{ORG}/{repo}/tags", "--paginate", "--jq", ".[].name", check=False)
            if out is None:
                raise Failure(f"cannot list tags of {ORG}/{repo}: the repository does not exist or the token cannot read it")
            self._tags[repo] = [t.removeprefix("v") for t in out.split() if t.startswith("v") and semver.is_valid(t)]
        return self._tags[repo]

    def forget_tags(self, repo):
        self._tags.pop(repo, None)

    def changed_files(self, repo, base, head):
        out = gh("api", f"repos/{ORG}/{repo}/compare/{base}...{head}", "--paginate", "--jq", ".files[].filename")
        return out.splitlines()

    def published(self, repo, version):
        out = gh("release", "view", f"v{version}", "-R", f"{ORG}/{repo}", "--json", "isDraft", "--jq", ".isDraft", check=False)
        return out is not None and out.strip() == "false"

    def runs(self, repo):
        out = gh("run", "list", "-R", f"{ORG}/{repo}", "-w", "release.yml", "-L", "50",
                 "--json", "databaseId,displayTitle,createdAt,status,conclusion,url", check=False)
        return json.loads(out) if out else []


def train_run_version(runs, train):
    """The version an earlier attempt of this train dispatched, from the run title."""
    pattern = re.compile(rf"^Release (\S+) · train {re.escape(str(train))}$")
    for run in runs:
        found = pattern.match(run.get("displayTitle", ""))
        if found:
            return found.group(1)
    return None


# ---------------------------------------------------------------- train

class Train:
    def __init__(self, graph, train_id, dry_run, github=None):
        self.graph = graph
        self.train = str(train_id)
        self.dry_run = dry_run
        self.github = github or GitHub()
        self.results = []

    def propagates(self, edge, version):
        upstream, paths = edge["from"], edge.get("paths")
        if not paths:
            log("🧭", f"{edge['to']}: follows every {upstream} release")
            return True
        tags = self.github.tags(upstream)
        before = semver.previous(tags, version)
        if before is None:
            log("🧭", f"{edge['to']}: {upstream} has no tag before {version}, propagating")
            return True
        head = f"v{version}" if version in tags else "master"
        changed = self.github.changed_files(upstream, f"v{before}", head)
        hits = [p for p in changed if matches_any(p, paths)]
        if hits:
            log("🧭", f"{edge['to']}: {upstream} v{before}...{head} changed {len(hits)} file(s) under {', '.join(paths)}, e.g. {hits[0]}")
            return True
        log("⏭️", f"{edge['to']}: {upstream} v{before}...{head} changed nothing under {', '.join(paths)}")
        return False

    def next_version(self, repo):
        earlier = train_run_version(self.github.runs(repo), self.train)
        if earlier:
            log("🧭", f"{repo}: an earlier attempt of train {self.train} chose {earlier}, keeping it")
            return earlier
        top = semver.highest(self.github.tags(repo))
        if top is None:
            raise Failure(f"{repo} has no v* tag yet, so it has no version to bump. Name one: --versions \"{repo}=X.Y.Z\"")
        return semver.next_patch(top)

    def release(self, step):
        inputs = " ".join(f"{k}={v}" for k, v in step.inputs.items())
        what = f"{step.repo} {step.version}" + (f" ({inputs})" if inputs else "")
        if self.dry_run:
            log("📦", f"would dispatch {what}: {step.reason}")
            self.results.append((step, "dry run"))
            return
        if self.github.published(step.repo, step.version):
            log("⏭️", f"{step.repo} v{step.version} is already released")
            self.results.append((step, "already released"))
            return

        title = f"Release {step.version} · train {self.train}"
        before = {r["databaseId"] for r in self.github.runs(step.repo)}
        args = ["workflow", "run", "release.yml", "-R", f"{ORG}/{step.repo}",
                "-f", f"version={step.version}", "-f", "notify=false", "-f", f"train={self.train}"]
        for name, value in step.inputs.items():
            args += ["-f", f"{name}={value}"]
        log("📦", f"dispatching {what}: {step.reason}")
        gh(*args)

        run = self.find_run(step.repo, title, before)
        log("⏳", f"waiting for {step.repo}: {run['url']}")
        proc = subprocess.run(["gh", "run", "watch", str(run["databaseId"]), "-R", f"{ORG}/{step.repo}",
                               "--exit-status", "--interval", "15"], capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
            raise Failure(f"{step.repo} release {step.version} failed: {run['url']}\n{tail}")
        self.github.forget_tags(step.repo)
        if not self.github.published(step.repo, step.version):
            raise Failure(f"{step.repo} release run succeeded but v{step.version} has no published release: {run['url']}")
        log("✅", f"{step.repo} v{step.version} released")
        self.results.append((step, "released"))

    def find_run(self, repo, title, before):
        deadline = time.monotonic() + FIND_RUN_SECONDS
        while True:
            for run in self.github.runs(repo):
                if run["databaseId"] not in before and run.get("displayTitle") == title:
                    return run
            if time.monotonic() > deadline:
                raise Failure(f"dispatched {repo}, but no run titled {title!r} appeared within {FIND_RUN_SECONDS} s")
            time.sleep(5)

    def run(self, explicit, released, planned=()):
        for step in walk(self.graph, explicit, released, self.propagates, self.next_version):
            self.release(step)
        touched = {step.repo for step, _ in self.results}
        for repo in planned:
            if repo not in touched and repo != (released or ("",))[0]:
                log("⏭️", f"{repo}: nothing upstream changed, not released")


def summary(rows, results, error):
    lines = ["## 🚂 Release train", ""]
    if rows:
        lines += ["| repo | plan | version | why |", "|---|---|---|---|"]
        lines += [f"| {r} | {a} | {v} | {w} |" for r, a, v, w in rows]
        lines.append("")
    if results:
        lines += ["| repo | version | inputs | result |", "|---|---|---|---|"]
        for step, result in results:
            inputs = ", ".join(f"`{k}={v}`" for k, v in step.inputs.items()) or "–"
            lines.append(f"| {step.repo} | {step.version} | {inputs} | {result} |")
        lines.append("")
    if error:
        lines += [f"❌ {error.splitlines()[0]}", ""]
    if not rows and not results and not error:
        lines += ["Nothing to release.", ""]
    return "\n".join(lines)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--released", default="", help="repo@version that is already released (the trigger)")
    parser.add_argument("--versions", default="", help='"coderpack=2.1.0 protocol=2.0.1" or "all=2.0.0"')
    parser.add_argument("--train", default=os.environ.get("GITHUB_RUN_ID", "local"), help="train id (default: $GITHUB_RUN_ID)")
    parser.add_argument("--graph", default=str(GRAPH), help="path to graph.yml")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, dispatch nothing")
    args = parser.parse_args(argv)

    rows, train, error = [], None, None
    try:
        graph = load_graph(args.graph)
        explicit = parse_versions(args.versions, graph["repos"])
        released = parse_released(args.released)
        if released and released[0] not in graph["repos"]:
            log("🚂", f"{released[0]} is not in graph.yml, so nothing is downstream of it")
        if released:
            explicit.pop(released[0], None)
        log("🚂", f"train {args.train}" + (" (dry run)" if args.dry_run else ""))
        rows = preview(graph, explicit, released)
        for line in table(rows) if rows else ["nothing to release"]:
            log("🧭", line)
        train = Train(graph, args.train, args.dry_run)
        train.run(explicit, released, [r[0] for r in rows])
        log("✅", "train finished")
    except (Failure, ValueError) as e:
        error = str(e)
        log("❌", error)
    finally:
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(summary(rows, train.results if train else [], error))
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
