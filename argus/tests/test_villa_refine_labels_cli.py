"""Guard the real refine-labels CLI spelling found by the September invocation."""
from pathlib import Path

from argus.core.villa_provider_adapter import _argv


def test_refine_labels_optional_flags_match_installed_entrypoint():
    command = _argv("refine_labels", "vesuvius.refine_labels", Path("input"), Path("output"),
                    {"dilation_distance": 3.0, "ridge_threshold": 0.5, "num_workers": 4})
    assert command == ["vesuvius.refine_labels", "input", "output",
                       "--dilation_distance", "3.0", "--ridge_threshold", "0.5",
                       "--num_workers", "4"]
