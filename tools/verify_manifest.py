"""Verify RELEASE_MANIFEST.json: every listed file exists with its sha256, and nothing is unlisted.

Usage: python tools/verify_manifest.py   (exit 0 on a match, 1 otherwise)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "RELEASE_MANIFEST.json"


def tracked() -> set | None:
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return {n for n in r.stdout.split("\n") if n}


def main() -> int:
    if not MANIFEST.is_file():
        print("no manifest: RELEASE_MANIFEST.json is absent")
        return 1
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = []
    for row in doc["files"]:
        p = ROOT / row["path"]
        if not p.is_file():
            bad.append("missing: %s" % row["path"])
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != row["sha256"]:
            bad.append("sha256 differs: %s" % row["path"])
    listed = {r["path"] for r in doc["files"]} | {"RELEASE_MANIFEST.json"}
    t = tracked()
    if t is not None:
        for extra in sorted(t - listed):
            bad.append("tracked but not in the manifest: %s" % extra)
    for line in bad:
        print(line)
    print("manifest: %d files, %d problems" % (len(doc["files"]), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
