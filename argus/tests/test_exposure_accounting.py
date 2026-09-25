"""Public exposure accounting: hermetic, fictional scroll ids, an in-memory survey."""
import copy
import io
import json

import pytest

from argus.core import exposure_accounting as EA
from argus.cli import cmd_exposure

SRC = {"s1": {"url": "https://example.org/card", "retrieved": "2026-01-02"}}


def _vol(scan, um):
    return {"scan_id": scan, "long_id": "%s-%.3fum-1.0m-80keV" % (scan, um), "pixel_size_um": um}


SURVEY = {
    "schema": "argus-public-official-survey-v1", "checked_at": "2026-01-01T00:00:00Z",
    "sources": {"catalogue": {"sha256": "0" * 64}},
    "prize_sets": {"SET_A": {"scrolls": ["PHerc9100"]}},
    "samples": {
        "PHerc9001": {"type": "scroll",
                      "scans": {"20250101000001": {"pixel_size_um": 8.0},
                                "20250101000002": {"pixel_size_um": 2.0}},
                      "volumes": {"20250102000001": _vol("20250101000001", 8.0),
                                  "20250102000002": _vol("20250101000002", 2.0)}},
        "PHerc9002": {"type": "scroll", "scans": {"20250103000001": {}},
                      "volumes": {"20250104000001": _vol("20250103000001", 8.0)}},
        "PHerc9003": {"type": "scroll", "scans": {}, "volumes": {}},
        "PHerc9003B": {"type": "fragment", "scans": {}, "volumes": {}},
        "PHerc9004": {"type": "scroll", "scans": {}, "volumes": {}},
        "PHerc9100": {"type": "scroll", "scans": {}, "volumes": {}},
        "PHerc9100Cr1Fr2": {"type": "fragment", "scans": {}, "volumes": {}},
    },
}


def rec(**kw):
    base = {"schema": EA.RECORD_SCHEMA, "sources": SRC,
            "models": [{"id": "m_ink", "role": "ink_detector"}], "claims": [], "edges": []}
    base.update(kw)
    return base


def clean_claims(model, exposed_direct=(), src="s1", status="VERIFIED"):
    """Every channel stated with a closed set / absence."""
    cl = [{"id": model + "-d", "model": model, "channel": "direct_labels",
           "kind": "exposed_set_complete", "scrolls": list(exposed_direct), "status": status,
           "source": src, "reasons": ["stated"]}]
    for i, ch in enumerate(("teacher_labels", "pseudo_label_lineage", "raw_ct_pretraining")):
        cl.append({"id": "%s-%d" % (model, i), "model": model, "channel": ch, "kind": "absent",
                   "scroll": "*", "status": status, "source": src, "reasons": ["stated"]})
    return cl


def acc(r):
    return EA.Accounting(r, SURVEY)


def test_all_verified_absent_is_eligible():
    v = acc(rec(claims=clean_claims("m_ink", ["PHerc9002"]))).verdict("m_ink", "PHerc9001")
    assert v["verdict"] == EA.ELIGIBLE
    assert all(c["state"] == "CLEAN" for c in v["channels"].values())


def test_missing_record_is_unverified_and_not_eligible():
    v = acc(rec()).verdict("m_ink", "PHerc9001")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert {c["state"] for c in v["channels"].values()} == {"UNVERIFIED"}
    assert "default UNVERIFIED" in " ".join(v["reasons"])


@pytest.mark.parametrize("name", ["20250102000002", "20250101000002",
                                  "seg7-on-20250102000002-2.000um.tifxyz",
                                  "https://example.org/PHerc9001/volumes/20250102000002-2.000um.zarr/",
                                  "PHerc9001", "pherc_9001"])
def test_rescan_resolution_alias_and_ids_leak_into_one_scroll(name):
    """Exposure recorded on the 2 um rescan (by any of its names) makes the scroll not held out."""
    v = acc(rec(claims=clean_claims("m_ink", [name]))).verdict("m_ink", "PHerc9001")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert v["channels"]["direct_labels"]["state"] == "EXPOSED"
    assert v["exposure_eligibility"] == "DEVELOPMENT_ONLY"


def test_exposed_rescan_query_by_volume_id():
    a = acc(rec(claims=clean_claims("m_ink", ["PHerc9001"])))
    v = a.verdict("m_ink", "20250102000001")
    assert v["verdict"] == EA.NOT_ELIGIBLE and v["physical_scroll"] == "PHerc9001"


def test_fragment_or_sibling_exposure_blocks_as_inferred_never_verified():
    v = acc(rec(claims=clean_claims("m_ink", ["PHerc9003B"]))).verdict("m_ink", "PHerc9003")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    ch = v["channels"]["direct_labels"]
    assert ch["state"] == "EXPOSURE_POSSIBLE"
    assert "may be the same physical object" in ch["reasons"][0]
    assert v["channels"]["teacher_labels"]["state"] == "CLEAN"


