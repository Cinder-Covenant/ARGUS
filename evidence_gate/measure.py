"""Real measurement mode: the actual ARGUS geometry gates run against real files."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pipeline import EvidenceReport, GateResult, REFUSAL, SCHEMA, _safe_argv

_MEASURED_DEFECT_REASONS = ("fall inside the volume", "not one continuous sheet",
                            "sampled voxels are non-fill")


def _classify_refusal(exc) -> str:
    return "FAIL" if any(s in str(exc) for s in _MEASURED_DEFECT_REASONS) else REFUSAL


def measure_mesh(mesh_dir: Path, acquisition: dict[str, Any], *, volume_shape=None,
                 volume_origin_zyx=(0.0, 0.0, 0.0), coord_scale: float = 1.0,
                 volume_url: str | None = None, allow_network: bool = False,
                 chunk_shape=(128, 128, 128), fill_value: float = 0.0, chunk_samples: int = 256,
                 orientation_provenance: str | None = None, orientation_control: str | None = None,
                 command: str = "evidence-gate measure", argv: list[str] | None = None,
                 ) -> EvidenceReport:
    inputs = {"mesh_dir": str(mesh_dir), "volume_url": volume_url,
             "network_permitted": bool(allow_network)}
    argv = _safe_argv(argv or sys.argv)
    now = lambda: datetime.now(timezone.utc).isoformat()

    try:
        from argus.core.contracts import Refusal
        from argus.adapters.published_mesh import PublishedMeshAdapter
    except ImportError as e:
        return EvidenceReport(SCHEMA, now(), REFUSAL, True, False, False, command, argv, inputs,
                              [GateResult("dependency", REFUSAL,
                                          "the argus package is required for real measurement "
                                          "and is not importable: %s" % e)])

    voxel_reader = None
    network_used = False
    reader_note = "chunk-identity gate (#1674) was not measured: no volume access permitted"
    if volume_url:
        is_local = volume_url.startswith("file://")
        if is_local or allow_network:
            try:
                from argus.adapters.zarr_range_reader import ZarrRangeReader
                voxel_reader = ZarrRangeReader(volume_url)
                network_used = not is_local
                reader_note = ("chunk-identity gate measured against %s (%d range request(s) "
                               "to follow)" % ("a local store" if is_local else "a remote store, "
                                                "network explicitly permitted", 0))
            except Exception as e:
                return EvidenceReport(SCHEMA, now(), REFUSAL, True, network_used, False, command,
                                      argv, inputs,
                                      [GateResult("volume_access", REFUSAL,
                                                  "volume store could not be opened: %s" % e)])
        else:
            reader_note = ("chunk-identity gate (#1674) was not measured: %s is remote and "
                           "--allow-network was not given" % volume_url)

    if not mesh_dir.is_dir():
        return EvidenceReport(SCHEMA, now(), REFUSAL, True, network_used, False, command, argv,
                              inputs, [GateResult("local_evidence", REFUSAL,
                                                  "mesh directory is absent: %s" % mesh_dir)])

    ctx = {"mesh_dir": mesh_dir, "acquisition": acquisition,
           "volume_shape": volume_shape or [10**9, 10**9, 10**9],
           "volume_origin_zyx": volume_origin_zyx, "coord_scale": coord_scale,
           "chunk_shape": chunk_shape, "fill_value": fill_value, "chunk_samples": chunk_samples,
           "orientation_provenance": orientation_provenance, "orientation_control": orientation_control}
    if voxel_reader is not None:
        ctx["voxel_reader"] = voxel_reader

    adapter = PublishedMeshAdapter()
    insp = adapter.inspect(ctx)
    if not insp["can_handle"]:
        return EvidenceReport(SCHEMA, now(), REFUSAL, True, network_used, False, command, argv,
                              inputs, [GateResult("preflight", REFUSAL, insp["why_not"])])

    with tempfile.TemporaryDirectory(prefix="evidence-gate-") as td:
        try:
            result = adapter.run(ctx, Path(td))
        except Refusal as e:
            status = _classify_refusal(e)
            gates = [GateResult("measured_geometry", status, str(e))]
            if voxel_reader is None:
                gates.append(GateResult("chunk_identity", "NOT_MEASURED", reader_note))
            return EvidenceReport(SCHEMA, now(), status, True, network_used, False, command, argv,
                                  inputs, gates)

    bundle = result["bundle"]
    gates = [
        GateResult("frame_handshake", "PASS",
                  "%.1f%% of mesh vertices fall inside the declared volume"
                  % (100 * bundle.frame_handshake["vertices_inside_volume"])),
        GateResult("topology", "PASS",
                  "sheet-following: max edge %.2fx median (limit 8x), %.4f%% of edges jump "
                  "(limit 0.10%%)" % (bundle.topology["step_max_ratio"],
                                       100 * bundle.topology["jump_fraction"])),
        GateResult("orientation", "PASS", "%s (%s)" % (bundle.orientation, bundle.orientation_source)),
    ]
    if voxel_reader is not None:
        report = voxel_reader.report()
        gates.append(GateResult(
            "chunk_identity", "PASS",
            "%d chunk(s) touched, %d present, %d never written (fill); %d range request(s) sent"
            % (report["chunks_present"] + report["chunks_missing_count"], report["chunks_present"],
               report["chunks_missing_count"], report["range_requests"])))
    else:
        gates.append(GateResult("chunk_identity", "NOT_MEASURED", reader_note))

    return EvidenceReport(SCHEMA, now(), "PASS", True, network_used, False, command, argv,
                          inputs, gates)
