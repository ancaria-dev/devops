#!/usr/bin/env python3
"""Builds meta.json from the latest GitHub Release of each component (graph.yml `meta`).

Writes meta.json and sets the step output `changed` to whether it differs from the live file.
"""

import argparse
import base64
import fnmatch
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import GRAPH, ORG, Failure, gh, load_graph, log  # noqa: E402

LIVE = "https://ancaria.dev/files/launcher/meta.json"
HEADERS = {"User-Agent": "ancaria-devops", "Cache-Control": "no-cache"}


def latest_release(repo):
    out = gh("release", "view", "-R", f"{ORG}/{repo}", "--json", "tagName,assets", check=False)
    if out is None:
        raise Failure(f"{ORG}/{repo} has no published release")
    return json.loads(out)


def pick_asset(release, pattern, repo):
    found = [a for a in release["assets"] if fnmatch.fnmatchcase(a["name"], pattern)]
    if len(found) != 1:
        names = ", ".join(a["name"] for a in release["assets"]) or "none"
        raise Failure(f"{ORG}/{repo} {release['tagName']}: expected one asset matching {pattern!r}, found {len(found)} (assets: {names})")
    return found[0]


def sha256_of(asset):
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        return digest.removeprefix("sha256:")
    log("📜", f"no digest for {asset['name']}, downloading it")
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(asset["url"], headers=HEADERS)) as response:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def api_level(spec, tag):
    out = gh("api", f"repos/{ORG}/{spec['repo']}/contents/{spec['path']}?ref={tag}", "--jq", ".content")
    source = base64.b64decode(out).decode("utf-8")
    found = re.search(spec["pattern"], source)
    if not found:
        raise Failure(f"{spec['repo']} {tag}: {spec['path']} has no match for {spec['pattern']!r}")
    return int(found.group(1))


def build(meta_spec):
    releases = {}

    def release(repo):
        if repo not in releases:
            releases[repo] = latest_release(repo)
        return releases[repo]

    level_spec = meta_spec["apiLevel"]
    meta = {
        "schema": meta_spec["schema"],
        "apiLevel": api_level(level_spec, release(level_spec["repo"])["tagName"]),
    }
    for name, spec in meta_spec["components"].items():
        try:
            rel = release(spec["repo"])
        except Failure as e:
            raise Failure(f"meta.json component {name!r}: {e}")
        asset = pick_asset(rel, spec["asset"], spec["repo"])
        meta[name] = {
            "version": rel["tagName"].removeprefix("v"),
            "url": asset["url"],
            "sha256": sha256_of(asset),
            "size": asset["size"],
        }
        log("📜", f"{name}: {meta[name]['version']} {asset['name']} ({asset['size']} bytes)")
    return meta


def live():
    try:
        with urllib.request.urlopen(urllib.request.Request(LIVE, headers=HEADERS)) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log("📜", "no live meta.json yet")
            return None
        log("📜", f"cannot read the live meta.json ({e}), treating it as changed")
        return None


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=str(GRAPH))
    parser.add_argument("--out", default="meta.json")
    args = parser.parse_args(argv)
    try:
        meta = build(load_graph(args.graph)["meta"])
    except Failure as e:
        log("❌", str(e))
        return 1
    text = json.dumps(meta, indent=2) + "\n"
    Path(args.out).write_text(text, encoding="utf-8")
    changed = meta != live()
    log("📜", "meta.json changed" if changed else "meta.json is the same as the live one")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