def test_unresolved_name_blocks_fail_closed():
    v = acc(rec(claims=clean_claims("m_ink", ["Mystery Scroll Q"]))).verdict("m_ink", "PHerc9001")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert v["channels"]["direct_labels"]["state"] == "UNVERIFIED"
    assert "resolves to no physical scroll" in " ".join(v["reasons"])


def test_ambiguous_provenance_is_inferred_never_verified():
    v = acc(rec(claims=clean_claims("m_ink", [], status="INFERRED"))).verdict("m_ink", "PHerc9001")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert {c["state"] for c in v["channels"].values()} == {"ABSENT_INFERRED"}


def test_verified_without_citation_is_downgraded_with_a_finding():
    a = acc(rec(claims=clean_claims("m_ink", [], src="nope")))
    assert a.rec["findings"] and "without a cited https source" in a.rec["findings"][0]
    assert a.verdict("m_ink", "PHerc9001")["verdict"] == EA.NOT_ELIGIBLE


def test_inferred_alias_makes_exposure_inferred_but_still_blocking():
    r = rec(claims=clean_claims("m_ink", ["Scroll Nine-Two"]),
            identity_aliases=[{"name": "Scroll Nine-Two", "scroll": "PHerc9002", "status": "INFERRED",
                               "reasons": ["only one scroll carries that number"]}])
    v = acc(r).verdict("m_ink", "PHerc9002")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert v["channels"]["direct_labels"]["exposed_by"][0]["status"] == "INFERRED"


def _lineage_record():
    models = [{"id": "child_a", "role": "ink_detector"}, {"id": "child_b", "role": "ink_detector"},
              {"id": "teacher", "role": "teacher"}, {"id": "lonely", "role": "ink_detector"},
              {"id": "surface", "role": "surface_provider"}]
    claims = clean_claims("child_a") + clean_claims("child_b") + clean_claims("lonely")
    claims += [{"id": "t-direct", "model": "teacher", "channel": "direct_labels", "kind": "exposed",
                "scroll": "PHerc9004", "status": "VERIFIED", "source": "s1"}]
    edges = [{"child": "child_a", "parent": "teacher", "kind": "TEACHER", "status": "VERIFIED",
              "source": "s1"},
             {"child": "child_b", "parent": "teacher", "kind": "PSEUDO_SOURCE", "status": "VERIFIED",
              "source": "s1"}]
    return rec(models=models, claims=claims, edges=edges)


def test_shared_teacher_lineage_joins_components_and_wording():
    a = acc(_lineage_record())
    assert a.components()[0]["members"] == ["child_a", "child_b", "teacher"]
    s = a.lineage_summary()["verified_edges"]
    assert s["joined_entries"] == 3 and s["joined_ink_detectors"] == 2
    assert s["sentence"].startswith("3 of 5 registered entries joined the same lineage component")
    assert "1 teacher" in s["sentence"]
    assert "contaminated" not in s["sentence"]
    assert "not evidence of independence" in s["sentence"]


def test_teacher_exposure_flows_to_children_on_the_named_channel():
    a = acc(_lineage_record())
    va, vb = a.verdict("child_a", "PHerc9004"), a.verdict("child_b", "PHerc9004")
    assert va["channels"]["teacher_labels"]["state"] == "EXPOSED"
    assert vb["channels"]["pseudo_label_lineage"]["state"] == "EXPOSED"
    assert va["channels"]["teacher_labels"]["exposed_by"][0]["path"] == ["child_a", "teacher"]
    assert a.verdict("lonely", "PHerc9004")["verdict"] == EA.ELIGIBLE


def test_inferred_edge_joins_only_at_the_weaker_strength():
    r = _lineage_record()
    r["edges"][1]["status"] = "INFERRED"
    r["edges"][1]["reasons"] = ["file name suggests it"]
    lin = acc(r).lineage_summary()
    assert lin["verified_edges"]["joined_entries"] == 2
    assert lin["verified_and_inferred_edges"]["joined_entries"] == 3


def test_ancestor_without_record_blocks_children():
    r = _lineage_record()
    r["edges"].append({"child": "lonely", "parent": "surface", "kind": "INIT", "status": "VERIFIED",
                       "source": "s1"})
    v = acc(r).verdict("lonely", "PHerc9001")
    assert v["verdict"] == EA.NOT_ELIGIBLE
    assert v["channels"]["raw_ct_pretraining"]["state"] == "UNVERIFIED"


def test_cycle_refused():
    r = _lineage_record()
    r["edges"].append({"child": "teacher", "parent": "child_a", "kind": "INIT", "status": "VERIFIED",
                       "source": "s1"})
    with pytest.raises(EA.RecordError, match="cycle"):
        acc(r)


