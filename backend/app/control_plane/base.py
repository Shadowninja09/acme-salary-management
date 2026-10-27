"""Declarative metadata for the control-plane database.

This base is independent of ``app.db.base.Base``. Assessment models must not
inherit it, and control-plane models must not inherit the assessment base.
Import ``app.control_plane.models`` to register the control-plane tables.
"""

from sqlalchemy.orm import DeclarativeBase

# Alembic's default version table is ``alembic_version``. A separate name keeps
# this history from sharing that table with the assessment history.
CONTROL_PLANE_VERSION_TABLE = "alembic_version_control_plane"


class ControlPlaneBase(DeclarativeBase):
    pass
