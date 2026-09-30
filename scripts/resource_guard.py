"""Resource admission, single-flight locking and owned-process cleanup.

Heavy callers use ``admit`` before allocation. The guard reads available RAM
from the OS, refuses concurrent holders of its PID-bearing lock, and installs
cleanup for the job's owned processes. A stale lock is reclaimed only after
its holder is verified absent. These mechanisms complement the Hecate job's
whole-GPU, temperature and disk sampling in ``hecate_candidate``.
"""
from __future__ import annotations

import atexit
import json
import os
import platform
import re
import signal
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

# THIS IMPORT WAS MISSING AND EVERY GUARD BELOW DEPENDED ON IT. `run_hidden` was
# called in four places -- the VRAM probe, the total-VRAM probe, the macOS RAM
# probe, and the Windows liveness probe -- and was never imported, so each call
# raised NameError straight into the `except Exception: pass` written to absorb
# a missing binary. The visible effect was not a crash, it was silent zeros:
# `free_vram_gb()` returned 0.0 on a working card, so `check()`'s VRAM branch
# (`fv > 0.0 and ...`) NEVER RAN, and `_pid_alive()` returned False for every
# live process, so the single-flight lock treated a running holder as stale and
# broke it. Both of the mechanisms that were supposed to stop two GPU jobs
# overlapping had been dead since they were written. This one line is the
# actual cause of N-215 and N-217's starved card; the aggregate view below is
# the second layer, not the fix.
from status import run_hidden  # noqa: E402 -- ONE home for the hidden runner

sys.path.insert(0, str(REPO / "src"))
# Pulled from Determinex's `hive/thermal.py` at the operator's direction rather
# than written again here: multi-source (nvidia-smi, rocm-smi, psutil, WMI) with
# a pause/abort control flow already in production there. Two things were fixed
# on the way in, both the same defect this file was carrying: its CPU-usage
# reader was psutil-only and psutil is NOT in this venv, so it returned a hard
# 0% and the CPU protections could never fire; and its GPU limits were
# hand-picked constants, now read from the card's own published target /
# max-operating / slowdown / shutdown temperatures.
from argus.core import hecate_thermal as thermal  # noqa: E402
LOCK = REPO / "artifacts" / ".resource_guard.lock"

#: HEADROOM FOR GROWTH, and only that -- derived from measurement rather than
#: typed, which is the standard the VRAM floor below already meets and this
#: constant did not.
#:
#: The old value was 6.0 GB "held back for the OS, the editor, and whatever else
#: the operator is running", and that rationale double-counts. It is subtracted
#: from `free_ram_gb()`, which reads `ullAvailPhys` -- a figure that ALREADY
#: excludes every running process. While the operator's own 17-process archive
#: upload held ~6 GB, available read 6.38 GB: the upload was already gone from
#: the number, and reserving another 6 GB for it charged the same memory twice.
#: The consequence was not theoretical -- a 1.5 GB probe was refused on a 31.8 GB
#: box with 6.4 GB genuinely free.
#:
#: What a reserve is legitimately FOR is room for the desktop to grow before a
#: compute job has to be evicted. So measure that. Ten samples of `ullAvailPhys`
#: at 2 s intervals on 2026-08-10, box busy with the upload:
#:   6.38 6.38 6.38 6.38 6.26 6.27 6.27 6.26 6.31 6.18  -> swing 0.21 GiB
#: 2.0 GB is ~10x the measured spontaneous swing, the same generosity the VRAM
#: floor grants ("the desktop can roughly double its working set").
#:
#: This also un-breaks MIN_FREE_AFTER_GB. At 6.0, passing the reserve check
#: guaranteed `avail - need >= 6.0 >= 4.0`, so the thrash floor was unreachable
#: dead code -- two checks that looked independent and were not. At 2.0 the
#: floor is the binding constraint again, which is right: it is the one derived
#: from what actually made the machine unusable.
RESERVE_GB = 2.0

#: Refuse anything that would leave less than this free. Below it Windows starts
#: paging hard, which is what "thrashing" was.
MIN_FREE_AFTER_GB = 4.0

#: VRAM headroom the DESKTOP needs, derived from measurement rather than typed.
#: With zero compute jobs running, this card reports 560-622 MiB resident across
#: samples taken minutes apart (2026-08-08, `nvidia-smi --query-gpu=memory.used`,
#: four samples: 494 / 560 / 574 / 622 MiB). That is the compositor, the browser
#: and the editor, and it MOVES by ~130 MiB on its own. So a job admitted down to
#: the last byte leaves the desktop nowhere to grow, which is precisely what
#: "the machine was unusable" meant on both occasions (N-215, N-217: 0.19 GB and
#: 0.14 GB free of 5.8). Floor = the measured residency, so the desktop can
#: roughly double its working set without evicting a compute job.
#: Negative-controlled in the selftest: 0.14 GB free must be REFUSED and the
#: 5.33 GB that restored the machine must be ADMITTED.
VRAM_FLOOR_GB = 0.6

#: Where admitted jobs announce themselves, so admission can be made against the
#: SUM of what is running rather than one job at a time. The lock below is
#: single-flight and was already in place on both starvation nights; an aggregate
#: is a different question -- "does this fit ALONGSIDE what is already admitted"
#: -- and nothing was answering it.
JOBS = REPO / "artifacts" / ".resource_guard.jobs.json"
RUNTIME_ABORTS = REPO / "artifacts" / "resource_guard_aborts"


def free_ram_gb() -> float:
    """Free physical RAM in GiB, or 0.0 if it genuinely cannot be read.

    Windows goes through `GlobalMemoryStatusEx` -- a kernel32 call needing no
    external binary. Determinex learned this the hard way: the old WMIC path is
    gone in Windows 11 24H2, failed silently, and reported 0.0 on a working box.
    """
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class _Mem(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = _Mem()
            st.dwLength = ctypes.sizeof(_Mem)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
                return st.ullAvailPhys / (1024 ** 3)
            return 0.0
        if system == "Darwin":
            r = run_hidden(["sysctl", "-n", "hw.memsize"], timeout=5)
            # macOS has no simple "available"; total is the honest fallback and
            # the caller's reserve absorbs the difference.
            return int(r.stdout.strip()) / (1024 ** 3) if r.returncode == 0 else 0.0
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 0.0


def free_vram_gb() -> float:
    """Live free VRAM on the best GPU, 0.0 if there is none or no nvidia-smi."""
    # 20 s, not 5. The 5-second budget is an idle-desktop assumption: spawning
    # nvidia-smi on a box whose every core is saturated -- the fitter indexing
    # 13.7M track points, say -- routinely takes longer than that, the call
    # times out, and a card with 45 of 46 GiB free is reported as 0.0, which
    # the watchdog reads as "unreadable" and eventually aborts the job. Two fit
    # arms died that way on 2026-09-02 with the GPU at 3 MiB used.
    try:
        r = run_hidden(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], timeout=20)
        if r.returncode == 0:
            vals = [int(x.strip()) for x in r.stdout.strip().splitlines()
                    if x.strip().isdigit()]
            if vals:
                return max(vals) / 1024
    except Exception:
        pass
    return 0.0