def test_prize_set_scroll_refused_and_masked():
    a = acc(rec(claims=clean_claims("m_ink", ["PHerc9100"])))
    v = a.verdict("m_ink", "PHerc9100")
    assert v["verdict"] == EA.NOT_EVALUATED and v["channels"] == {}
    assert "PHerc9100" not in json.dumps(v)
    rep = json.dumps(a.report(["PHerc9100", "PHerc9001"]))
    assert "PHerc9100" not in rep.replace("PHerc9100Cr1Fr2", "")
    assert "not evaluated here" in rep


def test_scroll_sharing_stem_with_prize_scroll_is_not_eligible():
    v = acc(rec(claims=clean_claims("m_ink"))).verdict("m_ink", "PHerc9100Cr1Fr2")
    assert v["verdict"] == EA.NOT_ELIGIBLE and "prize-set scroll" in " ".join(v["reasons"])
    assert "PHerc9100 " not in " ".join(v["reasons"])


def test_deterministic_and_schema_round_trip():
    r = _lineage_record()
    a = json.dumps(acc(r).report(["PHerc9004", "PHerc9001"]), sort_keys=True)
    b = json.dumps(acc(copy.deepcopy(r)).report(["PHerc9004", "PHerc9001"]), sort_keys=True)
    assert a == b
    rep = json.loads(a)
    assert rep["schema"] == EA.REPORT_SCHEMA and rep["record_schema"] == EA.RECORD_SCHEMA
    assert json.loads(json.dumps(rep, sort_keys=True)) == rep
    assert rep["verdicts"][0]["channels"]["teacher_labels"]["exposure_state"] in (
        "EXPOSED", "CLEAN", "UNKNOWN")
    assert EA.to_markdown(rep) == EA.to_markdown(json.loads(a))
    assert EA.graph_svg(rep).startswith("<svg")


def test_bad_schema_and_unknown_model_refused():
    with pytest.raises(EA.RecordError):
        acc({"schema": "other"})
    r = rec(claims=[{"id": "x", "model": "ghost", "channel": "direct_labels", "kind": "absent",
                     "scroll": "*"}])
    with pytest.raises(EA.RecordError, match="unknown model"):
        acc(r)


def test_cli_check_report_and_prize_exit(tmp_path, monkeypatch):
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(_lineage_record()), encoding="utf-8")
    monkeypatch.setattr(EA, "load_survey", lambda *a, **k: SURVEY)
    out = io.StringIO()
    assert cmd_exposure.run(["check", str(p), "--model", "lonely", "--scroll", "PHerc9001"],
                            out=out) == 0
    assert "ELIGIBLE_AS_HELD_OUT" in out.getvalue()
    out = io.StringIO()
    assert cmd_exposure.run(["check", str(p), "--model", "child_a", "--scroll", "PHerc9004",
                             "--json"], out=out) == 1
    assert json.loads(out.getvalue())["verdict"] == "NOT_ELIGIBLE"
    out = io.StringIO()
    assert cmd_exposure.run(["check", str(p), "--model", "child_a", "--scroll", "PHerc9100"],
                            out=out) == 1
    assert "NOT_EVALUATED_HERE" in out.getvalue()
    out = io.StringIO()
    assert cmd_exposure.run(["report", str(p), "--scroll", "PHerc9004"], out=out) == 0
    assert "joined the same lineage component" in out.getvalue()
    assert cmd_exposure.run(["check", str(p), "--model", "nope", "--scroll", "PHerc9001"],
                            out=io.StringIO()) == 2


def test_dispatcher_knows_exposure():
    from argus.cli import main
    assert main._dispatch("exposure") is cmd_exposure.run


def _example_dir():
    from pathlib import Path
    here = Path(__file__).resolve()
    for root in here.parents:
        for rel in ("docs/exposure_example",
                    "docs/release/public_export/overlay/docs/exposure_example"):
            if (root / rel / "EXAMPLE_RECORD.json").is_file():
                return root / rel
    return None


def test_shipped_real_data_example_regenerates_from_its_record():
    d = _example_dir()
    if d is None:
        pytest.skip("example directory not present in this checkout")
    rec = d / "EXAMPLE_RECORD.json"
    q = []
    for s in ("PHerc0139", "PHerc0814", "PHerc0009B", "PHerc0841", "PHerc0332", "PHerc0172"):
        q += ["--scroll", s]
    assert cmd_exposure.run(["validate", str(rec)], out=io.StringIO()) == 0
    out = io.StringIO()
    assert cmd_exposure.run(["report", str(rec)] + q + ["--json"], out=out) == 0
    fresh = json.loads(out.getvalue())
    shipped = json.loads((d / "EXAMPLE_EXPOSURE.json").read_text(encoding="utf-8"))
    assert fresh == shipped
    verdicts = [v["verdict"] for v in shipped["verdicts"]]
    assert len(verdicts) == 54
    assert set(verdicts) == {EA.NOT_ELIGIBLE}
    md = io.StringIO()
    assert cmd_exposure.run(["report", str(rec)] + q, out=md) == 0
    assert md.getvalue().replace("\r\n", "\n") == (d / "EXAMPLE_REPORT.md").read_text(encoding="utf-8").replace("\r\n", "\n")
