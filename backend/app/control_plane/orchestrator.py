"""Provisioning orchestration.

The caller owns the outer transaction. This module flushes and does not
commit that transaction. It does not call database or migration adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.control_plane.models import (
    ProvisioningAttempt,
    ProvisioningAttemptStatus,
    ProvisioningOperation,
    ProvisioningRequest,
    ProvisioningState,
    Tenant,
    TenantDatabase,
    TenantStatus,
)
from app.control_plane.provisioning import (
    DuplicateProvisioningRequestError,
    create_provisioning_request,
    get_provisioning_request_by_idempotency_key,
    record_provisioning_attempt,
)

ProvisioningRequestStartOutcome = Literal["created", "existing"]


@dataclass(frozen=True)
class ProvisioningRequestStart:
    request: ProvisioningRequest
    outcome: ProvisioningRequestStartOutcome


def start_provisioning_request(
    db: Session,
    *,
    tenant_id: int,
    idempotency_key: str,
    operation: str,
    created_at: datetime,
    updated_at: datetime,
    target_revision: str | None = None,
) -> ProvisioningRequestStart:
    """Return the request for one tenant, operation, and idempotency key.

    An existing row is returned as ``existing`` and is not inserted again.
    A new row is inserted inside a savepoint. A concurrent insert that wins
    the idempotency unique constraint rolls back that savepoint only, then
    this function returns the stored row as ``existing``. Releasing the
    savepoint does not commit the caller's transaction. Other integrity
    errors propagate.
    """
    existing = get_provisioning_request_by_idempotency_key(
        db,
        tenant_id=tenant_id,
        operation=operation,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        return ProvisioningRequestStart(request=existing, outcome="existing")

    try:
        with db.begin_nested():
            request = create_provisioning_request(
                db,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                operation=operation,
                target_revision=target_revision,
                created_at=created_at,
                updated_at=updated_at,
            )
    except DuplicateProvisioningRequestError:
        winner = get_provisioning_request_by_idempotency_key(
            db,
            tenant_id=tenant_id,
            operation=operation,
            idempotency_key=idempotency_key,
        )
        if winner is None:
            raise
        return ProvisioningRequestStart(request=winner, outcome="existing")
    return ProvisioningRequestStart(request=request, outcome="created")


class ProvisioningRequestNotFoundError(Exception):
    pass


def allocate_provisioning_attempt(
    db: Session,
    *,
    request_id: int,
    status: str | None = None,
    alembic_revision_before: str | None = None,
    alembic_revision_after: str | None = None,
    error_code: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ProvisioningAttempt:
    """Insert the next attempt for an existing provisioning request.

    The ``provisioning_requests`` row is locked with ``FOR UPDATE`` before
    attempt numbers are read. The first number is ``1``. Each later number
    is one greater than the highest stored ``attempt_number``. The caller
    keeps the transaction open through the insert. This function does not
    commit or call ``Session.rollback()``.
    """
    request = db.get(ProvisioningRequest, request_id, with_for_update=True)
    if request is None:
        raise ProvisioningRequestNotFoundError
    highest = db.scalar(
        select(func.max(ProvisioningAttempt.attempt_number)).where(
            ProvisioningAttempt.request_id == request.id
        )
    )
    attempt_number = 1 if highest is None else int(highest) + 1
    return record_provisioning_attempt(
        db,
        request_id=request.id,
        attempt_number=attempt_number,
        status=status,
        alembic_revision_before=alembic_revision_before,
        alembic_revision_after=alembic_revision_after,
        error_code=error_code,
        started_at=started_at,
        finished_at=finished_at,
    )


class ProvisioningAttemptNotFoundError(Exception):
    pass


class ProvisioningAttemptAlreadyCompletedError(Exception):
    pass


_OPEN_ATTEMPT_STATUSES = frozenset({None, ProvisioningAttemptStatus.STARTED.value})
_COMPLETED_ATTEMPT_STATUSES = frozenset(
    {
        ProvisioningAttemptStatus.SUCCEEDED.value,
        ProvisioningAttemptStatus.FAILED.value,
    }
)


def complete_provisioning_attempt(
    db: Session,
    *,
    request_id: int,
    attempt_number: int,
    outcome: Literal["succeeded", "failed"],
    finished_at: datetime,
    alembic_revision_after: str | None = None,
    error_code: str | None = None,
) -> ProvisioningAttempt:
    """Record the outcome of one open provisioning attempt.

    The attempt row is locked with ``FOR UPDATE`` before its state is
    checked. A failure also locks the tenant row and sets provisioning
    ``status`` to ``failed``. A successful outcome does not change tenant
    provisioning status, company access status, or routing metadata. The
    caller keeps the transaction open. This function does not commit, roll
    back, or connect to a tenant database.
    """
    attempt = db.scalar(
        select(ProvisioningAttempt)
        .where(
            ProvisioningAttempt.request_id == request_id,
            ProvisioningAttempt.attempt_number == attempt_number,
        )
        .with_for_update()
    )
    if attempt is None:
        raise ProvisioningAttemptNotFoundError
    if (
        attempt.status in _COMPLETED_ATTEMPT_STATUSES
        or attempt.finished_at is not None
        or attempt.status not in _OPEN_ATTEMPT_STATUSES
    ):
        raise ProvisioningAttemptAlreadyCompletedError

    tenant: Tenant | None = None
    routing: TenantDatabase | None = None
    if outcome == "failed":
        request = db.get(ProvisioningRequest, attempt.request_id)
        if request is None:
            raise ProvisioningRequestNotFoundError
        tenant = db.get(Tenant, request.tenant_id, with_for_update=True)
        if tenant is None:
            raise ProvisioningRequestNotFoundError
        if request.operation == ProvisioningOperation.MIGRATE.value:
            routing = db.scalar(
                select(TenantDatabase).where(
                    TenantDatabase.tenant_id == tenant.id
                )
            )

    attempt.status = outcome
    attempt.alembic_revision_after = alembic_revision_after
    attempt.error_code = error_code
    attempt.finished_at = finished_at
    if tenant is not None:
        tenant.status = TenantStatus.FAILED.value
    if routing is not None:
        routing.provisioning_state = ProvisioningState.FAILED.value
    db.flush()
    return attempt