def thermal_reasons(level: str, snap) -> list[str]:
    """Refuse to ADD load to a machine already running hot.

    Pure over the snapshot, so both directions are asserted without waiting for
    a hot card. "danger" and "critical" refuse; "warn" is reported and allowed,
    because the card's own target temperature under sustained load IS the warn
    line and refusing there would refuse all real work.
    """
    if level in ("danger", "critical"):
        w, d, c = thermal.gpu_thresholds()
        return [f"THERMAL ({level}): {snap.summary}. Limits read from the card "
                f"itself: warn {w:.0f} C, danger {d:.0f} C, critical {c:.0f} C. "
                f"Starting more work on hardware already this hot is how it "
                f"cooks. Let it cool."]
    return []


def install_thermal_watchdog(job: str, interval_s: float = 20.0) -> bool:
    """Kill this job if the machine reaches the temperature IT calls its ceiling.

    Admission is a snapshot; a run is an hour. The gate that matters is the one
    still watching at minute forty. Two consecutive critical readings, so a
    single bad sample cannot throw away an hour of work.

    Returns False when nothing could be read -- and the caller then SAYS the
    limit is not enforced rather than letting it be assumed. That distinction is
    the whole lesson of the VRAM probe that returned 0.0 on a working card for
    the life of this file.
    """
    import threading

    probe = thermal.read_temps()
    if not probe.sources_ok:
        return False

    def _watch():
        breaches = 0
        while True:
            time.sleep(interval_s)
            try:
                snap = thermal.read_temps()
            except Exception:
                continue
            if snap.danger_level == "critical":
                breaches += 1
                print(f"[guard] THERMAL CRITICAL ({breaches}/2) for {job!r}: "
                      f"{snap.summary}", file=sys.stderr, flush=True)
                if breaches >= 2:
                    print(f"[guard] KILLING {job!r}: hardware reached the "
                          f"temperature it calls its own ceiling. Losing a run "
                          f"is recoverable.", file=sys.stderr, flush=True)
                    release_lock()
                    deregister_job()
                    os._exit(4)
            else:
                breaches = 0

    threading.Thread(target=_watch, daemon=True).start()
    return True


def runtime_memory_reason(available_gb: float) -> str | None:
    """Return the fail-closed runtime reason for one RAM reading.

    Admission protects only the instant before allocation.  N-1121 passed an
    8 GiB declaration and then grew to ~36 GiB during point linking, leaving
    1.46 GiB available.  That is below the already-established 4 GiB paging
    floor, but no post-admission RAM watcher existed.  Zero means the probe is
    unreadable, not that the machine has zero RAM; repeated unreadable readings
    are also fatal because the safety property can no longer be verified.
    """
    if available_gb <= 0.0:
        return "free-RAM probe became unreadable"
    if available_gb < MIN_FREE_AFTER_GB:
        return (f"free RAM {available_gb:.2f} GiB is below the "
                f"{MIN_FREE_AFTER_GB:.2f} GiB thrash floor")
    return None


def runtime_vram_reason(free_gb: float) -> str | None:
    """Return the fail-closed runtime reason for one VRAM reading.

    The RAM watchdog above protects host memory; nothing protected the card.
    N-1121 smoke 2 was admitted correctly, completed optimizer step 1, and then
    during post-step evaluation reached 5,864 of 6,144 MiB -- 0.10 GiB free
    against the 0.6 GiB floor the desktop needs -- with no watcher to notice.
    Admission is an instant; evaluation allocates later and larger.

    Zero means the probe is unreadable, not that the card has no free memory,
    and repeated unreadable readings are fatal for the same reason as RAM: the
    safety property can no longer be verified. Raising the declaration instead
    would be answering the wrong question -- the physical card has no headroom
    left to declare.
    """
    if free_gb <= 0.0:
        return "free-VRAM probe became unreadable"
    if free_gb < VRAM_FLOOR_GB:
        return (f"free VRAM {free_gb:.2f} GiB is below the "
                f"{VRAM_FLOOR_GB:.2f} GiB desktop floor")
    return None


def _runtime_abort(job: str, reason: str, reading_gb: float,
                   exit_code: int = 5, *,
                   status: str = "ABORTED_RUNTIME_RESOURCE_GATE",
                   reading_key: str = "free_ram_gb",
                   floor_key: str = "thrash_floor_gb",
                   floor_gb: float = MIN_FREE_AFTER_GB,
                   suffix: str = "") -> None:
    """Durably record and terminate a job whose live safety gate failed.

    Keyword defaults reproduce the RAM receipt byte-for-byte; the VRAM watchdog
    passes its own status, key names and floor. `suffix` keeps the two receipts
    from colliding when one job trips both gates under the same pid.
    """
    RUNTIME_ABORTS.mkdir(parents=True, exist_ok=True)
    safe_job = re.sub(r"[^A-Za-z0-9_.-]+", "_", job).strip("_") or "job"
    receipt = RUNTIME_ABORTS / f"{safe_job}_{os.getpid()}{suffix}.json"
    _atomic_json_write(receipt, {
        "status": status,
        "job": job,
        "pid": os.getpid(),
        "reason": reason,
        reading_key: reading_gb,
        floor_key: floor_gb,
        "timestamp_unix": time.time(),
    })
    print(f"[guard] KILLING {job!r}: {reason}. Receipt: {receipt}",
          file=sys.stderr, flush=True)
    release_lock()
    deregister_job()
    os._exit(exit_code)


def install_memory_watchdog(job: str, interval_s: float = 2.0,
                            consecutive: int = 2) -> bool:
    """Kill after two consecutive unsafe or unreadable RAM samples.

    The kernel probe is cheap and the four-second default response is much
    faster than Windows can turn a runaway vectorisation into prolonged swap.
    One transient low sample is retained as a warning but does not discard a
    run.  This complements, rather than replaces, truthful RAM declarations.
    """
    import threading

    if free_ram_gb() <= 0.0:
        return False

    def _watch():
        breaches = 0
        while True:
            time.sleep(interval_s)
            reading = free_ram_gb()
            reason = runtime_memory_reason(reading)
            if reason is None:
                breaches = 0
                continue
            breaches += 1
            print(f"[guard] RAM UNSAFE ({breaches}/{consecutive}) for "
                  f"{job!r}: {reason}", file=sys.stderr, flush=True)
            if breaches >= consecutive:
                _runtime_abort(job, reason, reading)

    threading.Thread(target=_watch, daemon=True).start()
    return True


