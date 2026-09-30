"""Process status and a hidden subprocess runner for local resource probes.

CPU time divided by elapsed time can help distinguish active computation from
a stalled job. Low CPU usage alone does not establish failure, especially for
network-bound work, so callers must report uncertainty.
"""
from __future__ import annotations

def run_hidden(cmd, timeout=20, cwd=None):
    """Run a subprocess with NO console window, two ways.

    Repeated status probes must not open visible consoles or steal focus.

    CREATE_NO_WINDOW alone is not reliable here: some launchers (wsl.exe, and
    anything that re-execs) still flash. STARTUPINFO with SW_HIDE closes that,
    and setting both is cheap.

    BOTH Windows-only arguments are gated, not just one. `startupinfo` was
    guarded by `hasattr(_sp, "STARTUPINFO")` while `creationflags` was passed
    unconditionally, so on Linux every call raised
    `ValueError: creationflags is only supported on Windows platforms`.

    That is not cosmetic. `resource_guard.free_vram_gb()` runs `nvidia-smi`
    through here and swallows exceptions, so on Linux it returned **0.0** --
    and 0.0 is the guard's "probe unreadable" sentinel, which admission refuses
    and the runtime VRAM watchdog treats as fatal. The first Linux run would
    have been killed by its own safety net, reporting a memory problem that did
    not exist. Found on the RunPod A40 the moment the guard was asked to read a
    real box.
    """
    import subprocess as _sp

    kwargs = {}
    if hasattr(_sp, "STARTUPINFO"):             # Windows only
        si = _sp.STARTUPINFO()
        si.dwFlags |= _sp.STARTF_USESHOWWINDOW
        si.wShowWindow = 0                      # SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = 0x08000000    # CREATE_NO_WINDOW
    return _sp.run(cmd, capture_output=True, text=True, timeout=timeout,
                   cwd=cwd, encoding="utf-8", errors="replace", **kwargs)


import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def _ps() -> list[dict]:
    """Live python processes with CPU seconds and wall minutes."""
    ps = (
        "Get-Process python -ErrorAction SilentlyContinue | "
        "ForEach-Object { [PSCustomObject]@{ id=$_.Id; cpu=[math]::Round($_.CPU,0); "
        "ws=[math]::Round($_.WorkingSet64/1GB,2); "
        "min=[math]::Round(((Get-Date)-$_.StartTime).TotalMinutes,1) } } | ConvertTo-Json"
    )
    try:
        out = run_hidden(["powershell", "-NoProfile", "-Command", ps], timeout=30).stdout.strip()
        if not out:
            return []
        d = json.loads(out)
        return d if isinstance(d, list) else [d]
    except Exception:
        return []


def _gpu() -> tuple[float, float]:
    try:
        r = run_hidden(["nvidia-smi", "--query-gpu=memory.used,memory.free",
             "--format=csv,noheader,nounits"], timeout=10)
        u, f = r.stdout.strip().splitlines()[0].split(",")
        return float(u) / 1024, float(f) / 1024
    except Exception:
        return 0.0, 0.0


DIM, OK, BAD, ACC = "#7b8496", "#4ec9a0", "#e05561", "#5aa9e6"


def verdict(cpu_s: float, wall_min: float, gpu_held: bool) -> tuple[str, str]:
    """WORKING / STALLED / IDLE-ish, from CPU-over-wall. Returns (text, colour).

    THE ONE HOME for this classifier. `status_ui.py` imports it rather than
    keeping its own copy: two definitions of "stalled" is how a monitor starts
    disagreeing with itself, and a monitor you cannot trust is worse than none.
    """
    if wall_min < 0.5:
        return "STARTING", DIM
    ratio = cpu_s / (wall_min * 60.0)
    if ratio >= 0.15:
        return f"WORKING {ratio:.0%}", OK
    if ratio >= 0.05:
        return f"io-bound {ratio:.0%}", ACC
    if gpu_held:
        # The dangerous case: holding a scarce resource without using it.
        return f"STALLED? {ratio:.0%}", BAD
    return f"waiting {ratio:.0%}", DIM


def recent_artifacts(minutes: int = 30) -> list[tuple[str, float]]:
    """Files written recently -- proof that something is producing output."""
    cutoff = time.time() - minutes * 60
    out = []
    for base in (REPO / "artifacts", Path("T:/vesuvius-cache/spiral-dataset")):
        if not base.exists():
            continue
        try:
            for p in base.rglob("*"):
                if p.is_file() and p.stat().st_mtime > cutoff:
                    out.append((str(p.relative_to(base.parent) if base.parent in p.parents
                                    else p.name), p.stat().st_mtime))
                    if len(out) > 4000:
                        break
        except Exception:
            pass
    return sorted(out, key=lambda t: -t[1])[:6]


def main() -> int:
    procs = _ps()
    used, free = _gpu()
    gpu_held = used > 1.0

    print("=" * 62)
    print("  VESUVIUS STATUS")
    print("=" * 62)

    try:
        import resource_guard as g
        lock = g._read_lock()
        print(f"  RAM free   {g.free_ram_gb():5.1f} GB")
        print(f"  VRAM       {used:5.2f} GB used / {free:.2f} GB free")
        if lock:
            alive = g._pid_alive(int(lock.get("pid", -1)))
            print(f"  guard lock {lock.get('job')} (pid {lock.get('pid')}) "
                  f"{'ALIVE' if alive else 'STALE -- run: python scripts/resource_guard.py --reap'}")
        else:
            print("  guard lock none")
    except Exception as exc:
        print(f"  guard      unavailable: {exc}")

    print("-" * 62)
    real = [p for p in procs if p.get("min", 0) > 0.2]
    if not real:
        print("  NOTHING RUNNING")
    else:
        print(f"  {'pid':>6} {'cpu_s':>7} {'wall_m':>7} {'ws_gb':>6}  verdict")
        for p in sorted(real, key=lambda x: -x.get("cpu", 0)):
            v = verdict(p.get("cpu", 0), p.get("min", 0), gpu_held)[0]
            print(f"  {p['id']:>6} {p.get('cpu',0):>7.0f} {p.get('min',0):>7.1f} "
                  f"{p.get('ws',0):>6.2f}  {v}")

    print("-" * 62)
    ra = recent_artifacts()
    if ra:
        print("  recent output (last 30 min):")
        for name, mt in ra:
            print(f"    {time.strftime('%H:%M:%S', time.localtime(mt))}  {name[:52]}")
    else:
        print("  NO FILES WRITTEN IN 30 MIN -- if a job claims to be running, "
              "it is not producing")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
