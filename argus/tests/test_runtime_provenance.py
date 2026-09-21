"""/api/runtime names the source a tree was built from, and a declared-optional torch is not an error."""
from __future__ import annotations

import builtins
import json

from fastapi.testclient import TestClient

from argus.service import app as A


def _tree(tmp_path, *, provenance: bool, torch_optional: bool):
    (tmp_path / "runtime").mkdir()
    lock = b"# test lock\nnumpy==1.0\n"
    (tmp_path / "runtime" / "requirements.lock.txt").write_bytes(lock)
    import hashlib
    (tmp_path / "runtime" / "RUNTIME_FREEZE.json").write_text(json.dumps({
        "python": {"version": "0.0.0"},
        "torch": {"version": None, "optional": torch_optional},
        "lockfile": {"sha256": hashlib.sha256(lock).hexdigest(), "n_packages": 1}}), encoding="utf-8")
    if provenance:
        (tmp_path / "SOURCE_PROVENANCE.json").write_text(json.dumps({"source_revision": "abc123def"}), encoding="utf-8")


def _runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "ROOT", tmp_path)
    A._RUNTIME_MEMO.clear()
    real_import = builtins.__import__

    def no_torch(name, *a, **k):
        if name == "torch":
            raise ModuleNotFoundError("No module named 'torch'")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_torch)
    return TestClient(A.app).get("/api/runtime").json()


def test_an_export_reports_the_source_revision_it_was_built_from(monkeypatch, tmp_path):
    _tree(tmp_path, provenance=True, torch_optional=True)
    d = _runtime(monkeypatch, tmp_path)
    assert d["service_identity"]["source_revision"] == "abc123def"
    assert d["service_identity"]["source_provenance"] == "SOURCE_PROVENANCE.json"


def test_a_declared_optional_torch_that_is_absent_is_not_an_error(monkeypatch, tmp_path):
    _tree(tmp_path, provenance=False, torch_optional=True)
    d = _runtime(monkeypatch, tmp_path)
    assert d["torch"]["optional"] is True and d["torch"]["error"] is None and d["torch"]["matches"] is True
    assert d["service_identity"]["source_provenance"] == "this tree is the source checkout"


def test_an_undeclared_missing_torch_is_still_reported(monkeypatch, tmp_path):
    _tree(tmp_path, provenance=False, torch_optional=False)
    d = _runtime(monkeypatch, tmp_path)
    assert d["torch"]["optional"] is False and "ModuleNotFoundError" in (d["torch"]["error"] or "")
