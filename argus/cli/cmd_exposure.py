"""`argus exposure` -- public model-exposure accounting: is this scroll held out for this model?"""
from __future__ import annotations

import argparse
import json
import sys


def _load(path):
    from argus.core import exposure_accounting as EA
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return EA, EA.Accounting(doc)


def run(argv, out=sys.stdout) -> int:
    ap = argparse.ArgumentParser(prog="argus exposure", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for name in ("validate", "check", "report", "graph"):
        p = sub.add_parser(name)
        p.add_argument("record")
        if name in ("check", "report"):
            p.add_argument("--scroll", action="append", default=[])
            p.add_argument("--model", action="append", default=[])
        if name != "validate":
            p.add_argument("--json", action="store_true")
            p.add_argument("--svg", action="store_true")
        if name == "report":
            p.add_argument("--markdown", action="store_true")
    r = sub.add_parser("resolve")
    r.add_argument("name")
    r.add_argument("--survey")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if not a.cmd:
        print(__doc__, file=out)
        return 2
    try:
        if a.cmd == "resolve":
            from argus.core import exposure_accounting as EA
            from argus.core.official_identity import load_survey
            surv = load_survey(a.survey) if a.survey else None
            ident = EA.Identity(surv)
            res = ident.resolve(a.name)
            res["prize_set"] = bool(res["physical"] and ident.is_prize(res["physical"]))
            if res["prize_set"]:
                res["physical"] = EA.PRIZE_MASK
            res["related_possibly_same_object"] = [] if res["prize_set"] or not res["physical"] else [
                {"scroll": x["scroll"] if not ident.is_prize(x["scroll"]) else EA.PRIZE_MASK,
                 "status": x["status"], "reason": x["reason"] if not ident.is_prize(x["scroll"])
                 else "shares an id stem"} for x in ident.related(res["physical"])]
            print(json.dumps(res, indent=1, sort_keys=True), file=out)
            return 0 if res["physical"] else 1
        EA, acc = _load(a.record)
        if a.cmd == "validate":
            print("record ok: %d models, %d claims, %d edges" % (
                len(acc.models), len(acc.claims), len(acc.edges)), file=out)
            for f in acc.rec["findings"]:
                print("finding: " + f, file=out)
            return 0
        if a.cmd == "graph":
            rep = acc.report()
            print(EA.graph_svg(rep) if a.svg else json.dumps(rep["graph"], indent=1, sort_keys=True),
                  file=out)
            return 0
        if a.cmd == "check":
            if len(a.model) != 1 or len(a.scroll) != 1:
                print("argus exposure check: give exactly one --model and one --scroll", file=out)
                return 2
            v = acc.verdict(a.model[0], a.scroll[0])
            if a.json:
                print(json.dumps(v, indent=1, sort_keys=True), file=out)
            else:
                print("%s  %s  ->  %s" % (v["model"], v["query"], v["verdict"]), file=out)
                for n, c in v["channels"].items():
                    print("  %-22s %s" % (n, c["state"]), file=out)
                for x in v["reasons"]:
                    print("  why: " + x, file=out)
            return 0 if v["verdict"] == EA.ELIGIBLE else 1
        rep = acc.report(a.scroll, a.model)
        if a.json:
            print(json.dumps(rep, indent=1, sort_keys=True), file=out)
        elif a.svg:
            print(EA.graph_svg(rep), file=out)
        else:
            print(EA.to_markdown(rep), file=out)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("argus exposure: %s" % exc, file=out)
        return 2


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
