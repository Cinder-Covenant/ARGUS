"""Three retained runtime-isolation regressions; mocked inventory, no CT or service access."""
from argus.core import scroll_shelf as SHELF

def test_default_composition_cannot_borrow_a_neighboring_runtime(monkeypatch):
    local = {"source": "in_process_authorities", "scrolls": []}
    calls = []
    monkeypatch.setattr(SHELF, "compose_local", lambda: local)
    monkeypatch.setattr(SHELF, "compose", lambda base: calls.append(base) or {
        "source": "neighbor", "scrolls": [{"scroll": "PHercFixture", "held": True}]})
    assert SHELF.compose_available() == local
    assert calls == []

def test_explicit_composition_retains_the_selected_remote(monkeypatch):
    calls = []
    remote = {"source": "explicit", "scrolls": []}
    monkeypatch.setattr(SHELF, "_SERVICE_RETRY_AFTER", {})
    monkeypatch.setattr(SHELF, "compose", lambda base: calls.append(base) or remote)
    assert SHELF.compose_available("http://127.0.0.1:19306") == remote
    assert calls == ["http://127.0.0.1:19306"]

def test_explicit_unavailable_service_falls_back_to_this_runtime(monkeypatch):
    local = {"source": "in_process_authorities", "scrolls": []}
    def unavailable(base):
        raise SHELF.ShelfError("unavailable")
    monkeypatch.setattr(SHELF, "_SERVICE_RETRY_AFTER", {})
    monkeypatch.setattr(SHELF, "compose", unavailable)
    monkeypatch.setattr(SHELF, "compose_local", lambda: local)
    assert SHELF.compose_available("http://127.0.0.1:19306") == local
