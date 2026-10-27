"""Control-plane tables from the current schema proposal.

Character lengths are not specified, so character columns use unbounded text.
Nullability and defaults are included only where the proposal states them.
No assessment model is imported here.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    JSON,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.control_plane.base import ControlPlaneBase


class TenantStatus(StrEnum):
    REQUESTED = "requested"
    PROVISIONING = "provisioning"
    MIGRATING = "migrating"
    READY = "ready"
    FAILED = "failed"
    SUSPENDED = "suspended"


class AccessStatus(StrEnum):
    ONBOARD = "onboard"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class ProvisioningState(StrEnum):
    PENDING = "pending"
    DATABASE_CREATED = "database_created"
    MIGRATED = "migrated"
    ADMIN_BOOTSTRAPPED = "admin_bootstrapped"
    READY = "ready"
    FAILED = "failed"


class RoutingDisposition(StrEnum):
    IN_SERVICE = "in_service"
    QUARANTINED = "quarantined"
    DROPPED = "dropped"


class ProvisioningOperation(StrEnum):
    CREATE_DATABASE = "create_database"
    MIGRATE = "migrate"
    BOOTSTRAP_ADMIN = "bootstrap_admin"


class ProvisioningConclusion(StrEnum):
    OPEN = "open"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ProvisioningAttemptStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PlatformAuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


def _value_check(column: str, values: type[StrEnum]) -> str:
    listed = ", ".join(f"'{member.value}'" for member in values)
    return f"{column} IN ({listed})"


TENANT_STATUS_CHECK = _value_check("status", TenantStatus)
TENANT_ACCESS_STATUS_CHECK = _value_check("access_status", AccessStatus)
TENANT_DATABASE_PROVISIONING_STATE_CHECK = _value_check(
    "provisioning_state", ProvisioningState
)
TENANT_DATABASE_ROUTING_DISPOSITION_CHECK = _value_check(
    "routing_disposition", RoutingDisposition
)
PROVISIONING_REQUEST_OPERATION_CHECK = _value_check(
    "operation", ProvisioningOperation
)
PROVISIONING_REQUEST_CONCLUSION_CHECK = _value_check(
    "conclusion", ProvisioningConclusion
)
PROVISIONING_REQUEST_TARGET_REVISION_CHECK = (
    "(operation = 'migrate' AND target_revision IS NOT NULL) "
    "OR (operation <> 'migrate' AND target_revision IS NULL)"
)
PROVISIONING_ATTEMPT_STATUS_CHECK = _value_check(
    "status", ProvisioningAttemptStatus
)
PLATFORM_AUDIT_OUTCOME_CHECK = _value_check("outcome", PlatformAuditOutcome)


class Tenant(ControlPlaneBase):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_tenants_public_id"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
        CheckConstraint(TENANT_STATUS_CHECK, name="ck_tenants_status"),
        CheckConstraint(TENANT_ACCESS_STATUS_CHECK, name="ck_tenants_access_status"),
        Index("ix_tenants_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str | None] = mapped_column(Text)
    slug: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    access_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'onboard'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TenantDatabase(ControlPlaneBase):
    __tablename__ = "tenant_databases"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_databases_tenant_id"),
        UniqueConstraint(
            "instance_ref",
            "database_name",
            name="uq_tenant_databases_instance_ref_database_name",
        ),
        CheckConstraint(
            TENANT_DATABASE_PROVISIONING_STATE_CHECK,
            name="ck_tenant_databases_provisioning_state",
        ),
        CheckConstraint(
            TENANT_DATABASE_ROUTING_DISPOSITION_CHECK,
            name="ck_tenant_databases_routing_disposition",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "tenants.id",
            ondelete="RESTRICT",
            name="fk_tenant_databases_tenant_id",
        ),
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(Text)
    instance_ref: Mapped[str | None] = mapped_column(Text)
    database_name: Mapped[str | None] = mapped_column(Text)
    secret_ref: Mapped[str | None] = mapped_column(Text)
    migration_secret_ref: Mapped[str | None] = mapped_column(Text)
    provisioning_state: Mapped[str | None] = mapped_column(Text)
    routing_disposition: Mapped[str | None] = mapped_column(Text)
    schema_revision: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProvisioningRequest(ControlPlaneBase):
    __tablename__ = "provisioning_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "operation",
            "idempotency_key",
            name="uq_provisioning_requests_tenant_id_operation_idempotency_key",
        ),
        CheckConstraint(
            PROVISIONING_REQUEST_OPERATION_CHECK,
            name="ck_provisioning_requests_operation",
        ),
        CheckConstraint(
            PROVISIONING_REQUEST_CONCLUSION_CHECK,
            name="ck_provisioning_requests_conclusion",
        ),
        CheckConstraint(
            PROVISIONING_REQUEST_TARGET_REVISION_CHECK,
            name="ck_provisioning_requests_target_revision",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "tenants.id",
            ondelete="RESTRICT",
            name="fk_provisioning_requests_tenant_id",
        ),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str | None] = mapped_column(Text)
    target_revision: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProvisioningAttempt(ControlPlaneBase):
    __tablename__ = "provisioning_attempts"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "attempt_number",
            name="uq_provisioning_attempts_request_id_attempt_number",
        ),
        CheckConstraint(
            PROVISIONING_ATTEMPT_STATUS_CHECK,
            name="ck_provisioning_attempts_status",
        ),
        Index(
            "ix_provisioning_attempts_request_id_started_at",
            "request_id",
            "started_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "provisioning_requests.id",
            ondelete="RESTRICT",
            name="fk_provisioning_attempts_request_id",
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str | None] = mapped_column(Text)
    target_revision: Mapped[str | None] = mapped_column(Text)
    alembic_revision_before: Mapped[str | None] = mapped_column(Text)
    alembic_revision_after: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformAuditEvent(ControlPlaneBase):
    __tablename__ = "platform_audit_events"
    __table_args__ = (
        CheckConstraint(
            PLATFORM_AUDIT_OUTCOME_CHECK,
            name="ck_platform_audit_events_outcome",
        ),
        Index(
            "ix_platform_audit_events_target_tenant_id_created_at",
            "target_tenant_id",
            "created_at",
        ),
        Index(
            "ix_platform_audit_events_actor_ref_created_at",
            "actor_ref",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_ref: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    target_tenant_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "tenants.id",
            ondelete="RESTRICT",
            name="fk_platform_audit_events_target_tenant_id",
        ),
    )
    outcome: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[Any | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


__all__ = [
    "AccessStatus",
    "PlatformAuditEvent",
    "PlatformAuditOutcome",
    "ProvisioningAttempt",
    "ProvisioningAttemptStatus",
    "ProvisioningConclusion",
    "ProvisioningOperation",
    "ProvisioningRequest",
    "ProvisioningState",
    "RoutingDisposition",
    "Tenant",
    "TenantDatabase",
    "TenantStatus",
]
