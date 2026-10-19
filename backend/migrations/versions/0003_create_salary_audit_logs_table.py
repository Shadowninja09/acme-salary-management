"""create salary_audit_logs table

Revision ID: 0003_create_salary_audit_logs
Revises: 0002_create_salary_records
Create Date: 2026-10-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_create_salary_audit_logs"
down_revision: Union[str, Sequence[str], None] = "0002_create_salary_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("salary_record_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("old_values", JSONB(), nullable=True),
        sa.Column("new_values", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=100), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["salary_record_id"],
            ["salary_records.id"],
            name="fk_salary_audit_logs_salary_record_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action IN ('CREATE', 'UPDATE')",
            name="ck_salary_audit_logs_action",
        ),
        sa.CheckConstraint(
            "(action = 'CREATE') OR (action = 'UPDATE' AND reason IS NOT NULL AND length(trim(reason)) > 0)",
            name="ck_salary_audit_logs_update_reason",
        ),
    )
    op.create_index(
        "ix_salary_audit_logs_salary_record_id",
        "salary_audit_logs",
        ["salary_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_salary_audit_logs_salary_record_id",
        table_name="salary_audit_logs",
    )
    op.drop_table("salary_audit_logs")
