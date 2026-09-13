"""Conservative process identity checks across exit, permission and PID reuse races."""

from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ProcessIdentity:
    state: str
    created: float | None = None
    error: str | None = None


def inspect_process(pid: int) -> ProcessIdentity:
    try:
        if not psutil.pid_exists(pid):
            return ProcessIdentity("ABSENT")
        process = psutil.Process(pid)
        return ProcessIdentity("LIVE", process.create_time())
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return ProcessIdentity("ABSENT")
    except psutil.Error as exc:
        return ProcessIdentity("UNKNOWN", error=type(exc).__name__)


def original_process_running(record: dict) -> bool:
    # If the original was observed gone after Popen, a later reuse is irrelevant.
    if record.get("state") == "ABSENT":
        return False
    identity = inspect_process(record["pid"])
    if identity.state == "ABSENT":
        return False
    if identity.state == "UNKNOWN":
        raise RuntimeError(
            "Cannot determine previous simulator identity; refusing duplicate resume"
        )
    if record.get("created") is None:
        raise RuntimeError(
            "Previous simulator creation time unavailable; refusing duplicate resume"
        )
    return abs(identity.created - record["created"]) < 0.01