def install_vram_watchdog(job: str, interval_s: float = 2.0,
                          consecutive: int = 2) -> bool:
    """Kill after two consecutive unsafe or unreadable VRAM samples.

    Mirrors the RAM watchdog deliberately: same two-sample rule, so one
    transient spike during a kernel launch is warned about but does not discard
    a run, and the same durable receipt so an aborted run explains itself
    without a live terminal.

    Returns False when the card cannot be read at install time -- no GPU, or no
    `nvidia-smi`. That is reported by the caller rather than treated as safe;
    a box with no readable GPU is not one this watchdog can protect, and
    silently arming a watcher that can never fire would be worse than saying so.
    """
    import threading

    if free_vram_gb() <= 0.0:
        return False

    def _watch():
        breaches = 0
        while True:
            time.sleep(interval_s)
            reading = free_vram_gb()
            reason = runtime_vram_reason(reading)
            # An UNREADABLE probe is not the same event as a full card, and
            # conflating them cost a whole fit arm: on 2026-09-02 the patch_dt
            # arm was aborted at "free-VRAM probe became unreadable" while the
            # A40 had 40+ GiB free -- `nvidia-smi` had simply failed to answer
            # under the CPU load of indexing 13.7M track points. The docstring
            # above is right that a safety property which cannot be verified is
            # not satisfied, so this does not soften the rule: it re-probes
            # immediately, and only a reading that stays unreadable counts as a
            # breach. A genuinely full card reads fine and is unaffected.
            if reason is not None and reading <= 0.0:
                for _ in range(3):
                    time.sleep(0.5)
                    reading = free_vram_gb()
                    reason = runtime_vram_reason(reading)
                    if reading > 0.0:
                        break
            if reason is None:
                breaches = 0
                continue
            breaches += 1
            print(f"[guard] VRAM UNSAFE ({breaches}/{consecutive}) for "
                  f"{job!r}: {reason}", file=sys.stderr, flush=True)
            if breaches >= consecutive:
                _runtime_abort(job, reason, reading,
                               status="ABORTED_RUNTIME_VRAM_FLOOR",
                               reading_key="free_vram_gb",
                               floor_key="vram_floor_gb",
                               floor_gb=VRAM_FLOOR_GB,
                               suffix="_vram")

    threading.Thread(target=_watch, daemon=True).start()
    return True


