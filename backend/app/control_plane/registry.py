"""Tenant registry operations.

The caller owns the transaction. These functions flush and do not commit.
Pass a control-plane session. This module does not open the assessment
session and does not create a ``tenant_databases`` row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.control_plane.models import Tenant

PUBLIC_ID_UNIQUE_CONSTRAINT = "uq_tenants_public_id"
SLUG_UNIQUE_CONSTRAINT = "uq_tenants_slug"


class DuplicateTenantPublicIdError(Exception):
    pass


class DuplicateTenantSlugError(Exception):
    pass


def _constraint_name(exc: IntegrityError) -> str | None:
    orig = exc.orig
    if orig is None:
        return None
    diag = getattr(orig, "diag", None)
    if diag is None:
        return None
    name = getattr(diag, "constraint_name", None)
    if isinstance(name, str) and name:
        return name
    return None


def _raise_if_duplicate(exc: IntegrityError) -> None:
    constraint_name = _constraint_name(exc)
    if constraint_name == PUBLIC_ID_UNIQUE_CONSTRAINT:
        raise DuplicateTenantPublicIdError from exc
    if constraint_name == SLUG_UNIQUE_CONSTRAINT:
        raise DuplicateTenantSlugError from exc


def create_tenant(
    db: Session,
    *,
    created_at: datetime,
    updated_at: datetime,
    public_id: UUID | None = None,
    name: str | None = None,
    slug: str | None = None,
    status: str | None = None,
) -> Tenant:
    """Insert one registry row.

    ``created_at`` and ``updated_at`` are required because those columns are
    not null and have no database default. ``public_id``, ``name``, ``slug``,
    and provisioning ``status`` stay optional. This function does not choose
    a provisioning status. Company access is ``access_status``; that column
    is left unset so the database default ``onboard`` applies.
    """
    tenant = Tenant(
        public_id=public_id,
        name=name,
        slug=slug,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError as exc:
        _raise_if_duplicate(exc)
        raise
    db.refresh(tenant)
    return tenant


def get_tenant_by_id(db: Session, tenant_id: int) -> Tenant | None:
    return db.get(Tenant, tenant_id)


def get_tenant_by_public_id(db: Session, public_id: UUID) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.public_id == public_id))


def get_tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == slug))
