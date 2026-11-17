"""Wake the scheduler worker the moment a schedule is submitted (Postgres LISTEN/NOTIFY).

NOTIFY is sent in the submitting transaction, so it only fires on commit. It is a
latency optimisation only: the schedule's trigger_at stays set, so a worker that
was down simply picks it up on its next cycle.
"""

import uuid
from typing import Any, final

from sqlalchemy import text
from sqlalchemy.orm import Session

from dxforge.db.session import engine

CHANNEL = "forge_dispatch"


def notify(session: Session, tenant_id: uuid.UUID, schedule_id: uuid.UUID) -> None:
    _ = session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": f"{tenant_id}:{schedule_id}"},
    )


def parse(payload: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    try:
        tenant_id, schedule_id = payload.split(":")
        return uuid.UUID(tenant_id), uuid.UUID(schedule_id)
    except ValueError:
        return None


@final
class Listener:
    """Dedicated autocommit connection subscribed to CHANNEL."""

    def __init__(self) -> None:
        self._connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        self._raw: Any = self._connection.connection.driver_connection
        _ = self._raw.execute(f"LISTEN {CHANNEL}")

    def wait(self, timeout_seconds: float) -> list[str]:
        """Block up to timeout_seconds; returns the payloads received."""
        return [
            str(notification.payload)
            for notification in self._raw.notifies(timeout=timeout_seconds, stop_after=1)
        ]

    def close(self) -> None:
        # Not returned to the pool: it is still LISTENing.
        self._connection.invalidate()
