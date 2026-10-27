"""create control-plane tables

Revision ID: 0001_create_control_plane_tables
Revises:
Create Date: 2026-10-27

Applying this revision requires an explicit sqlalchemy.url on
alembic-control-plane.ini. This file does not read DATABASE_URL.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_control_plane_tables"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column(
            "access_status",
            sa.Text(),
            server_default=sa.text("'onboard'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_tenants_public_id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint(
            "status IN ('requested', 'provisioning', 'migrating', 'ready', "
            "'failed', 'suspended')",
            name="ck_tenants_status",
        ),
        sa.CheckConstraint(
            "access_status IN ('onboard', 'active', 'deactivated')",
            name="ck_tenants_access_status",
        ),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])

    op.create_table(
        "tenant_databases",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("instance_ref", sa.Text(), nullable=True),
        sa.Column("database_name", sa.Text(), nullable=True),
        sa.Column("secret_ref", sa.Text(), nullable=True),
        sa.Column("migration_secret_ref", sa.Text(), nullable=True),
        sa.Column("provisioning_state", sa.Text(), nullable=True),
        sa.Column("routing_disposition", sa.Text(), nullable=True),
        sa.Column("schema_revision", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_databases_tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_databases_tenant_id"),
        sa.UniqueConstraint(
            "instance_ref",
            "database_name",
            name="uq_tenant_databases_instance_ref_database_name",
        ),
        sa.CheckConstraint(
            "provisioning_state IN ('pending', 'database_created', 'migrated', "
            "'admin_bootstrapped', 'ready', 'failed')",
            name="ck_tenant_databases_provisioning_state",
        ),
        sa.CheckConstraint(
            "routing_disposition IN ('in_service', 'quarantined', 'dropped')",
            name="ck_tenant_databases_routing_disposition",
        ),
    )

    op.create_table(
        "provisioning_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("target_revision", sa.Text(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_provisioning_requests_tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "operation",
            "idempotency_key",
            name="uq_provisioning_requests_tenant_id_operation_idempotency_key",
        ),
        sa.CheckConstraint(
            "operation IN ('create_database', 'migrate', 'bootstrap_admin')",
            name="ck_provisioning_requests_operation",
        ),
        sa.CheckConstraint(
            "conclusion IN ('open', 'succeeded', 'failed')",
            name="ck_provisioning_requests_conclusion",
        ),
        sa.CheckConstraint(
            "(operation = 'migrate' AND target_revision IS NOT NULL) "
            "OR (operation <> 'migrate' AND target_revision IS NULL)",
            name="ck_provisioning_requests_target_revision",
        ),
    )

    op.create_table(
        "provisioning_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_number", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("target_revision", sa.Text(), nullable=True),
        sa.Column("alembic_revision_before", sa.Text(), nullable=True),
        sa.Column("alembic_revision_after", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["provisioning_requests.id"],
            name="fk_provisioning_attempts_request_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "request_id",
            "attempt_number",
            name="uq_provisioning_attempts_request_id_attempt_number",
        ),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed')",
            name="ck_provisioning_attempts_status",
        ),
    )
    op.create_index(
        "ix_provisioning_attempts_request_id_started_at",
        "provisioning_attempts",
        ["request_id", "started_at"],
    )

    op.create_table(
        "platform_audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("target_tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["target_tenant_id"],
            ["tenants.id"],
            name="fk_platform_audit_events_target_tenant_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure')",
            name="ck_platform_audit_events_outcome",
        ),
    )
    op.create_index(
        "ix_platform_audit_events_target_tenant_id_created_at",
        "platform_audit_events",
        ["target_tenant_id", "created_at"],
    )
    op.create_index(
        "ix_platform_audit_events_actor_ref_created_at",
        "platform_audit_events",
        ["actor_ref", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("platform_audit_events")
    op.drop_table("provisioning_attempts")
    op.drop_table("provisioning_requests")
    op.drop_table("tenant_databases")
    op.drop_table("tenants")
