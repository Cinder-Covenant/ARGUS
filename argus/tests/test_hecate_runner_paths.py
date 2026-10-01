"""The portable Hecate worker reports artifacts relative to ARGUS_REPO."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _runner():
    path = Path(__file__).resolve().parents[2] / "scripts" / "hecate_control_runner.py"
    spec = importlib.util.spec_from_file_location("hecate_control_runner_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_output_paths_follow_configured_artifact_root(tmp_path):
    runner = _runner()
    installed_source = tmp_path / "installed-source"
    configured_repo = tmp_path / "configured-repo"
    output = configured_repo / "artifacts" / "hecate_control_pherc0139_123456789abc" / "prediction.png"
    output.parent.mkdir(parents=True)
    assert runner.repo_artifact_path(output, configured_repo / "artifacts") == (
        "artifacts/hecate_control_pherc0139_123456789abc/prediction.png")
    assert installed_source != configured_repo


def test_output_path_outside_configured_artifact_root_is_refused(tmp_path):
    runner = _runner()
    outside = tmp_path / "elsewhere" / "prediction.png"
    outside.parent.mkdir()
    try:
        runner.repo_artifact_path(outside, tmp_path / "configured" / "artifacts")
    except ValueError as exc:
        assert "outside the configured artifact root" in str(exc)
    else:
        raise AssertionError("an output outside ARGUS_REPO artifacts must be refused")
