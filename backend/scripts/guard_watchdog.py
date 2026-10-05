#!/usr/bin/env python
"""Watch system memory and kill a target process before the OS thrashes into a reboot.

Usage (from backend/):
    ./venv/bin/python scripts/guard_watchdog.py <pid> [min_avail_gb=2.0] [max_swap_gb=5.0]

A Mac that is already frozen cannot run anything, so this acts on the *pre-freeze*
signal: when free RAM falls below min_avail_gb, or swap in use reaches max_swap_gb,
it SIGKILLs the target process and all its children, then exits.
"""

import sys
import time

import psutil


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: guard_watchdog.py <pid> [min_avail_gb=2.0] [max_swap_gb=5.0]")
        raise SystemExit(2)

    pid = int(sys.argv[1])
    min_avail = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    max_swap = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[watchdog] pid {pid} is not running")
        return

    while proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        avail = vm.available / 1e9
        swap = sw.used / 1e9
        print(f"[watchdog] avail={avail:.2f}GB swap={swap:.2f}GB", flush=True)

        if avail < min_avail or swap >= max_swap:
            print(
                f"[watchdog] CRITICAL -> killing pid {pid} and children "
                f"(avail={avail:.2f}GB swap={swap:.2f}GB)",
                flush=True,
            )
            try:
                for child in proc.children(recursive=True):
                    child.kill()
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
            return

        time.sleep(2)

    print("[watchdog] target finished; exiting", flush=True)


if __name__ == "__main__":
    main()
