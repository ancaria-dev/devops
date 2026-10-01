"""Semantic versions as the release workflows use them: MAJOR.MINOR.PATCH[-pre], tags v<version>.

CLI, used by the composite actions:
  semver.py check <version>        prints the version without a leading v, exits 1 when it is not semver
  semver.py max [<version>...]     prints the highest valid version (ignores the rest), nothing when none
  semver.py lt <a> <b>             exits 0 when a < b, 1 otherwise
"""

import re
import sys
from functools import cmp_to_key

PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?$"
)


def parse(text):
    """Returns (major, minor, patch, [pre identifiers]) or None."""
    match = PATTERN.match(text.strip().removeprefix("v"))
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return int(major), int(minor), int(patch), pre.split(".") if pre else []


def is_valid(text):
    return parse(text) is not None


def normalize(text):
    """The version without a leading v. Raises ValueError when it is not semver."""
    if not is_valid(text):
        raise ValueError(f"not a version (MAJOR.MINOR.PATCH[-pre]): {text!r}")
    return text.strip().removeprefix("v")


def _compare_pre(a, b):
    if not a or not b:
        return (not a) - (not b)
    for x, y in zip(a, b):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return -1 if int(x) < int(y) else 1
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return -1 if x < y else 1
    return (len(a) > len(b)) - (len(a) < len(b))


def compare(a, b):
    pa, pb = parse(a), parse(b)
    if pa is None or pb is None:
        raise ValueError(f"cannot compare {a!r} and {b!r}")
    if pa[:3] != pb[:3]:
        return -1 if pa[:3] < pb[:3] else 1
    return _compare_pre(pa[3], pb[3])


def highest(versions):
    valid = [normalize(v) for v in versions if is_valid(v)]
    return max(valid, key=cmp_to_key(compare)) if valid else None


def previous(versions, version):
    """The highest of `versions` below `version`, or None."""
    return highest(v for v in versions if is_valid(v) and compare(v, version) < 0)


def next_patch(version):
    """1.2.3 -> 1.2.4; a pre-release becomes its release: 1.3.0-rc.1 -> 1.3.0."""
    major, minor, patch, pre = parse(version)
    return f"{major}.{minor}.{patch}" if pre else f"{major}.{minor}.{patch + 1}"


def _main(args):
    if args[:1] == ["check"] and len(args) == 2:
        if not is_valid(args[1]):
            return 1
        print(normalize(args[1]))
        return 0
    if args[:1] == ["max"]:
        top = highest(args[1:])
        if top:
            print(top)
        return 0
    if args[:1] == ["lt"] and len(args) == 3:
        return 0 if compare(args[1], args[2]) < 0 else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
