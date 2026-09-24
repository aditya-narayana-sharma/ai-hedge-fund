"""Database engine and session handling.

Persistence is opt-in: without ``AI_HEDGE_FUND_DATABASE_URL`` the backend never
opens a connection and behaves exactly as it did before, which keeps
"clone and run" working with no database to provision.
"""

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.backend.database.models import Base

DATABASE_URL_ENV_VAR = "AI_HEDGE_FUND_DATABASE_URL"

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def database_url() -> Optional[str]:
    """Configured database URL, or None when persistence is disabled."""
    return os.environ.get(DATABASE_URL_ENV_VAR) or None


def is_enabled() -> bool:
    return database_url() is not None


def get_engine() -> Optional[Engine]:
    """Lazily create the engine so importing this module never connects."""
    global _engine, _session_factory

    url = database_url()
    if url is None:
        return None

    if _engine is None:
        # check_same_thread only applies to SQLite, where the run executes on a
        # worker thread while the request handler lives on the event loop.
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, future=True, connect_args=connect_args)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

    return _engine


def init_db() -> None:
    """Create any missing tables. Alembic owns schema changes after that."""
    engine = get_engine()
    if engine is not None:
        Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Optional[Session]]:
    """Yield a committed session, or None when persistence is disabled."""
    engine = get_engine()
    if engine is None or _session_factory is None:
        yield None
        return

    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Drop the cached engine so a new URL takes effect. Used by tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
