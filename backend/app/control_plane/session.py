"""Control-plane engine and sessions.

Importing this module does not open a database. The engine is created on the
first call that needs it, using ``CONTROL_PLANE_DATABASE_URL`` and the checks
in ``control_plane_migrations.url``. Assessment code keeps using
``app.db.session``.

Future control-plane services should use ``get_control_plane_db`` as a FastAPI
dependency, or ``control_plane_session`` outside a request. Do not import this
module from assessment routes.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from control_plane_migrations.url import resolve_configured_control_plane_database_url

_session_factory: sessionmaker[Session] | None = None


def control_plane_sessionmaker(
    search_paths: list[Path] | None = None,
) -> sessionmaker[Session]:
    """Build a new session factory after the control-plane URL checks pass."""
    database_url = resolve_configured_control_plane_database_url(search_paths)
    engine = create_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_control_plane_sessionmaker() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = control_plane_sessionmaker()
    return _session_factory


def get_control_plane_engine() -> Engine:
    bind = get_control_plane_sessionmaker().kw["bind"]
    if not isinstance(bind, Engine):
        raise RuntimeError("Control-plane session factory has no engine.")
    return bind


def dispose_control_plane_engine() -> None:
    global _session_factory
    factory = _session_factory
    _session_factory = None
    if factory is None:
        return
    bind = factory.kw.get("bind")
    if isinstance(bind, Engine):
        bind.dispose()


@contextmanager
def control_plane_session() -> Generator[Session, None, None]:
    db = get_control_plane_sessionmaker()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_control_plane_db() -> Generator[Session, None, None]:
    with control_plane_session() as db:
        yield db