def cpu_thread_cap() -> int:
    """How many threads ONE job may use. Derived from the box, not chosen.

    A CPU eval left to itself ran at 431% -- torch defaults to every core it can
    see -- on the operator's own desktop while they slept. The RAM rule already
    says this is their machine and not a batch node; the same reservation has to
    hold for the processor, or the guard protects one resource and hands over
    the other. One quarter of the logical cores: 3 of 12 here.
    """
    return max(1, (os.cpu_count() or 4) // 4)


def apply_cpu_cap(cap: int | None = None) -> dict:
    """Enforce the cap on this process AND on anything it spawns.

    Environment variables for children and for any BLAS imported later; a live
    `torch.set_num_threads` for a torch already imported, since by the time
    `admit()` runs the caller has usually imported it and the env var is then
    too late to matter.
    """
    cap = cap or cpu_thread_cap()
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS"):
        os.environ[var] = str(cap)
    applied = {"cap": cap, "torch": None}
    torch_mod = sys.modules.get("torch")
    if torch_mod is not None:
        try:
            torch_mod.set_num_threads(cap)
            applied["torch"] = torch_mod.get_num_threads()
        except Exception:
            pass
    return applied


def total_vram_gb() -> float:
    """Total VRAM on the best GPU, 0.0 if there is none or no nvidia-smi."""
    try:
        r = run_hidden(["nvidia-smi", "--query-gpu=memory.total",
                        "--format=csv,noheader,nounits"], timeout=5)
        if r.returncode == 0:
            vals = [int(x.strip()) for x in r.stdout.strip().splitlines()
                    if x.strip().isdigit()]
            if vals:
                return max(vals) / 1024
    except Exception:
        pass
    return 0.0


def vram_reasons(need_gb: float, live_declared_gb: float, free_gb: float,
                 total_gb: float, floor_gb: float = VRAM_FLOOR_GB) -> list[str]:
    """Would this job fit on the card, ALONGSIDE what is already admitted?

    Pure, so both directions are testable without a GPU or a second process.

    Three separate questions, because the two starvation nights failed only the
    second and third and the guard was asking only the first:

      1. does it fit in what is free RIGHT NOW
      2. does it leave the desktop its measured residency
      3. does the SUM of every admitted job still fit on the card

    (3) uses each job's DECLARED figure, not its observed peak, and that is
    deliberate. `torch.cuda.max_memory_allocated` -- the source of
    `resource_peaks.json` -- counts allocated tensors and excludes the CUDA
    context and the caching allocator's reserve, several hundred MiB per
    process. Summing observed peaks would have said the two jobs on N-217 needed
    4.61 GB of a 6.0 GB card and admitted them; the card actually went to 0.14 GB
    free. Declarations are the conservative number and this is the place for one.
    """
    out = []
    if need_gb <= 0.0 or total_gb <= 0.0:
        return out
    if free_gb > 0.0 and need_gb > free_gb:
        out.append(f"VRAM: needs {need_gb:.1f} GB, only {free_gb:.1f} GB free")
    elif free_gb > 0.0 and (free_gb - need_gb) < floor_gb:
        out.append(
            f"VRAM: would leave {free_gb - need_gb:.2f} GB free, below the "
            f"{floor_gb:.1f} GB desktop floor -- this is the state that made the "
            f"machine unusable twice (N-215, N-217)")
    if live_declared_gb > 0.0 and (need_gb + live_declared_gb) > (total_gb - floor_gb):
        out.append(
            f"VRAM AGGREGATE: {live_declared_gb:.1f} GB already admitted to other "
            f"jobs + {need_gb:.1f} GB here = {need_gb + live_declared_gb:.1f} GB, "
            f"over the {total_gb - floor_gb:.1f} GB usable on a {total_gb:.1f} GB "
            f"card. Each fits alone; together they starve the card")
    return out


def _read_jobs() -> dict:
    try:
        d = json.loads(JOBS.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise RuntimeError(f"resource registry is not an object: {JOBS}")
        return d
    except FileNotFoundError:
        return {}
    except Exception as exc:
        # A registry we cannot read is NOT an empty registry. Treating parse or
        # permission failures as "nothing is running" is a fail-open admission.
        raise RuntimeError(f"cannot read resource registry {JOBS}: {exc}") from exc


def _atomic_json_write(path: Path, value: object) -> None:
    """Durably replace a JSON control file; any failure is visible to caller."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with tmp.open("x", encoding="utf-8", newline="\n") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def live_jobs(exclude_pid: int | None = None) -> dict:
    """Admitted jobs whose PID is still alive. Dead entries are dropped.

    A job killed with SIGKILL never runs its atexit, so the registry MUST be
    self-cleaning or one crash poisons admission for every job after it -- the
    same failure mode the stale lock already has a fix for.
    """
    out = {}
    for pid_s, rec in _read_jobs().items():
        try:
            pid = int(pid_s)
        except Exception as exc:
            raise RuntimeError(
                f"resource registry contains an unparseable pid {pid_s!r}; "
                "refusing to treat it as dead") from exc
        if not isinstance(rec, dict):
            raise RuntimeError(
                f"resource registry entry for pid {pid_s} is not an object")
        if exclude_pid is not None and pid == exclude_pid:
            continue
        if _pid_alive(pid, rec.get("image"), rec.get("started")):
            out[pid_s] = rec
    return out


def register_job(job: str, need_ram_gb: float, need_vram_gb: float) -> None:
    """Announce this process's declared footprint, and prune the dead."""
    cur = live_jobs()
    cur[str(os.getpid())] = {
        "job": job, "need_ram_gb": float(need_ram_gb),
        "need_vram_gb": float(need_vram_gb),
        # Recorded so a recycled pid cannot inherit this job's reservation.
        "image": os.path.basename(sys.executable),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _atomic_json_write(JOBS, cur)


def deregister_job() -> None:
    cur = _read_jobs()
    if cur.pop(str(os.getpid()), None) is not None:
        _atomic_json_write(JOBS, cur)


def _get_process(pid: int):
    """Small injection seam so access-denied behavior is testable."""
    import psutil
    return psutil.Process(pid)


def _pid_alive(pid: int, image: str | None = None,
               started: str | None = None) -> bool:
    """Is this pid alive AND still the process we registered?

    THE `image` ARGUMENT IS THE WHOLE POINT. Windows recycles pids quickly, and
    a bare "does this pid exist" check returns True the moment the number is
    reissued to something else. Observed directly: a heartbeat for a finished
    extraction reported LIVE for pid 117920, which by then was `conhost.exe`.
    That is not cosmetic -- the job registry uses this same probe, so a dead
    job's declared RAM stays "admitted elsewhere" permanently once its pid is
    reused, and the guard then refuses every subsequent job for a footprint that
    was freed hours ago. Several refusals in this session were blamed on a kill
    racing a relaunch; this is at least as likely to have been the cause.

    Comparing the image name catches reuse by a DIFFERENT program, which is the
    common case. Reuse by another python.exe would still pass, and that residual
    is stated rather than papered over -- closing it needs the process start
    time, which costs a CIM query per check.

    THE RESIDUAL STOPPED BEING RESIDUAL, so it is closed here (2026-08-11).
    `run_when_free.sh` polls this guard by spawning a fresh python every 60
    seconds, which makes "the recycled pid happens to be another python.exe"
    the LIKELY case rather than an edge one. It bit exactly as predicted: a
    SIGTERM'd `register_scroll` left a 2.0 GB reservation, its pid was reissued
    to a poll subprocess, the image matched, and the guard refused every job
    afterwards for memory that had been free for half an hour.

    `started` closes it. A recycled pid belongs to a process that began AFTER
    the reservation was written, so a create_time later than `started` proves
    reuse. psutil is already a dependency here, so this costs no CIM query --
    the objection in the paragraph above was to a cost we do not actually pay.
    Without psutil, or without a recorded `started`, the old behaviour stands
    and the residual is back: reported, not silently assumed away.
    """
    if pid <= 0:
        return False
    try:
        proc = _get_process(pid)
    except Exception as exc:
        # psutil's NoSuchProcess is the only positive proof of death. Access
        # denied, a missing dependency, or any probe failure must block rather
        # than erase a live reservation.
        if exc.__class__.__name__ in {"NoSuchProcess", "ZombieProcess"}:
            return False
        return True
    try:
        if not proc.is_running():
            return False
        status = str(proc.status()).lower()
        if "zombie" in status:
            return False
        if image:
            actual = os.path.basename(proc.name()).lower()
            expected = os.path.basename(image).lower()
            if actual != expected:
                return False
        if started:
            import datetime as _dt
            began = _dt.datetime.fromtimestamp(proc.create_time())
            # 2 s of slack: `started` is written just after the process begins.
            if began > _dt.datetime.fromisoformat(started) + _dt.timedelta(seconds=2):
                return False
        return True
    except Exception:
        # We found the process but could not inspect it. That is not proof it
        # died, so retain its lock and reservation.
        return True


def _read_lock() -> dict | None:
    try:
        return json.loads(LOCK.read_text(encoding="utf-8"))
    except Exception:
        return None


def acquire_lock(job: str) -> tuple[bool, str]:
    """Atomically acquire single-flight; stale/unclear locks refuse safely."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"job": job, "pid": os.getpid(),
                          "started": time.strftime("%Y-%m-%dT%H:%M:%S")})
    try:
        fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        cur = _read_lock()
        if not cur:
            return False, "guard lock exists but is unreadable; refusing"
        try:
            pid = int(cur.get("pid", -1))
        except Exception:
            return False, "guard lock has an invalid pid; refusing"
        state = "LIVE" if _pid_alive(pid) else "provably stale"
        return False, (f"another heavy job holds the guard: {cur.get('job')!r} "
                       f"(pid {pid}, started {cur.get('started')}, {state}). "
                       "Never break a lock during admission; run --reap only "
                       "after positive proof its holder is dead.")
    except Exception as exc:
        return False, f"cannot create guard lock atomically: {exc}"
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception as exc:
        try:
            LOCK.unlink(missing_ok=True)
        except Exception:
            pass
        return False, f"could not persist guard lock: {exc}"
    return True, "acquired"


def release_lock() -> None:
    cur = _read_lock()
    if cur and int(cur.get("pid", -1)) == os.getpid():
        try:
            LOCK.unlink()
        except Exception:
            pass


def install_reaper() -> None:
    """Kill our process group on exit, so a crash leaves no orphans behind.

    This is the mechanism whose ABSENCE left eight stray Python processes after
    failed background launches. Registered for normal exit AND for the signals a
    harness uses to stop a job, because the orphan case is precisely the abnormal
    one.
    """
    atexit.register(release_lock)
    atexit.register(deregister_job)

    def _bye(signum, _frame):
        release_lock()
        deregister_job()
        try:
            if platform.system() != "Windows":
                os.killpg(os.getpgid(0), signal.SIGTERM)
        except Exception:
            pass
        sys.exit(128 + int(signum))

    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, _bye)
        except Exception:
            pass


def self_report(job: str) -> None:
    """Record THIS process's own peak usage at exit, measured not typed.

    The first peaks in this file were entered BY HAND from `nvidia-smi`, which
    reports the whole card -- including the ~540 MiB the desktop compositor
    holds. That inflated `verify_bbox_difficulty` from a real ~5.2 GB to a
    recorded 5.74, the declaration was raised to 6.0, and the gate then refused
    the job permanently on a 6.1 GB card that never has more than ~5.4 GB free.
    A guard poisoned by bad numbers blocks real work, which is the opposite
    failure to freezing and just as useless.

    `torch.cuda.max_memory_allocated` is THIS process's allocation. RSS is this
    process's RAM. Neither can pick up another program's usage.
    """
    import atexit

    def _rec():
        ram = vram = 0.0
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]

            if platform.system() == "Windows":
                # ARGTYPES AND RESTYPE ARE LOAD-BEARING. Without them ctypes
                # treats the process HANDLE as a C int, the value overflows, the
                # call raises OverflowError, the surrounding except swallows it,
                # and `peak_ram_gb` is recorded as 0.0 -- which is
                # indistinguishable from "used no memory" and can NEVER trip the
                # under-declaration check. Four runs were logged that way while
                # preflight reported PASS: a guard reporting an outcome it never
                # established, which is this project's most-repeated defect.
                k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                k32.GetCurrentProcess.restype = wintypes.HANDLE
                k32.K32GetProcessMemoryInfo.argtypes = [
                    wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
                k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
                c = _PMC()
                c.cb = ctypes.sizeof(_PMC)
                if k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(),
                                               ctypes.byref(c), c.cb):
                    ram = c.PeakWorkingSetSize / (1024 ** 3)
        except Exception:
            pass
        try:
            import torch

            if torch.cuda.is_available():
                vram = torch.cuda.max_memory_allocated() / (1024 ** 3)
        except Exception:
            pass
        if ram or vram:
            record_peak(job, ram, vram)

    atexit.register(_rec)


def record_peak(job: str, peak_ram_gb: float, peak_vram_gb: float = 0.0) -> None:
    """Log a job's OBSERVED peak so the declared estimate can be corrected.

    The estimates passed to `admit()` are hand-written and at least one was
    already wrong: `distill_scale_sweep` declared 6.0 GB and used 7.35 (N-150).
    A gate whose numbers are guesses admits things it should refuse. This
    accumulates ground truth so the declarations can be trued up against
    measurement instead of intuition.
    """
    path = REPO / "artifacts" / "resource_peaks.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    cur = data.get(job, {})
    data[job] = {
        "peak_ram_gb": round(max(peak_ram_gb, cur.get("peak_ram_gb", 0.0)), 2),
        "peak_vram_gb": round(max(peak_vram_gb, cur.get("peak_vram_gb", 0.0)), 2),
        "observations": int(cur.get("observations", 0)) + 1,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def declared_vs_observed(root: Path | None = None) -> list[str]:
    """Declarations that are BELOW what the job was actually measured using.

    `root` exists so preflight's negative control can plant an under-declared
    job in a temporary tree and see it caught. Without it this function read the
    real repository no matter what it was asked about, so the planted defect was
    invisible and that arm of the selftest had been reporting GUARD IS INERT --
    correctly, and unnoticed, for as long as it has existed.
    """
    root = root or REPO
    path = root / "artifacts" / "resource_peaks.json"
    try:
        obs = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    scripts_dir = root / "scripts"
    for f in sorted(scripts_dir.glob("*.py")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        # finditer, not search. `search` returns the FIRST declaration in a file
        # and stops, so a script with two modes and two different footprints had
        # exactly one of them checked and the other was free to drift. Nothing
        # announced that; the check just quietly covered less than it appeared to.
        for m in re.finditer(
                r"admit\(\s*['\"]([^'\"]+)['\"]\s*,\s*need_ram_gb=([\d.]+)"
                r"(?:\s*,\s*need_vram_gb=([\d.]+))?", txt):
            job, ram = m.group(1), float(m.group(2))
            vram = float(m.group(3) or 0.0)
            o = obs.get(job)
            if not o:
                continue
            if o["peak_ram_gb"] > ram:
                out.append(f"{job}: declares {ram} GB RAM, observed peak "
                           f"{o['peak_ram_gb']} GB over {o['observations']} run(s)")
            if o["peak_vram_gb"] > vram:
                out.append(f"{job}: declares {vram} GB VRAM, observed peak "
                           f"{o['peak_vram_gb']} GB over {o['observations']} run(s)")
    return out


def check(need_ram_gb: float, need_vram_gb: float = 0.0,
          live: dict | None = None) -> dict:
    """Would this job fit? Pure decision, no side effects -- so it is testable.

    `live` is the aggregate view: the other admitted jobs and what they declared.
    Passed in rather than read here so the selftest can assert both directions
    without spawning a second process. Default None means "read the registry".
    """
    fr, fv = free_ram_gb(), free_vram_gb()
    tv = total_vram_gb()
    if live is None:
        live = live_jobs(exclude_pid=os.getpid())
    live_ram = sum(float(r.get("need_ram_gb", 0.0)) for r in live.values())
    live_vram = sum(float(r.get("need_vram_gb", 0.0)) for r in live.values())
    reasons = []
    # 0.0 means "could not read", which is NOT the same as "no memory". `check`
    # reports that state; `admit` fails closed because an unverified allocation
    # must not be allowed onto the operator's machine.
    ram_unknown = fr <= 0.0
    if not ram_unknown:
        # The aggregate applies to RAM too: another admitted job's declaration is
        # memory this one cannot have, even though the kernel has not handed it
        # over yet.
        eff_free_ram = fr - live_ram
        if need_ram_gb > max(0.0, eff_free_ram - RESERVE_GB):
            reasons.append(
                f"RAM: needs {need_ram_gb:.1f} GB, only {fr:.1f} GB free"
                + (f" ({live_ram:.1f} GB already admitted elsewhere)" if live_ram else "")
                + f" and {RESERVE_GB:.1f} GB is reserved for the OS")
        elif (eff_free_ram - need_ram_gb) < MIN_FREE_AFTER_GB:
            reasons.append(
                f"RAM: would leave {eff_free_ram - need_ram_gb:.1f} GB free, below "
                f"the {MIN_FREE_AFTER_GB:.1f} GB thrash floor")
    reasons += vram_reasons(need_vram_gb, live_vram, fv, tv)
    snap = thermal.read_temps()
    reasons += thermal_reasons(snap.danger_level, snap)
    return {"ok": not reasons, "free_ram_gb": round(fr, 2),
            "thermal": snap.summary, "thermal_level": snap.danger_level,
            "thermal_probe_ok": bool(snap.sources_ok),
            "free_vram_gb": round(fv, 2), "total_vram_gb": round(tv, 2),
            "ram_probe_failed": ram_unknown,
            "vram_probe_failed": tv <= 0.0,
            "live_jobs": {r.get("job", "?"): r.get("need_vram_gb", 0.0)
                          for r in live.values()},
            "live_declared_ram_gb": round(live_ram, 2),
            "live_declared_vram_gb": round(live_vram, 2),
            "need_ram_gb": need_ram_gb, "need_vram_gb": need_vram_gb,
            "reasons": reasons}


def admit(job: str, need_ram_gb: float, need_vram_gb: float = 0.0,
          single_flight: bool = True) -> None:
    """THE RULE. Call this before allocating. Exits non-zero rather than thrashing."""
    v = check(need_ram_gb, need_vram_gb)
    if v["ram_probe_failed"]:
        print(f"[guard] REFUSED {job!r}: free-RAM probe failed; admission "
              "cannot be verified.", file=sys.stderr)
        sys.exit(3)
    elif need_vram_gb > 0.0 and v["vram_probe_failed"]:
        # SAY SO. A GPU job admitted while the VRAM probe is dead is exactly the
        # state this guard was in from the day it was written until 2026-08-08:
        # silent zeros read as "no GPU here", the VRAM branch skipped, and two
        # jobs let onto a 6 GB card. If the probe cannot answer, that is a fact
        # about the check, not a pass.
        print(f"[guard] REFUSED {job!r}: no VRAM reading available; cannot "
              f"verify a {need_vram_gb:.1f} GB request.",
              file=sys.stderr)
        sys.exit(3)
    elif not v["ok"]:
        print(f"[guard] REFUSED {job!r}:", file=sys.stderr)
        for r in v["reasons"]:
            print(f"  - {r}", file=sys.stderr)
        print("  Refusing to start is recoverable. Freezing the machine is not.",
              file=sys.stderr)
        sys.exit(3)
    self_report(job)
    if single_flight:
        ok, msg = acquire_lock(job)
        if not ok:
            print(f"[guard] REFUSED {job!r}: {msg}", file=sys.stderr)
            sys.exit(3)
    try:
        register_job(job, need_ram_gb, need_vram_gb)
    except Exception as exc:
        release_lock()
        print(f"[guard] REFUSED {job!r}: could not durably register job: {exc}",
              file=sys.stderr)
        sys.exit(3)
    install_reaper()

    # CAP THE PROCESSOR BEFORE ANY WORK STARTS. A CPU eval left to itself ran at
    # 431% on the operator's own desktop while they slept -- torch takes every
    # core it can see -- and the operator saw it on the queue and said stop.
    # Refusing to think about the CPU while carefully rationing RAM protected
    # one resource and handed over the other.
    cap = apply_cpu_cap()
    watching = install_thermal_watchdog(job)
    watching_memory = install_memory_watchdog(job)
    watching_vram = install_vram_watchdog(job)

    others = ", ".join(f"{k} {v_:.1f} GB" for k, v_ in v["live_jobs"].items())
    print(f"[guard] admitted {job!r}: need {need_ram_gb:.1f} GB RAM"
          f"{f' + {need_vram_gb:.1f} GB VRAM' if need_vram_gb else ''}, "
          f"free {v['free_ram_gb']:.1f} GB RAM / {v['free_vram_gb']:.1f} GB VRAM"
          f" of {v['total_vram_gb']:.1f} GB"
          + (f"; alongside {others}" if others else ""))
    print(f"[guard] {v['thermal']} ({v['thermal_level']}), cpu capped to "
          f"{cap['cap']} of {os.cpu_count()} threads, thermal watchdog "
          + ("ARMED" if watching else "NOT AVAILABLE -- heat limit unenforced")
          + ", RAM watchdog "
          + ("ARMED" if watching_memory else
             "NOT AVAILABLE -- runtime floor unenforced")
          + ", VRAM watchdog "
          + ("ARMED" if watching_vram else
             "NOT AVAILABLE -- card floor unenforced"))


def _selftest_resource_guard_inner() -> int:
    """Both directions. A gate that cannot refuse is not a gate."""
    fails = []
    ran = []

    def ck(name, cond):
        # COUNTED, not hard-coded. The old `total = 13` was a literal, and two of
        # the thirteen were inside `if _pid_alive(1):` -- so when the liveness
        # probe broke, the suite ran eleven checks and still printed "13/13".
        # A count that cannot notice a skipped check is a count of nothing.
        ran.append(name)
        if not cond:
            fails.append(name)

    fr = free_ram_gb()
    ck("ram_probe_returns_number", isinstance(fr, float))
    ck("ram_probe_nonzero_on_this_box", fr > 0.0)

    # A tiny request must be ADMITTED and an absurd one REFUSED. Both, or the
    # gate is decoration -- the same negative-control rule this project applies
    # to every other guard.
    ck("small_job_ok", check(0.1)["ok"] is True)
    ck("absurd_job_refused", check(100000.0)["ok"] is False)
    ck("refusal_states_reason", len(check(100000.0)["reasons"]) > 0)

    # The thrash floor must bite even when the raw request would technically fit.
    ck("thrash_floor_bites", check(max(0.1, fr - 1.0))["ok"] is False)

    # THE TWO RAM CHECKS MUST BE INDEPENDENT. With RESERVE_GB=6.0 against a
    # 4.0 thrash floor, passing the reserve check GUARANTEED avail-need >= 6.0
    # >= 4.0, so the floor was unreachable dead code that looked like a second
    # line of defence. Reachability is exactly the condition below, and it is
    # asserted rather than reasoned about.
    ck("the_thrash_floor_is_reachable_not_dead_code",
       RESERVE_GB < MIN_FREE_AFTER_GB)
    ck("runtime_memory_floor_accepts_safe_reading",
       runtime_memory_reason(MIN_FREE_AFTER_GB + 0.01) is None)
    ck("runtime_memory_floor_rejects_thrashing_reading",
       "thrash floor" in (runtime_memory_reason(MIN_FREE_AFTER_GB - 0.01) or ""))
    ck("runtime_memory_probe_failure_is_not_called_safe",
       "unreadable" in (runtime_memory_reason(0.0) or ""))

    # ---- VRAM runtime floor -------------------------------------------------
    # Admission is an instant; N-1121 smoke 2 was admitted correctly and then
    # reached 5,864/6,144 MiB during post-step evaluation with nothing watching.
    ck("runtime_vram_floor_accepts_safe_reading",
       runtime_vram_reason(VRAM_FLOOR_GB + 0.01) is None)
    ck("runtime_vram_floor_rejects_starved_reading",
       "desktop floor" in (runtime_vram_reason(VRAM_FLOOR_GB - 0.01) or ""))
    ck("runtime_vram_probe_failure_is_not_called_safe",
       "unreadable" in (runtime_vram_reason(0.0) or ""))
    ck("runtime_vram_rejects_the_exact_reading_that_stopped_smoke2",
       runtime_vram_reason((6144 - 5864) / 1024) is not None)

    # ---- the watchdogs must actually BITE -----------------------------------
    # A watchdog is a thread that calls os._exit, so the only honest test is a
    # real process that either dies or does not. Codex's RAM watchdog had only
    # its predicate asserted; both are exercised end-to-end here.
    import subprocess as _sp

    def _bite(mode: str):
        before = set(RUNTIME_ABORTS.glob("*.json")) if RUNTIME_ABORTS.exists() \
            else set()
        try:
            p = _sp.run([sys.executable, str(Path(__file__).resolve()),
                         "--watchdog-bite-child", mode],
                        capture_output=True, text=True, timeout=40)
            rc = p.returncode
        except _sp.TimeoutExpired:
            rc = None
        after = set(RUNTIME_ABORTS.glob("*.json")) if RUNTIME_ABORTS.exists() \
            else set()
        return rc, (after - before)

    rc_v, new_v = _bite("vram")
    ck("vram_watchdog_bites", rc_v == 5)
    ck("vram_watchdog_writes_a_durable_receipt",
       any(f.name.endswith("_vram.json") for f in new_v))
    if new_v:
        try:
            _rec = json.loads(sorted(new_v)[0].read_text(encoding="utf-8"))
        except Exception:
            _rec = {}
        ck("vram_receipt_names_the_vram_gate",
           _rec.get("status") == "ABORTED_RUNTIME_VRAM_FLOOR")
        ck("vram_receipt_records_the_reading_and_floor",
           "free_vram_gb" in _rec and _rec.get("vram_floor_gb") == VRAM_FLOOR_GB)
    else:
        ck("vram_receipt_names_the_vram_gate", False)
        ck("vram_receipt_records_the_reading_and_floor", False)

    # NEGATIVE CONTROL. A gate that kills on any single sample would discard
    # good runs on one transient spike, so the two-sample rule is asserted by
    # requiring SURVIVAL here. Without this the bite test above would pass just
    # as happily for a watchdog that fires unconditionally.
    rc_t, _ = _bite("vram-transient")
    ck("vram_watchdog_ignores_a_single_transient_spike", rc_t == 0)

    rc_r, new_r = _bite("ram")
    ck("ram_watchdog_bites", rc_r == 5)
    ck("ram_receipt_is_distinct_from_the_vram_receipt",
       any(not f.name.endswith("_vram.json") for f in new_r))

    for _f in new_v | new_r:
        try:
            _f.unlink()
        except OSError:
            pass
    ck("the_reserve_is_measured_not_typed",
       "swing 0.21 GiB" in (__doc__ or "") or "swing 0.21 GiB" in open(
           __file__, encoding="utf-8").read())
    # Deterministic, driven off a fixed reading rather than the live box.
    _g = globals()
    _rf = _g["free_ram_gb"]
    try:
        _g["free_ram_gb"] = lambda: 6.0
        r = check(2.5, 0.0, live={})
        ck("SABOTAGE_a_job_that_would_leave_the_box_thrashing_is_refused",
           not r["ok"] and any("thrash floor" in x for x in r["reasons"]))
        ck("and_it_is_the_FLOOR_that_refuses_not_the_reserve",
           not any("reserved for the OS" in x for x in r["reasons"]))
        ck("a_job_that_leaves_real_headroom_is_admitted",
           check(1.5, 0.0, live={})["ok"])
        _g["free_ram_gb"] = lambda: 4.5
        ck("SABOTAGE_a_nearly_full_box_still_refuses_a_small_job",
           not check(1.5, 0.0, live={})["ok"])
        # An unreadable probe is NOT "no memory" -- it must not silently refuse.
        _g["free_ram_gb"] = lambda: 0.0
        ck("SABOTAGE_an_unreadable_probe_is_reported_not_treated_as_empty",
           check(1.5, 0.0, live={})["ram_probe_failed"])
    finally:
        _g["free_ram_gb"] = _rf

    # THE LIVENESS PROBE MUST BE ABLE TO SAY "ALIVE". It returned False for every
    # process on Windows for the life of this file, because `run_hidden` was
    # never imported and the NameError went into an `except Exception`. A lock
    # whose holder always looks dead is not a lock -- it broke itself every time
    # and is how two GPU jobs ran together (N-215, N-217). Assert on OUR OWN pid,
    # which is unarguably alive.
    ck("liveness_probe_sees_this_process", _pid_alive(os.getpid()) is True)
    ck("liveness_probe_rejects_impossible_pid", _pid_alive(999999) is False)
    # PID REUSE. Our own pid with the RIGHT image is alive; the same pid with a
    # different image is a recycled number and must read dead, or a finished
    # job's reservation outlives it and blocks the queue forever.
    ck("liveness_accepts_the_right_image",
       _pid_alive(os.getpid(), os.path.basename(sys.executable)) is True)
    ck("liveness_rejects_a_recycled_pid",
       _pid_alive(os.getpid(), "conhost.exe") is False)
    # Probe failure is UNKNOWN, never DEAD. This exact Access-Denied shape let
    # register_scroll replace a live v5 lock on 2026-08-28.
    _gp = _g["_get_process"]
    try:
        def _denied(_pid):
            raise PermissionError("synthetic access denied")
        _g["_get_process"] = _denied
        ck("SABOTAGE_access_denied_keeps_holder_alive",
           _pid_alive(os.getpid()) is True)
    finally:
        _g["_get_process"] = _gp

    # SAME FOR THE VRAM PROBE. The old assertion here was
    # `check(0.1, 99999)["ok"] is (free_vram_gb() == 0.0)` -- which passes
    # trivially when the probe is broken, because both sides become "no GPU".
    # A check that is satisfied by its own subject failing is not a check.
    fv, tv = free_vram_gb(), total_vram_gb()
    if tv > 0.0:
        ck("vram_probe_returns_a_real_total", tv > 0.5)
        ck("vram_free_not_above_total", 0.0 <= fv <= tv + 1e-6)
        ck("absurd_vram_refused", check(0.1, tv * 10)["ok"] is False)
    else:
        # Genuinely no GPU: VRAM must be ignored rather than refused, or a
        # CPU-only box is blocked for lacking hardware it never claimed.
        ck("vram_ignored_without_gpu", check(0.1, 99999.0)["ok"] is True)

    # THE AGGREGATE, both directions, as pure arithmetic -- no second process
    # needed, so it is asserted on every run rather than when the stars align.
    # Numbers are this card and the two jobs that starved it: 6.0 GB total,
    # adapt_teacher_9um declares 3.5, pipeline_distill_train declares 2.0.
    ck("aggregate_refuses_the_pair_that_starved_the_card",
       len(vram_reasons(3.5, 2.0, 5.4, 6.0)) > 0)
    ck("aggregate_admits_the_same_job_alone",
       len(vram_reasons(3.5, 0.0, 5.4, 6.0)) == 0)
    # The measured-bad and measured-good free-VRAM states from the notebook.
    ck("floor_refuses_the_observed_starved_state",
       len(vram_reasons(0.5, 0.0, 0.14 + 0.5, 6.0)) > 0)
    ck("floor_admits_the_state_that_restored_the_machine",
       len(vram_reasons(0.5, 0.0, 5.33 + 0.5, 6.0)) == 0)
    # A registry entry only counts while its process lives.
    ck("registry_drops_dead_pids",
       str(999999) not in live_jobs())

    # HEAT, both directions, on the thresholds the card actually publishes.
    gw, gd, gc = thermal.gpu_thresholds()
    ck("gpu_thresholds_are_ordered", gw < gd < gc)
    snap_now = thermal.read_temps()
    ck("thermal_probe_reads_something", bool(snap_now.sources_ok))
    ck("cool_machine_is_not_refused",
       thermal_reasons("ok", snap_now) == [])
    ck("hot_machine_is_refused",
       len(thermal_reasons("critical", snap_now)) > 0)
    # A CPU-usage probe that cannot read must not be indistinguishable from an
    # idle machine. psutil is absent in this venv and the upstream reader
    # returned a hard 0.0, which is exactly what "idle" looks like.
    ck("cpu_usage_probe_is_real_or_says_it_is_not",
       snap_now.cpu_usage != 0.0)
    ck("cpu_cap_leaves_the_operator_most_of_the_box",
       1 <= cpu_thread_cap() <= max(1, (os.cpu_count() or 4) // 2))

    # Lock: acquire, see it refuse a foreign live holder, then release.
    ok1, _ = acquire_lock("selftest")
    ck("lock_acquires", ok1)
    # OUR pid, not pid 1: the old test used pid 1 behind an `if _pid_alive(1)`
    # guard, so when the liveness probe was broken the whole assertion was
    # SKIPPED and the suite stayed green.
    LOCK.write_text(json.dumps({"job": "other", "pid": os.getpid(),
                                "started": "x"}), encoding="utf-8")
    ok2, msg = acquire_lock("selftest2")
    ck("lock_refuses_live_holder", (not ok2) and "holds the guard" in msg)
    LOCK.write_text(json.dumps({"job": "dead", "pid": 999999, "started": "x"}),
                    encoding="utf-8")
    ok3, msg3 = acquire_lock("selftest3")
    ck("stale_lock_refuses_during_admission",
       (not ok3) and "provably stale" in msg3)
    LOCK.unlink()
    ok4, _ = acquire_lock("selftest4")
    ck("lock_acquires_after_explicit_stale_reap", ok4)
    release_lock()
    ck("lock_released", not LOCK.exists())

    # THE SELF-MEASUREMENT MUST RETURN A REAL NUMBER. It silently returned 0.0
    # for four runs because ctypes argtypes were missing, the HANDLE overflowed,
    # and the except swallowed it -- and 0.0 can never trip the
    # under-declaration check, so preflight passed while RAM was unverified.
    # Asserting non-zero is the only thing that distinguishes "measured nothing"
    # from "measured zero".
    import os as _os

    _tmp = REPO / "artifacts" / "_selftest_peaks.json"
    _real = REPO / "artifacts" / "resource_peaks.json"
    _saved = _real.read_text(encoding="utf-8") if _real.exists() else None
    try:
        _real.write_text("{}", encoding="utf-8")
        _probe_ram = 0.0
        try:
            import ctypes
            from ctypes import wintypes

            if platform.system() == "Windows":
                k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                k32.GetCurrentProcess.restype = wintypes.HANDLE
                class _P(ctypes.Structure):
                    _fields_ = [("cb", wintypes.DWORD), ("f", wintypes.DWORD),
                                ("pk", ctypes.c_size_t), ("ws", ctypes.c_size_t),
                                ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                                ("c", ctypes.c_size_t), ("d", ctypes.c_size_t),
                                ("e", ctypes.c_size_t), ("g", ctypes.c_size_t)]
                k32.K32GetProcessMemoryInfo.argtypes = [
                    wintypes.HANDLE, ctypes.POINTER(_P), wintypes.DWORD]
                k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
                _c = _P(); _c.cb = ctypes.sizeof(_P)
                if k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(),
                                               ctypes.byref(_c), _c.cb):
                    _probe_ram = _c.pk / (1024 ** 3)
            else:
                # LINUX. Without this branch `_probe_ram` stays 0.0 on every
                # non-Windows box, so `record_peak` writes zero forever and the
                # declared-vs-observed correction loop -- the thing that caught
                # `n1104_spiral_fit: declares 8.0 GB, observed peak 24.01 GB` --
                # silently never accumulates. VmHWM is the kernel's own peak
                # RSS, the direct analogue of PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize.
                with open("/proc/self/status", encoding="utf-8") as _fh:
                    for _line in _fh:
                        if _line.startswith("VmHWM:"):
                            _probe_ram = int(_line.split()[1]) / (1024 ** 2)
                            break
        except Exception:
            pass
        ck("ram_self_measurement_is_real", _probe_ram > 0.0)
        record_peak("__selftest__", _probe_ram, 0.0)
        _rec = json.loads(_real.read_text(encoding="utf-8"))
        ck("recorded_ram_is_nonzero",
           _rec.get("__selftest__", {}).get("peak_ram_gb", 0.0) > 0.0)
    finally:
        if _saved is not None:
            _real.write_text(_saved, encoding="utf-8")
        elif _real.exists():
            _real.unlink()

    total = len(ran)
    print(f"selftest: {total - len(fails)}/{total} passed")
    if fails:
        print("FAILED: " + ", ".join(fails))
        return 1
    return 0


def selftest_resource_guard() -> int:
    """Run destructive lock/registry checks only against an isolated sandbox."""
    import tempfile

    g = globals()
    old_repo, old_lock, old_jobs = g["REPO"], g["LOCK"], g["JOBS"]
    with tempfile.TemporaryDirectory(prefix="vesuvius-resource-guard-") as td:
        root = Path(td)
        (root / "artifacts").mkdir()
        g["REPO"] = root
        g["LOCK"] = root / "artifacts" / ".resource_guard.lock"
        g["JOBS"] = root / "artifacts" / ".resource_guard.jobs.json"
        try:
            return _selftest_resource_guard_inner()
        finally:
            g["REPO"], g["LOCK"], g["JOBS"] = old_repo, old_lock, old_jobs


def _watchdog_bite_child(mode: str) -> int:
    """Child process for the watchdog bite tests. Not a user-facing entrypoint.

    A watchdog is a thread that calls `os._exit`, so the only honest test of it
    is a real process that either dies or does not. Asserting the predicate in
    isolation would leave the wiring -- thread started, breaches counted, abort
    reached -- completely unverified, which is how a guard ends up looking armed
    and never firing.
    """
    g = globals()
    if mode == "vram":
        g["free_vram_gb"] = lambda: VRAM_FLOOR_GB / 4.0
        install_vram_watchdog("bite_test_vram", interval_s=0.05, consecutive=2)
    elif mode == "vram-transient":
        # One unsafe reading, then safe forever. Must NOT kill: a single spike
        # during a kernel launch is not a reason to discard a run.
        state = {"n": 0}

        def _probe():
            state["n"] += 1
            return VRAM_FLOOR_GB / 4.0 if state["n"] == 1 else VRAM_FLOOR_GB * 4
        g["free_vram_gb"] = _probe
        install_vram_watchdog("bite_test_transient", interval_s=0.05,
                              consecutive=2)
    elif mode == "ram":
        g["free_ram_gb"] = lambda: MIN_FREE_AFTER_GB / 4.0
        install_memory_watchdog("bite_test_ram", interval_s=0.05, consecutive=2)
    time.sleep(6.0)
    print(f"SURVIVED {mode}")
    return 0


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reap", action="store_true",
                    help="clear a stale lock left by a killed job")
    ap.add_argument("--watchdog-bite-child", choices=("vram", "vram-transient",
                                                      "ram"),
                    help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.watchdog_bite_child:
        return _watchdog_bite_child(a.watchdog_bite_child)
    if a.selftest:
        return selftest_resource_guard()
    if a.reap:
        cur = _read_lock()
        if LOCK.exists() and not cur:
            print("lock exists but is unreadable -- refusing to clear without owner proof")
            return 1
        if cur and _pid_alive(int(cur.get("pid", -1))):
            print(f"lock held by LIVE pid {cur['pid']} ({cur.get('job')!r}) -- not clearing")
            return 1
        if LOCK.exists():
            LOCK.unlink()
            print("stale lock cleared")
        else:
            print("no lock")
        return 0
    live = live_jobs()
    print(json.dumps({"free_ram_gb": round(free_ram_gb(), 2),
                      "free_vram_gb": round(free_vram_gb(), 2),
                      "total_vram_gb": round(total_vram_gb(), 2),
                      "reserve_gb": RESERVE_GB,
                      "thrash_floor_gb": MIN_FREE_AFTER_GB,
                      "vram_floor_gb": VRAM_FLOOR_GB,
                      "live_jobs": live,
                      "live_declared_vram_gb": round(
                          sum(float(r.get("need_vram_gb", 0.0))
                              for r in live.values()), 2),
                      "lock": _read_lock()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
