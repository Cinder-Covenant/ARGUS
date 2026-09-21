from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence_gate.pipeline import REFUSAL, check_saved_mesh, evaluate_payload, write_receipt

pytest.importorskip("argus.core.contracts", reason="measured-mode tests need the argus package")
pytest.importorskip("tifffile", reason="measured-mode tests need tifffile")

from evidence_gate.measure import measure_mesh
from evidence_gate_fixtures.build_measured import build as build_measured


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "evidence_gate_fixtures"


def test_fixture_corpus_matches_expected_verdicts() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["fixtures"]:
        payload = json.loads((FIXTURES / f"{item['name']}.json").read_text(encoding="utf-8"))
        assert evaluate_payload(payload).status == item["expected"]


def test_remote_volume_is_refused_without_network() -> None:
    report = check_saved_mesh(FIXTURES / "clean.json", "s3://private/volume.zarr")
    assert report.status == REFUSAL
    assert report.network_used is False
    assert report.gates[0].name == "local_evidence"


def test_missing_measurement_refuses_instead_of_guessing() -> None:
    report = evaluate_payload({"mesh_bbox": [0, 0, 0], "volume_bounds": [1, 1, 1], "mesh_contained": True})
    assert report.status == REFUSAL
    assert any(g.status == REFUSAL for g in report.gates)


def test_receipt_records_command_and_redacts_credentials(tmp_path: Path) -> None:
    report = evaluate_payload(
        json.loads((FIXTURES / "clean.json").read_text(encoding="utf-8")),
        command="evidence-gate check",
        argv=["evidence-gate", "check", "--api-key", "do-not-write-this"],
    )
    receipt = tmp_path / "receipt.json"
    write_receipt(report, receipt)
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    assert saved["command"] == "evidence-gate check"
    assert "do-not-write-this" not in receipt.read_text(encoding="utf-8")
    assert saved["argv"][-1] == "<redacted>"



def test_measured_clean_mesh_passes_every_gate_including_chunk_identity(tmp_path: Path) -> None:
    manifest = build_measured(tmp_path)
    m = manifest["cases"]["clean"]["manifest"]
    report = measure_mesh(Path(m["mesh_dir"]), m["acquisition"], volume_shape=m["volume_shape"],
                          volume_url=m["volume_url"], chunk_shape=tuple(m["chunk_shape"]),
                          orientation_provenance=m["orientation_provenance"])
    assert report.status == "PASS"
    names = {g.name: g.status for g in report.gates}
    assert names["frame_handshake"] == "PASS"
    assert names["topology"] == "PASS"
    assert names["chunk_identity"] == "PASS"
    assert report.network_used is False


def test_measured_mesh_outside_volume_fails_citing_1660(tmp_path: Path) -> None:
    manifest = build_measured(tmp_path)
    m = manifest["cases"]["mesh_outside_volume"]["manifest"]
    report = measure_mesh(Path(m["mesh_dir"]), m["acquisition"], volume_shape=m["volume_shape"],
                          orientation_provenance=m["orientation_provenance"])
    assert report.status == "FAIL"
    assert any("#1660" in g.reason for g in report.gates)


def test_measured_seam_across_sheet_fails_citing_1675(tmp_path: Path) -> None:
    manifest = build_measured(tmp_path)
    m = manifest["cases"]["seam_across_sheet"]["manifest"]
    report = measure_mesh(Path(m["mesh_dir"]), m["acquisition"], volume_shape=m["volume_shape"],
                          orientation_provenance=m["orientation_provenance"])
    assert report.status == "FAIL"
    assert any("#1675" in g.reason for g in report.gates)


def test_measured_all_fill_fails_citing_1674(tmp_path: Path) -> None:
    manifest = build_measured(tmp_path)
    m = manifest["cases"]["all_fill"]["manifest"]
    report = measure_mesh(Path(m["mesh_dir"]), m["acquisition"], volume_shape=m["volume_shape"],
                          volume_url=m["volume_url"], chunk_shape=tuple(m["chunk_shape"]),
                          orientation_provenance=m["orientation_provenance"])
    assert report.status == "FAIL"
    assert any("#1674" in g.reason for g in report.gates)


def test_measured_remote_volume_is_not_read_without_allow_network(tmp_path: Path) -> None:
    manifest = build_measured(tmp_path)
    m = manifest["cases"]["clean"]["manifest"]
    report = measure_mesh(Path(m["mesh_dir"]), m["acquisition"], volume_shape=m["volume_shape"],
                          volume_url="https://example.invalid/volume.zarr",
                          orientation_provenance=m["orientation_provenance"])
    assert report.network_used is False
    names = {g.name: g.status for g in report.gates}
    assert names["frame_handshake"] == "PASS"
    assert names["chunk_identity"] == "NOT_MEASURED"
