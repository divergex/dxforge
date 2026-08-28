import uuid

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, SessionTransaction

from dxforge.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)


def _tenant_context_listener(tenant_id: str):
    # SET accepts no bind parameters, so the value is interpolated.
    # tenant_id is a UUID string from str(uuid.UUID(...))
    statement = text(f"SET LOCAL app.tenant_id = '{tenant_id}'")

    def _set_tenant_context(
        _session: Session, _transaction: SessionTransaction, connection: Connection
    ) -> None:
        _ = connection.execute(statement)

    return _set_tenant_context


def session_factory(tenant_id: uuid.UUID | str) -> Session:
    session = Session(bind=engine, expire_on_commit=False)
    event.listen(session, "after_begin", _tenant_context_listener(str(tenant_id)))
    return session
