"""Spawn a sandboxed host process and watch it: exit, stop, hard timeout, health."""

import ctypes
import os
import resource
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import httpx

NOBODY_UID = 65534
NOBODY_GID = 65534
_PR_SET_PDEATHSIG = 1
# Kill-timeouts report the coreutils `timeout` convention.
TIMEOUT_EXIT_CODE = 124


def _set_parent_death_signal() -> None:
    """The child dies with its supervisor, so a crashed supervisor leaves no orphan."""
    if sys.platform.startswith("linux"):
        _ = int(ctypes.CDLL(None).prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0))


def sandbox_preexec() -> None:
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(NOBODY_GID)
        os.setuid(NOBODY_UID)
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    # After setuid: a credential change clears the parent-death signal.
    _set_parent_death_signal()


def spawn(
    command: list[str], cwd: Path, stdout: IO[bytes], stderr: IO[bytes]
) -> "subprocess.Popen[bytes]":
    """Own session + process group so the whole tree can be signalled."""
    return subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
        preexec_fn=sandbox_preexec,
    )


def _signal_group(process: "subprocess.Popen[bytes]", sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def terminate(process: "subprocess.Popen[bytes]", grace_seconds: float) -> int:
    """SIGTERM the process group, SIGKILL after the grace period; returns exit code."""
    _signal_group(process, signal.SIGTERM)
    try:
        return process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _signal_group(process, signal.SIGKILL)
        return process.wait()


def healthy(url: str, timeout_seconds: float) -> bool:
    try:
        response = httpx.get(
            url, timeout=timeout_seconds, follow_redirects=False, trust_env=False
        )
    except httpx.HTTPError:
        return False
    return 200 <= response.status_code < 300


@dataclass(frozen=True)
class Outcome:
    status: str  # success | failed | stopped | timeout | unhealthy
    exit_code: int


def supervise(
    process: "subprocess.Popen[bytes]",
    *,
    hard_timeout_seconds: float | None,
    health_url: str | None,
    alive_timeout_seconds: float,
    health_interval_seconds: float,
    grace_seconds: float,
    should_stop: Callable[[], bool],
    tick_seconds: float = 0.5,
) -> Outcome:
    """Block until the process ends or a rule kills it.

    hard_timeout_seconds: kill after this long no matter what (None = never).
    health_url: when set, kill once no 2xx answer arrived for alive_timeout_seconds;
    the clock starts at process start, which is also the startup grace.
    """
    started = time.monotonic()
    last_healthy = started
    next_check = started
    while True:
        code = process.poll()
        if code is not None:
            return Outcome("success" if code == 0 else "failed", code)

        if should_stop():
            return Outcome("stopped", terminate(process, grace_seconds))

        now = time.monotonic()
        if hard_timeout_seconds is not None and now - started >= hard_timeout_seconds:
            _ = terminate(process, grace_seconds)
            return Outcome("timeout", TIMEOUT_EXIT_CODE)

        if health_url is not None:
            if now >= next_check:
                if healthy(health_url, min(health_interval_seconds, 5.0)):
                    last_healthy = time.monotonic()
                next_check = time.monotonic() + health_interval_seconds
            if time.monotonic() - last_healthy > alive_timeout_seconds:
                _ = terminate(process, grace_seconds)
                return Outcome("unhealthy", TIMEOUT_EXIT_CODE)

        time.sleep(tick_seconds)
