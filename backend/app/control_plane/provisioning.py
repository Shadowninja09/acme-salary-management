"""Provisioning request and attempt records.

The caller owns the transaction. These functions flush and do not commit.
They do not create a tenant database, run migrations, change routing, or
change company access status.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.control_plane.models import (
    ProvisioningAttempt,
    ProvisioningRequest,
    Tenant,
    TenantStatus,
)

REQUEST_IDEMPOTENCY_UNIQUE_CONSTRAINT = (
    "uq_provisioning_requests_tenant_id_operation_idempotency_key"
)
ATTEMPT_NUMBER_UNIQUE_CONSTRAINT = (
    "uq_provisioning_attempts_request_id_attempt_number"
)


class DuplicateProvisioningRequestError(Exception):
    pass


class DuplicateProvisioningAttemptError(Exception):
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
    if constraint_name == REQUEST_IDEMPOTENCY_UNIQUE_CONSTRAINT:
        raise DuplicateProvisioningRequestError from exc
    if constraint_name == ATTEMPT_NUMBER_UNIQUE_CONSTRAINT:
        raise DuplicateProvisioningAttemptError from exc


def create_provisioning_request(
    db: Session,
    *,
    tenant_id: int,
    idempotency_key: str,
    created_at: datetime,
    updated_at: datetime,
    operation: str | None = None,
    target_revision: str | None = None,
    conclusion: str | None = None,
) -> ProvisioningRequest:
    """Insert one logical provisioning request.

    ``operation``, ``target_revision``, and ``conclusion`` stay optional.
    When the tenant's provisioning ``status`` is unset, this records
    ``requested``. An existing provisioning status is left as it is.
    ``access_status`` is not written.
    """
    tenant = db.get(Tenant, tenant_id)
    if tenant is not None and tenant.status is None:
        tenant.status = TenantStatus.REQUESTED.value
    request = ProvisioningRequest(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        operation=operation,
        target_revision=target_revision,
        conclusion=conclusion,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(request)
    try:
        db.flush()
    except IntegrityError as exc:
        _raise_if_duplicate(exc)
        raise
    db.refresh(request)
    return request


def get_provisioning_request_by_id(
    db: Session, request_id: int
) -> ProvisioningRequest | None:
    return db.get(ProvisioningRequest, request_id)


def get_provisioning_request_by_idempotency_key(
    db: Session,
    *,
    tenant_id: int,
    operation: str | None,
    idempotency_key: str,
) -> ProvisioningRequest | None:
    statement = (
        select(ProvisioningRequest)
        .where(
            ProvisioningRequest.tenant_id == tenant_id,
            ProvisioningRequest.operation == operation,
            ProvisioningRequest.idempotency_key == idempotency_key,
        )
        .order_by(ProvisioningRequest.id)
    )
    return db.scalars(statement).first()


def record_provisioning_attempt(
    db: Session,
    *,
    request_id: int,
    attempt_number: int,
    status: str | None = None,
    alembic_revision_before: str | None = None,
    alembic_revision_after: str | None = None,
    error_code: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ProvisioningAttempt:
    """Insert one attempt row.

    ``target_revision`` is copied from the request. The caller supplies
    ``attempt_number``. Nullable attempt fields stay unset unless the caller
    passes them.
    """
    request = db.get(ProvisioningRequest, request_id)
    attempt = ProvisioningAttempt(
        request_id=request_id,
        attempt_number=attempt_number,
        status=status,
        target_revision=None if request is None else request.target_revision,
        alembic_revision_before=alembic_revision_before,
        alembic_revision_after=alembic_revision_after,
        error_code=error_code,
        started_at=started_at,
        finished_at=finished_at,
    )
    db.add(attempt)
    try:
        db.flush()
    except IntegrityError as exc:
        _raise_if_duplicate(exc)
        raise
    db.refresh(attempt)
    return attempt


def list_provisioning_attempts(
    db: Session, request_id: int
) -> list[ProvisioningAttempt]:
    """Return attempts for one request.

    Rows are ordered by ``started_at`` ascending, with null timestamps last,
    then by ``attempt_number``.
    """
    statement = (
        select(ProvisioningAttempt)
        .where(ProvisioningAttempt.request_id == request_id)
        .order_by(
            ProvisioningAttempt.started_at.asc().nulls_last(),
            ProvisioningAttempt.attempt_number.asc(),
        )
    )
    return list(db.scalars(statement).all())
