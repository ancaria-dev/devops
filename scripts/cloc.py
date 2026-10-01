#!/usr/bin/env python3
"""Counts lines of code in every code repository and writes shields.io endpoint files to badges/<repo>.json."""

import argparse
import json
import subprocess
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import ORG, gh, log  # noqa: E402

REPOS = ["mappings", "agent", "coderpack", "protocol", "launcher", "build", "mods", "idea", "site", "research", "devops"]
EXCLUDE = "node_modules,build,dist,target,.gradle,gen"


def short(n):
    """950 -> '950', 12345 -> '12.3k', 12000 -> '12k', 1234567 -> '1.2M'."""
    def tenths(divisor):
        return (Decimal(n) / divisor).quantize(Decimal("0.1"), ROUND_HALF_UP)

    if n < 1000:
        return str(n)
    if tenths(1000) < 1000:
        return f"{tenths(1000).normalize():f}k"
    return f"{tenths(10**6).normalize():f}M"


def badge(lines):
    return {"schemaVersion": 1, "label": "lines of code", "message": short(lines), "color": "blue"}


def count(repo, workdir):
    if gh("api", f"repos/{ORG}/{repo}", "--jq", ".name", check=False) is None:
        log("⏭️", f"{repo}: not on GitHub yet")
        return None
    target = Path(workdir) / repo
    subprocess.run(["git", "clone", "--quiet", "--depth", "1", f"https://github.com/{ORG}/{repo}.git", str(target)], check=True)
    out = subprocess.run(["cloc", "--json", "--quiet", f"--exclude-dir={EXCLUDE}", str(target)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["SUM"]["code"] if out.strip() else 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="badges")
    parser.add_argument("repos", nargs="*", default=REPOS)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as workdir:
        for repo in args.repos:
            lines = count(repo, workdir)
            if lines is None:
                continue
            data = badge(lines)
            (out / f"{repo}.json").write_text(json.dumps(data) + "\n", encoding="utf-8")
            log("✅", f"{repo}: {lines} lines of code ({data['message']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
