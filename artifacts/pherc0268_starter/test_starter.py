"""Synthetic-only integration tests; no CT/remote reads or inference."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import zarr
import common
import load_local
import reconstruct

HERE = Path(__file__).resolve().parent


def fixture_entry(root):
    # Independent synthetic voxel value: encode each axis distinctly.
    name = "seed1_020202_z7413_y6773_x4566.zarr"
    field = root / name
    kwargs = ({"config": {"write_empty_chunks": True}, "zarr_format": 2}
              if int(zarr.__version__.split(".")[0]) >= 3
              else {"write_empty_chunks": True, "zarr_version": 2})
    arr = zarr.open_array(str(field), mode="w", shape=(128,) * 3, chunks=(64,) * 3,
                          dtype="uint8", order="C", **kwargs)
    values = np.fromfunction(lambda z, y, x: (z + 3 * y + 5 * x) % 256,
                             (128,) * 3, dtype=np.int32).astype(np.uint8)
    arr[:] = values
    entry = {"name": name, "anchor": "seed1", "grid_index_zyx": [2, 2, 2],
             "center_zyx": [7413, 6773, 4566], "origin_zyx": [7349, 6709, 4502],
             "stop_zyx_exclusive": [7477, 6837, 4630], "shape_zyx": [128] * 3,
             "chunks_zyx": [64] * 3, "dtype": "uint8",
             "files": [{"path": p.name, "bytes": p.stat().st_size, "sha256": common.sha256(p)}
                       for p in sorted(field.iterdir())]}
    return entry


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-test-", dir=HERE)
        self.root = Path(self.temp.name)
        self.entry = fixture_entry(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_hand_calculated_coordinates_and_axes(self):
        c = common.coordinates(self.entry["name"])
        self.assertEqual(c["origin_zyx"], [7349, 6709, 4502])
        self.assertEqual(c["stop_zyx_exclusive"], [7477, 6837, 4630])
        data, where = load_local.load_crop(self.root, self.entry, (17, 29, 41))
        self.assertEqual(int(data[2, 3, 4]), (19 + 3 * 32 + 5 * 45) % 256)
        self.assertEqual(where["origin_zyx"], [7366, 6738, 4543])
        self.assertEqual(where["stop_zyx_exclusive"], [7430, 6802, 4607])
        self.assertEqual(where["axes"], "ZYX")

    def test_wrong_filename_coordinates_refused(self):
        for name in ["seed1_020202_z4566_y6773_x7413.zarr", "../" + self.entry["name"],
                     "seed1_990202_z7413_y6773_x4566.zarr"]:
            with self.assertRaises(ValueError):
                common.coordinates(name)

    def test_crop_boundaries_and_normalization(self):
        for offset in [(-1, 0, 0), (0, 65, 0), (0, 0), (0.5, 0, 0)]:
            with self.assertRaises(ValueError):
                load_local.load_crop(self.root, self.entry, offset)
        data, _ = load_local.load_crop(self.root, self.entry, (64, 64, 64), normalize=True)
        self.assertAlmostEqual(float(data.mean()), 0, places=5)
        self.assertAlmostEqual(float(data.std()), 1, places=5)

    def test_metadata_refuses_shape_and_missing_chunk(self):
        field = self.root / self.entry["name"]
        metadata = field / ".zarray"
        original = metadata.read_text()
        metadata.write_text(original.replace("128", "127", 1))
        with self.assertRaises(ValueError):
            load_local.inspect_field(self.root, self.entry)
        metadata.write_text(original)
        (field / "1.1.1").unlink()
        with self.assertRaises(ValueError):
            load_local.inspect_field(self.root, self.entry)

    def test_hash_corruption_refused_without_decode(self):
        field = self.root / self.entry["name"] / "0.0.0"
        data = bytearray(field.read_bytes())
        data[-1] ^= 1
        field.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            load_local.inspect_field(self.root, self.entry, verify_hashes=True)

    def test_root_escape_and_fresh_output(self):
        for name in ["../outside", str(self.root / "absolute.zarr"), "x/y"]:
            with self.assertRaises(ValueError):
                common.child_path(self.root, name)
        with self.assertRaises(ValueError):
            common.fresh_output(self.root)
        with self.assertRaises(ValueError):
            common.fresh_output(self.root / ".." / "escape")
        self.assertEqual(common.fresh_output(self.root / "fresh"), self.root / "fresh")

    def test_source_chunk_estimate_known_unaligned_cube(self):
        plan = common.access_plan([self.entry])
        self.assertEqual(plan["unique_source_chunks"], 8)
        self.assertEqual(plan["output_uncompressed_bytes"], 2097152)
        self.assertEqual(plan["source_chunk_uncompressed_bytes"], 16777216)

    def test_manifest_provenance_and_count_tamper_refused(self):
        original = common.read_manifest(HERE / "pherc0268_manifest.json")
        self.assertEqual(len(original["entries"]), 342)
        for edit in ["axes", "coordinates", "count"]:
            changed = copy.deepcopy(original)
            if edit == "axes":
                changed["source"]["axes"] = "XYZ"
            elif edit == "coordinates":
                changed["entries"][0]["origin_zyx"][0] += 1
            else:
                changed["retained_field_count"] = 341
            path = self.root / "bad.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                common.read_manifest(path)

    def test_dry_run_never_opens_source(self):
        with patch.object(reconstruct, "open_remote", side_effect=AssertionError("network prohibited")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                reconstruct.main([])
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["fields"], 24)

    def test_fetch_ack_output_and_caps_refuse_before_network(self):
        scenarios = [["--allow-source-fetch"],
                     ["--allow-source-fetch", "--acknowledge-source-terms", "--output", str(self.root)],
                     ["--max-fields", "23"], ["--max-source-uncompressed-bytes", "1"],
                     ["--max-source-chunk-requests", "191"], ["--all"]]
        with patch.object(reconstruct, "open_remote", side_effect=AssertionError("network prohibited")):
            for argv in scenarios:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        reconstruct.main(argv)

    def test_mock_original_host_slices_and_fresh_receipt(self):
        entry = self.entry
        class SyntheticSource:
            shape = common.SOURCE_SHAPE
            chunks = (128,) * 3
            dtype = np.dtype("uint8")
            def __getitem__(self, slices):
                expected = [(7349, 7477), (6709, 6837), (4502, 4630)]
                if [(s.start, s.stop) for s in slices] != expected:
                    raise AssertionError("ZYX slice mismatch")
                return np.zeros((128,) * 3, dtype=np.uint8)
        manifest = common.read_manifest(HERE / "pherc0268_manifest.json")
        output = common.fresh_output(self.root / "mock-reconstruction")
        with patch.object(reconstruct, "open_remote", return_value=SyntheticSource()):
            with contextlib.redirect_stdout(io.StringIO()):
                reconstruct.execute([entry], manifest, output)
        rebuilt = common.read_manifest(output / "local_manifest.json")
        data, _ = load_local.load_crop(output, rebuilt["entries"][0], normalize=True)
        self.assertTrue(np.all(data == 0))

    def test_selection_count_balance_identity(self):
        manifest = common.read_manifest(HERE / "pherc0268_manifest.json")
        entries = common.select_entries(manifest, HERE / "sampler_24.json")
        self.assertEqual(len(entries), 24)
        self.assertEqual({a: sum(e["anchor"] == a for e in entries) for a in common.ANCHORS_XYZ},
                         {"seed1": 8, "seed2": 8, "g16": 8})
        selection = json.loads((HERE / "sampler_24.json").read_text())
        self.assertEqual(selection["manifest_sha256"], common.sha256(HERE / "pherc0268_manifest.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
