"""Alembic environment for the control-plane history.

Run from the repository root:

    python -m alembic -c backend/alembic-control-plane.ini heads

``heads`` reads the revision files and does not open a database. Commands that
open a database require ``CONTROL_PLANE_DATABASE_URL``. This file does not use
the assessment engine, session, settings, or ``alembic_sqlalchemy_url()``.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.control_plane.base import CONTROL_PLANE_VERSION_TABLE, ControlPlaneBase
from app.control_plane.models import (  # noqa: F401
    PlatformAuditEvent,
    ProvisioningAttempt,
    ProvisioningRequest,
    Tenant,
    TenantDatabase,
)
from control_plane_migrations.url import (
    resolve_configured_control_plane_database_url,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = ControlPlaneBase.metadata


def get_url() -> str:
    return resolve_configured_control_plane_database_url(
        ini_sqlalchemy_url=config.get_main_option("sqlalchemy.url")
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        version_table=CONTROL_PLANE_VERSION_TABLE,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=CONTROL_PLANE_VERSION_TABLE,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
