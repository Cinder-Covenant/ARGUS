"""Public generic exposure accounting: are these models independent evidence, and is this scroll genuinely held out for THIS model?"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from enum import Enum

from argus.core import exposure as X
from argus.core.official_identity import load_survey, parse_segment_on_volume
from argus.core.scroll_ids import ALIASES as _SCROLL_ALIASES, normalize as _norm

RECORD_SCHEMA = "argus-exposure-record-v1"
REPORT_SCHEMA = "argus-exposure-report-v1"

RULE_SHARED_ANCESTRY_V1 = "shared_ancestry_v1"
RULES = {
    RULE_SHARED_ANCESTRY_V1: (
        "Two registered entries join one lineage component when a chain of recorded ancestry "
        "edges (INIT: weights continued from a parent; TEACHER: a parent's predictions used as "
        "labels; PSEUDO_SOURCE: a parent's outputs or embeddings steered pseudo-labels) connects "
        "them, in either direction. Sharing a training scroll does not join components; it is "
        "reported separately. Edges are counted at two strengths: VERIFIED edges only, and "
        "VERIFIED plus INFERRED edges. UNVERIFIED edges never join."),
}


class Status(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNVERIFIED = "UNVERIFIED"


_RANK = {Status.VERIFIED: 2, Status.INFERRED: 1, Status.UNVERIFIED: 0}


def weakest(*statuses) -> Status:
    return min((Status(s) for s in statuses), key=lambda s: _RANK[s]) if statuses \
        else Status.UNVERIFIED


class Ch(str, Enum):
    DIRECT = "direct_labels"
    TEACHER = "teacher_labels"
    PSEUDO = "pseudo_label_lineage"
    PRETRAIN = "raw_ct_pretraining"


CHANNEL_TO_EXPOSURE = {Ch.DIRECT: X.Channel.SUPERVISED_LABEL, Ch.TEACHER: X.Channel.TEACHER_PREDICTION,
                       Ch.PSEUDO: X.Channel.PSEUDO_LABEL, Ch.PRETRAIN: X.Channel.RAW_VOLUME_PRETRAINING}
EDGE_KINDS = {"INIT": Ch.PRETRAIN, "TEACHER": Ch.TEACHER, "PSEUDO_SOURCE": Ch.PSEUDO}
CLAIM_KINDS = ("exposed", "absent", "exposed_set_complete")
ROLES = ("ink_detector", "surface_provider", "fiber_segmenter", "backbone", "teacher",
         "pseudo_label_source", "other")

ELIGIBLE = "ELIGIBLE_AS_HELD_OUT"
NOT_ELIGIBLE = "NOT_ELIGIBLE"
NOT_EVALUATED = "NOT_EVALUATED_HERE"
PRIZE_MASK = "a prize-set scroll (not evaluated here)"

_LEGACY = {ELIGIBLE: X.Eligibility.MODEL_HELDOUT_ELIGIBLE.value}


class RecordError(ValueError):
    pass


def canon(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
                          .encode("utf-8")).hexdigest()



_FRAGMENT_OF = re.compile(r"^(.+?)Cr\d+Fr\d+$")


class Identity:
    """Resolves any name for a piece of data to ONE physical scroll of the public survey."""

    def __init__(self, survey: dict | None = None, aliases=None):
        self.survey = survey if survey is not None else load_survey()
        if not self.survey:
            raise RecordError("the public official survey is not available, so scroll identity "
                              "cannot be normalised (run scripts/refresh_official_survey.py)")
        self.samples = self.survey.get("samples") or {}
        self._key = {}
        self._token = {}
        for s in sorted(self.samples):
            self._key[_norm(s)] = s
            row = self.samples[s]
            for sid, sc in (row.get("scans") or {}).items():
                self._token.setdefault(sid, (s, "scan_id"))
                if sc.get("long_id"):
                    self._key.setdefault(_norm(sc["long_id"]), s)
            for vid, v in (row.get("volumes") or {}).items():
                self._token.setdefault(vid, (s, "volume_id"))
                if v.get("scan_id"):
                    self._token.setdefault(v["scan_id"], (s, "scan_id"))
                if v.get("long_id"):
                    self._key.setdefault(_norm(v["long_id"]), s)
        for a, c in _SCROLL_ALIASES.items():
            if c in self.samples:
                self._key.setdefault(_norm(a), c)
        self.declared = {}
        for al in aliases or []:
            tgt = al.get("scroll")
            st = Status(al.get("status", "UNVERIFIED"))
            if tgt in self.samples and st is not Status.UNVERIFIED:
                self.declared[_norm(al["name"])] = (tgt, st, al.get("reasons") or [])
        prize = (self.survey.get("prize_sets") or {})
        self.prize = {s for v in prize.values() for s in (v.get("scrolls") or [])}
        for s, row in self.samples.items():
            if any(v.get("prizes") for v in (row.get("volumes") or {}).values()):
                self.prize.add(s)

    def is_prize(self, scroll) -> bool:
        return scroll in self.prize

    def resolve(self, name) -> dict:
        """{physical, via, status, reasons}."""
        raw = str(name or "").strip()
        out = {"name": raw, "physical": None, "via": None, "status": Status.UNVERIFIED.value,
               "reasons": []}
        if not raw:
            out["reasons"].append("empty name")
            return out
        k = _norm(raw)
        if k in self._key:
            out.update(physical=self._key[k], via="survey_key_or_alias", status="VERIFIED")
            return out
        vid, _pitch = parse_segment_on_volume(raw)
        toks = [vid] if vid else []
        toks += re.findall(r"(?<!\d)(\d{14})(?!\d)", raw)
        hits = {self._token[t] for t in toks if t in self._token}
        phys = {h[0] for h in hits}
        if len(phys) == 1:
            kinds = sorted({h[1] for h in hits})
            out.update(physical=sorted(phys)[0], via="+".join(kinds), status="VERIFIED")
            return out
        if len(phys) > 1:
            out["reasons"].append("the name carries tokens of several physical scrolls: %s"
                                  % ", ".join(sorted(phys)))
            return out
        if not phys and "/" in raw.replace("\\", "/"):
            parts = {self._key[_norm(x)] for x in re.split(r"[/\]", raw)
                     if x and _norm(x) in self._key and self._key[_norm(x)] in self.samples}
            if len(parts) == 1:
                out.update(physical=sorted(parts)[0], via="path_component", status="VERIFIED")
                return out
        if k in self.declared:
            s, st, why = self.declared[k]
            out.update(physical=s, via="declared_alias", status=st.value,
                       reasons=list(why) or ["declared alias"])
            return out
        out["reasons"].append("the name matches no survey scroll, alias, volume id or scan id")
        return out

    def related(self, scroll) -> list:
        """Other survey scrolls that MAY be the same physical object (INFERRED, never verified)."""
        out = []
        for o in sorted(self.samples):
            if o == scroll:
                continue
            reason = self._related_reason(scroll, o)
            if reason:
                out.append({"scroll": o, "status": Status.INFERRED.value, "reason": reason})
        return out

    @staticmethod
    def _stem(x):
        m = re.match(r"^(PHerc\d+)[A-Za-z]{0,2}\d?$", x)
        if m:
            return m.group(1)
        m = re.match(r"^(.*?[A-Z0-9])[a-z]+$", x)
        return m.group(1) if m else x

    @classmethod
    def _related_reason(cls, a, b):
        for x, y in ((a, b), (b, a)):
            m = _FRAGMENT_OF.match(x)
            if m and m.group(1) == y:
                return "%s is named as a crate/fragment of %s" % (x, y)
        sa, sb = cls._stem(a), cls._stem(b)
        if sa == sb and a != b:
            return ("the ids share the stem %s; a piece or a sibling of the same object cannot "
                    "be excluded from the names alone" % sa)
        return None



def _need(cond, msg):
    if not cond:
        raise RecordError(msg)


def load_record(doc: dict) -> dict:
    """Validate a record and return a normalised copy plus a `findings` list."""
    _need(isinstance(doc, dict) and doc.get("schema") == RECORD_SCHEMA,
          "schema must be %r" % RECORD_SCHEMA)
    rec = copy.deepcopy(doc)
    findings = []
    rule = (rec.get("rule") or RULE_SHARED_ANCESTRY_V1)
    _need(rule in RULES, "unknown lineage rule %r; declared rules: %s" % (rule, sorted(RULES)))
    rec["rule"] = rule
    sources = rec.setdefault("sources", {})
    models = {}
    for m in rec.get("models") or []:
        _need(m.get("id") and m["id"] not in models, "model ids must be present and unique: %r"
              % m.get("id"))
        _need(m.get("role", "other") in ROLES, "model %s: role must be one of %s" % (m["id"], ROLES))
        m.setdefault("role", "other")
        models[m["id"]] = m

    def cited(item, what):
        st = Status(item.get("status", "UNVERIFIED"))
        if st is Status.VERIFIED:
            src = sources.get(item.get("source"))
            if not (src and str(src.get("url", "")).startswith("https://")
                    and re.match(r"^\d{4}-\d{2}-\d{2}", str(src.get("retrieved", "")))):
                findings.append("%s claims VERIFIED without a cited https source and retrieval "
                                "date; treated as UNVERIFIED" % what)
                st = Status.UNVERIFIED
        if st is Status.INFERRED and not item.get("reasons"):
            findings.append("%s is INFERRED without stated reasons; treated as UNVERIFIED" % what)
            st = Status.UNVERIFIED
        item["status"] = st.value

    for i, c in enumerate(rec.get("claims") or []):
        w = "claim %s" % c.get("id", i)
        _need(c.get("model") in models, "%s names unknown model %r" % (w, c.get("model")))
        _need(c.get("kind") in CLAIM_KINDS, "%s: kind must be one of %s" % (w, CLAIM_KINDS))
        try:
            Ch(c.get("channel"))
        except ValueError:
            raise RecordError("%s: channel must be one of %s" % (w, [x.value for x in Ch])) from None
        if c["kind"] == "exposed_set_complete":
            _need(isinstance(c.get("scrolls"), list), "%s needs a scrolls list" % w)
        else:
            _need(c.get("scroll"), "%s needs a scroll (absent may use \"*\")" % w)
        cited(c, w)
    seen = set()
    for i, e in enumerate(rec.get("edges") or []):
        w = "edge %s<-%s" % (e.get("child"), e.get("parent"))
        _need(e.get("child") in models and e.get("parent") in models,
              "%s names an unknown model" % w)
        _need(e.get("kind") in EDGE_KINDS, "%s: kind must be one of %s" % (w, sorted(EDGE_KINDS)))
        cited(e, w)
    parents = {}
    for e in rec.get("edges") or []:
        parents.setdefault(e["child"], []).append(e["parent"])

    def walk(n, stack):
        _need(n not in stack, "ancestry cycle through %s" % n)
        for p in parents.get(n, []):
            walk(p, stack | {n})
    for m in models:
        walk(m, frozenset())
    rec.setdefault("claims", [])
    rec.setdefault("edges", [])
    rec.setdefault("identity_aliases", [])
    for a in rec["identity_aliases"]:
        cited(a, "alias %s" % a.get("name"))
    rec["findings"] = findings
    return rec



class Accounting:
    def __init__(self, record: dict, survey: dict | None = None):
        self.rec = load_record(record)
        self.ident = Identity(survey, self.rec["identity_aliases"])
        self.models = {m["id"]: m for m in self.rec["models"]}
        self.claims = self.rec["claims"]
        self.edges = self.rec["edges"]
        self._memo = {}

    def _scrolls_of(self, claim) -> list:
        names = claim["scrolls"] if claim["kind"] == "exposed_set_complete" else [claim["scroll"]]
        return [self.ident.resolve(n) if n != "*" else {"name": "*", "physical": "*",
                                                        "status": "VERIFIED", "reasons": []}
                for n in names]

    def _channel_claims(self, model, ch):
        return [c for c in self.claims if c["model"] == model and c["channel"] == ch.value]

    def parents(self, model, ch=None):
        return [e for e in self.edges if e["child"] == model
                and (ch is None or EDGE_KINDS[e["kind"]] is ch)]

    def channel(self, model, ch: Ch, scroll, _stack=()) -> dict:
        key = (model, ch, scroll)
        if key in self._memo:
            return self._memo[key]
        _need(model not in _stack, "ancestry cycle through %s" % model)
        exposed, reasons, blocked = [], [], []
        absent_status = None
        for c in self._channel_claims(model, ch):
            ids = self._scrolls_of(c)
            unresolved = [i["name"] for i in ids if i["physical"] is None]
            hit = [i for i in ids if i["physical"] == scroll]
            if c["kind"] == "exposed":
                if hit:
                    st = weakest(c["status"], hit[0]["status"])
                    exposed.append({"model": model, "channel": ch.value, "status": st.value,
                                    "claim": c.get("id"), "source": c.get("source"),
                                    "via_name": hit[0]["name"], "segments": c.get("segments"),
                                    "path": [model]})
                elif unresolved:
                    blocked.append("claim %s names %s, which resolves to no physical scroll, so "
                                   "it cannot be shown to differ from %s" % (c.get("id"),
                                   ", ".join(unresolved), scroll))
            elif c["kind"] == "exposed_set_complete":
                if hit:
                    st = weakest(c["status"], hit[0]["status"])
                    exposed.append({"model": model, "channel": ch.value, "status": st.value,
                                    "claim": c.get("id"), "source": c.get("source"),
                                    "via_name": hit[0]["name"], "segments": c.get("segments"),
                                    "path": [model]})
                elif unresolved:
                    blocked.append("closed set %s names %s, which resolves to no physical scroll"
                                   % (c.get("id"), ", ".join(unresolved)))
                else:
                    st = weakest(c["status"], *[i["status"] for i in ids])
                    absent_status = st if absent_status is None else max(
                        absent_status, st, key=lambda s: _RANK[s])
                    if st is not Status.VERIFIED:
                        weak = [i["name"] for i in ids if i["status"] != "VERIFIED"]
                        reasons.append("closed-set claim %s is only %s%s" % (
                            c.get("id"), st.value, " (identity of %s is only inferred)"
                            % ", ".join(weak) if weak else ""))
            else:
                wild = any(i["physical"] == "*" for i in ids)
                if hit or wild:
                    st = weakest(c["status"], (hit or ids)[0]["status"])
                    absent_status = st if absent_status is None else max(
                        absent_status, st, key=lambda s: _RANK[s])
                    if st is not Status.VERIFIED:
                        reasons.append("absence claim %s is only %s" % (c.get("id"), st.value))
                elif unresolved:
                    blocked.append("absence claim %s names unresolved %s"
                                   % (c.get("id"), ", ".join(unresolved)))
        anc_ok = True
        for e in self.parents(model, ch):
            for ch2 in Ch:
                sub = self.channel(e["parent"], ch2, scroll, _stack + (model,))
                blocked.extend(sub["blocked_by"])
                for x in sub["exposed"]:
                    exposed.append({**x, "channel": ch.value,
                                    "status": weakest(x["status"], e["status"]).value,
                                    "path": [model] + x["path"], "inherited_channel": ch2.value,
                                    "edge": e["kind"]})
                if sub["state"] != "CLEAN" and not sub["exposed"]:
                    anc_ok = False
                    reasons.append("ancestor %s (%s edge) is not verified absent on %s: %s"
                                   % (e["parent"], e["kind"], ch2.value, sub["state"]))
            if Status(e["status"]) is not Status.VERIFIED:
                anc_ok = False
                reasons.append("the %s edge to %s is only %s" % (e["kind"], e["parent"], e["status"]))
        possible = []
        for r in self.ident.related(scroll):
            if self.ident.is_prize(r["scroll"]):
                continue
            sub = self._own_exposed(model, ch, r["scroll"])
            if sub:
                possible.append({"related": r["scroll"], "reason": r["reason"],
                                 "status": "INFERRED", "via": sub})
        if exposed:
            state = "EXPOSED"
            worst = weakest(*[x["status"] for x in exposed])
            reasons.insert(0, "exposed (%s): %s" % (worst.value, "; ".join(
                sorted({" <- ".join(x["path"]) for x in exposed}))))
        elif blocked:
            state = "UNVERIFIED"
            reasons = sorted(set(blocked)) + reasons
        elif possible:
            state = "EXPOSURE_POSSIBLE"
            reasons = ["%s may be the same physical object as %s (%s) and is exposed there"
                       % (scroll, p["related"], p["reason"]) for p in possible] + reasons
        elif absent_status is None:
            state = "UNVERIFIED"
            reasons.insert(0, "no source states this channel for this model (default UNVERIFIED)")
        elif absent_status is Status.VERIFIED and anc_ok:
            state = "CLEAN"
        elif absent_status is Status.VERIFIED:
            state = "UNVERIFIED"
        else:
            state = "ABSENT_INFERRED"
        out = {"channel": ch.value, "state": state, "exposed": exposed, "reasons": reasons,
               "blocked_by": sorted(set(blocked)), "possible": possible,
               "exposure_channel": CHANNEL_TO_EXPOSURE[ch].value,
               "exposure_state": {"EXPOSED": X.State.EXPOSED.value, "CLEAN": X.State.CLEAN.value}
               .get(state, X.State.UNKNOWN.value)}
        self._memo[key] = out
        return out

    def _own_exposed(self, model, ch, scroll):
        """Cheap own-claim check used for sibling links (no inheritance, no recursion)."""
        for c in self._channel_claims(model, ch):
            if c["kind"] in ("exposed", "exposed_set_complete") and any(
                    i["physical"] == scroll for i in self._scrolls_of(c)):
                return c.get("id")
        for e in self.parents(model, ch):
            for ch2 in Ch:
                r = self._own_exposed(e["parent"], ch2, scroll)
                if r:
                    return r
        return None

    def verdict(self, model, scroll_name) -> dict:
        _need(model in self.models, "unknown model %r" % model)
        ident = self.ident.resolve(scroll_name)
        base = {"model": model, "query": scroll_name, "physical_scroll": ident["physical"],
                "identity": {"via": ident["via"], "status": ident["status"],
                            "reasons": ident["reasons"]}}
        if ident["physical"] and self.ident.is_prize(ident["physical"]):
            return {**base, "physical_scroll": None, "query": PRIZE_MASK, "verdict": NOT_EVALUATED,
                    "channels": {}, "reasons": ["prize-set scrolls are not evaluated by the public "
                                                "tool; nothing about them is reported"]}
        if not ident["physical"]:
            return {**base, "verdict": NOT_ELIGIBLE, "channels": {},
                    "reasons": ["the scroll name resolves to no physical scroll: %s"
                                % "; ".join(ident["reasons"])]}
        chans = {ch.value: self.channel(model, ch, ident["physical"]) for ch in Ch}
        ok = all(v["state"] == "CLEAN" for v in chans.values())
        reasons = []
        if any(self.ident.is_prize(r["scroll"]) for r in self.ident.related(ident["physical"])):
            ok = False
            reasons.append("the id shares a stem with a prize-set scroll; that the two are "
                           "different physical objects cannot be shown from names, and the "
                           "prize-set scroll is not evaluated here")
        for name, v in chans.items():
            if v["state"] != "CLEAN":
                reasons.append("%s: %s%s" % (name, v["state"],
                               " -- " + "; ".join(v["reasons"][:3]) if v["reasons"] else ""))
        legacy = X.Eligibility.MODEL_HELDOUT_ELIGIBLE if ok else (
            X.Eligibility.DEVELOPMENT_ONLY if any(v["state"] == "EXPOSED" for v in chans.values())
            else X.Eligibility.INDETERMINATE)
        return {**base, "verdict": ELIGIBLE if ok else NOT_ELIGIBLE,
                "exposure_eligibility": legacy.value,
                "channels": {n: {"state": v["state"], "exposure_state": v["exposure_state"],
                                 "reasons": v["reasons"],
                                 "exposed_by": [{k: x.get(k) for k in ("status", "claim", "source",
                                                 "path", "via_name", "segments", "edge",
                                                 "inherited_channel")} for x in v["exposed"]]}
                             for n, v in chans.items()},
                "reasons": reasons if not ok else ["every channel is VERIFIED-absent"]}

    def graph(self) -> dict:
        nodes = [{"id": m["id"], "role": m["role"], "type": "model", "url": m.get("url")}
                 for m in self.rec["models"]]
        scrolls = {}
        for c in self.claims:
            if c["kind"] == "absent":
                continue
            for i in self._scrolls_of(c):
                p = i["physical"] or ("UNRESOLVED:" + i["name"])
                if p != "*" and not self.ident.is_prize(i["physical"] or ""):
                    scrolls.setdefault(p, None)
        snodes = [{"id": s, "type": "scroll"} for s in sorted(scrolls)]
        sedges = []
        for c in self.claims:
            if c["kind"] == "absent":
                continue
            for i in self._scrolls_of(c):
                if i["physical"] and self.ident.is_prize(i["physical"]):
                    continue
                sedges.append({"model": c["model"], "scroll": i["physical"] or "UNRESOLVED:" + i["name"],
                               "channel": c["channel"], "status": weakest(c["status"], i["status"]).value,
                               "claim": c.get("id")})
        return {"nodes": nodes + snodes, "ancestry_edges": [
                    {"child": e["child"], "parent": e["parent"], "kind": e["kind"],
                     "status": e["status"], "source": e.get("source")} for e in self.edges],
                "scroll_edges": sorted(sedges, key=lambda x: (x["model"], x["scroll"], x["channel"], x["claim"] or ""))}

    def components(self, min_status=Status.VERIFIED) -> list:
        uf = {m: m for m in self.models}

        def find(x):
            while uf[x] != x:
                uf[x] = uf[uf[x]]
                x = uf[x]
            return x
        for e in self.edges:
            if _RANK[Status(e["status"])] >= _RANK[min_status]:
                uf[find(e["child"])] = find(e["parent"])
        groups = {}
        for m in sorted(self.models):
            groups.setdefault(find(m), []).append(m)
        comps = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
        return [{"members": g, "size": len(g),
                 "roles": {r: sum(1 for m in g if self.models[m]["role"] == r)
                           for r in sorted({self.models[m]["role"] for m in g})}} for g in comps]

    def shared_scrolls(self) -> list:
        """Scroll overlap between entries, reported apart from lineage (it does not join)."""
        by = {}
        for c in self.claims:
            if c["kind"] == "absent":
                continue
            for i in self._scrolls_of(c):
                if i["physical"] and i["physical"] != "*" and not self.ident.is_prize(i["physical"]):
                    by.setdefault(i["physical"], set()).add(c["model"])
        return [{"scroll": s, "models": sorted(m)} for s, m in sorted(by.items()) if len(m) > 1]

    def _released(self, m) -> bool:
        return self.models[m].get("released", True) is not False

    def lineage_summary(self) -> dict:
        rel = [m for m in self.models if self._released(m)]
        n = len(rel)
        out = {"rule": self.rec["rule"], "rule_text": RULES[self.rec["rule"]],
               "registered_entries": n,
               "unreleased_ancestor_nodes": sorted(m for m in self.models if not self._released(m))}
        for label, ms in (("verified_edges", Status.VERIFIED), ("verified_and_inferred_edges",
                                                                Status.INFERRED)):
            comps = self.components(ms)
            for c in comps:
                c["released_members"] = [m for m in c["members"] if self._released(m)]
                c["released_roles"] = {r: sum(1 for m in c["released_members"]
                                              if self.models[m]["role"] == r)
                                       for r in sorted({self.models[m]["role"]
                                                        for m in c["released_members"]})}
            big = max(comps, key=lambda c: (len(c["released_members"]), c["size"]),
                      default={"members": [], "released_members": [], "released_roles": {},
                               "size": 0})
            joined = len(big["released_members"]) if big["size"] > 1 else 0
            out[label] = {"components": comps,
                          "largest_component_size": big["size"],
                          "joined_entries": joined,
                          "joined_ink_detectors": big["released_roles"].get("ink_detector", 0)
                          if joined else 0,
                          "joined_other_roles": {r: k for r, k in big["released_roles"].items()
                                                 if r != "ink_detector"} if joined else {},
                          "unreleased_nodes_in_component": [m for m in big["members"]
                                                            if not self._released(m)] if joined else [],
                          "entries_in_no_recorded_lineage": sum(
                              1 for c in comps if c["size"] == 1 and c["released_members"]),
                          "sentence": self._sentence(n, big, ms)}
        return out

    def _sentence(self, n, big, ms):
        strength = "VERIFIED edges only" if ms is Status.VERIFIED else "VERIFIED and INFERRED edges"
        rel = big.get("released_members", [])
        if big["size"] < 2 or not rel:
            return ("0 of %d registered entries joined a lineage component with another entry "
                    "under rule %s (%s)." % (n, self.rec["rule"], strength))
        rest = {r: k for r, k in big["released_roles"].items() if r != "ink_detector"}
        unrel = [m for m in big["members"] if not self._released(m)]
        return ("%d of %d registered entries joined the same lineage component under rule %s "
                "(%s). Ink detectors among them: %d. Entries that are not ink detectors are "
                "counted separately by role: %s. The component also holds %d unreleased ancestor "
                "node(s) recorded from source text. Registered entries with no recorded ancestry "
                "sit in singleton components; that is the absence of a record, not evidence of "
                "independence."
                % (len(rel), n, self.rec["rule"], strength,
                   big["released_roles"].get("ink_detector", 0),
                   ", ".join("%d %s" % (k, r) for r, k in sorted(rest.items())) or "none",
                   len(unrel)))

    def report(self, queries=None, models=None) -> dict:
        ms = sorted(models) if models else sorted(m for m in self.models if self._released(m))
        qs = list(queries or [])
        verdicts = [self.verdict(m, q) for q in qs for m in ms]
        return {"schema": REPORT_SCHEMA, "record_schema": RECORD_SCHEMA,
                "record_sha256": canon({k: v for k, v in self.rec.items() if k != "findings"}),
                "identity_reference": {"checked_at": self.ident.survey.get("checked_at"),
                                       "catalogue_sha256": ((self.ident.survey.get("sources") or {})
                                                            .get("catalogue") or {}).get("sha256")},
                "findings": self.rec["findings"],
                "lineage": self.lineage_summary(),
                "shared_training_scrolls": self.shared_scrolls(),
                "graph": self.graph(),
                "verdicts": verdicts,
                "not_shown": ["measured leakage or score inflation", "prize-set scrolls",
                              "anything a cited source is silent about (UNVERIFIED)",
                              "independence: no recorded ancestry is not independence"]}


def to_markdown(rep: dict, record: dict | None = None) -> str:
    L = ["# Exposure accounting report", "",
         "Schema `%s`; record sha256 `%s`." % (rep["schema"], rep["record_sha256"][:16]),
         "Identity reference: public official survey checked %s." % rep["identity_reference"]["checked_at"], ""]
    if rep["findings"]:
        L += ["## Record findings", ""] + ["- " + f for f in rep["findings"]] + [""]
    lin = rep["lineage"]
    L += ["## Lineage (rule `%s`)" % lin["rule"], "", lin["rule_text"], ""]
    for key in ("verified_edges", "verified_and_inferred_edges"):
        s = lin[key]
        L += ["- " + s["sentence"]]
    L += ["", "### Components (VERIFIED and INFERRED edges)", ""]
    for i, c in enumerate(lin["verified_and_inferred_edges"]["components"], 1):
        L.append("%d. %s (released: %s)" % (i, ", ".join(c["members"]),
                 ", ".join("%d %s" % (k, r) for r, k in c["released_roles"].items()) or "none"))
    if rep["shared_training_scrolls"]:
        L += ["", "### Scrolls named by more than one entry (reported apart; does not join)", ""]
        L += ["- %s: %s" % (s["scroll"], ", ".join(s["models"])) for s in rep["shared_training_scrolls"]]
    if rep["verdicts"]:
        L += ["", "## Held-out queries (fail-closed)", "",
              "A scroll is eligible for a model only when every channel is VERIFIED-absent.", ""]
        chs = [c.value for c in Ch]
        L += ["| model | query | verdict | " + " | ".join(chs) + " |",
              "|---|---|---|" + "---|" * len(chs)]
        for v in rep["verdicts"]:
            L.append("| %s | %s | %s | %s |" % (v["model"], v["query"], v["verdict"], " | ".join(
                v["channels"].get(c, {}).get("state", "-") for c in chs)))
        L += [""]
        for v in rep["verdicts"]:
            if v["verdict"] != ELIGIBLE and v["channels"]:
                L.append("- `%s` / `%s`: %s" % (v["model"], v["query"], " | ".join(v["reasons"])[:600]))
    L += ["", "## Not shown", ""] + ["- " + x for x in rep["not_shown"]]
    return "\n".join(L) + "\n"


def graph_svg(rep: dict) -> str:
    """A small layered SVG of the ancestry graph (ancestors left, descendants right)."""
    g = rep["graph"]
    models = [n for n in g["nodes"] if n["type"] == "model"]
    par = {}
    for e in g["ancestry_edges"]:
        par.setdefault(e["child"], []).append(e["parent"])
    depth = {}

    def d(n):
        if n not in depth:
            depth[n] = 0 if not par.get(n) else 1 + max(d(p) for p in par[n])
        return depth[n]
    for m in models:
        d(m["id"])
    cols = {}
    for m in sorted(models, key=lambda n: n["id"]):
        cols.setdefault(depth[m["id"]], []).append(m)
    W, H, cw, rh = 230, 46, 290, 64
    pos = {}
    for x, col in sorted(cols.items()):
        for y, m in enumerate(col):
            pos[m["id"]] = (20 + x * cw, 20 + y * rh)
    width = 40 + (max(cols) + 1) * cw
    height = 40 + max(len(c) for c in cols.values()) * rh
    col = {"VERIFIED": "#1b7f3b", "INFERRED": "#b26a00", "UNVERIFIED": "#888888"}
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;")
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="sans-serif" '
         'font-size="11">' % (width, height + 40),
         '<rect width="100%" height="100%" fill="#ffffff"/>']
    for e in g["ancestry_edges"]:
        (x1, y1), (x2, y2) = pos[e["parent"]], pos[e["child"]]
        dash = "" if e["status"] == "VERIFIED" else ' stroke-dasharray="5 3"'
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2"%s/>'
                 % (x1 + W, y1 + H // 2, x2, y2 + H // 2, col[e["status"]], dash))
        o.append('<text x="%d" y="%d" fill="%s">%s</text>' % ((x1 + W + x2) // 2 - 20,
                 (y1 + y2) // 2 + H // 2 - 3, col[e["status"]], esc(e["kind"])))
    for m in models:
        x, y = pos[m["id"]]
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#f4f6fa" stroke="#334"/>'
                 % (x, y, W, H))
        o.append('<text x="%d" y="%d">%s</text>' % (x + 8, y + 19, esc(m["id"][:34])))
        o.append('<text x="%d" y="%d" fill="#555">%s</text>' % (x + 8, y + 36, esc(m["role"])))
    o.append('<text x="20" y="%d" fill="#333">solid = VERIFIED edge, dashed = INFERRED edge; '
             'edge points from ancestor (left) to descendant (right).</text>' % (height + 30))
    o.append("</svg>")
    return "\n".join(o) + "\n"
