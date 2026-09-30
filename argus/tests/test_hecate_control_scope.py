"""The public Hecate execution door admits only its named retained control."""
from __future__ import annotations

import hashlib
import json

from argus.core import hecate_candidate as H


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_retained_control_binding_refuses_substitution(tmp_path, monkeypatch):
    input_path = tmp_path / "control.npy"
    input_path.write_bytes(b"fixed exposed control")
    preparation = tmp_path / "PREPARATION.json"
    preparation.write_text(json.dumps({"input": {"sha256": _sha(input_path)}}), encoding="utf-8")
    runtime = tmp_path / "python.exe"
    runtime.write_bytes(b"runtime")
    provider = tmp_path / "hecate.py"
    provider.write_bytes(b"provider")
    checkpoint = tmp_path / "hecate_9.6um.pth"
    checkpoint.write_bytes(b"weights")
    runtime_receipt = tmp_path / "RUNTIME.json"
    runtime_receipt.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "artifacts"
    outputs.mkdir()

    for name, path in (
        ("_CONTROL_INPUT", input_path), ("_CONTROL_PREPARATION", preparation),
        ("_CONTROL_RUNTIME", runtime), ("_CONTROL_PROVIDER", provider),
        ("_CONTROL_CHECKPOINT", checkpoint), ("_CONTROL_RUNTIME_RECEIPT", runtime_receipt),
    ):
        monkeypatch.setattr(H, name, path)
    monkeypatch.setattr(H, "SOURCE_BLOB_SHA1", H._git_blob_id(provider))
    monkeypatch.setattr(H.paths, "artifact_write_root", lambda: outputs)
    candidate = {"id": "hecate_96um", "artifact": {"sha256": _sha(checkpoint)},
                 "selected_scroll_exposure": "development-exposed"}
    monkeypatch.setattr(H.science_candidates, "inventory", lambda scroll=None: {"candidates": [candidate]})
    monkeypatch.setattr(H.scroll_ids, "resolve", lambda scroll: scroll)

    control = H.control_request()
    assert control["available"]
    plan = H.plan(**control["request"])
    assert H.retained_control_binding(plan)

    wrong_scroll = H.plan(**{**control["request"], "scroll": "PHerc1203"})
    assert H.retained_control_binding(wrong_scroll) is None
    preparation.write_text(json.dumps({"input": {"sha256": "0" * 64}}), encoding="utf-8")
    assert H.retained_control_binding(plan) is None


def test_unconfigured_control_is_not_offered(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "_CONTROL_INPUT", tmp_path / "missing.npy")
    result = H.control_request()
    assert result["available"] is False
    assert "missing.npy" in result["why"]
