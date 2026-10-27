import ast
import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.control_plane.models import (
    AccessStatus,
    ProvisioningRequest,
    TenantDatabase,
    TenantStatus,
)
from app.control_plane.provisioning import (
    DuplicateProvisioningAttemptError,
    DuplicateProvisioningRequestError,
    create_provisioning_request,
    get_provisioning_request_by_id,
    get_provisioning_request_by_idempotency_key,
    list_provisioning_attempts,
    record_provisioning_attempt,
)
from app.control_plane.registry import create_tenant
from app.core.test_database import default_env_file_paths
from app.db.session import SessionLocal
from control_plane_migrations.url import resolve_control_plane_sqlalchemy_url

_CREATED_AT = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
_UPDATED_AT = datetime(2026, 10, 27, 12, 5, tzinfo=timezone.utc)


def _configured_database_url(env_name: str) -> str | None:
    from_env = os.environ.get(env_name, "").strip()
    if from_env and make_url(from_env).database != "acme_unused":
        return from_env
    for path in default_env_file_paths():
        if not path.is_file():
            continue
        value = (dotenv_values(path).get(env_name) or "").strip()
        if value:
            return value
    return None


def _control_plane_database_url() -> str:
    assessment_url = _configured_database_url("DATABASE_URL")
    if assessment_url is None:
        pytest.fail("DATABASE_URL is not configured; acme_salary will not be used")
    control_url = make_url(assessment_url).set(database="acme_control_plane")
    if control_url.database != "acme_control_plane":
        pytest.fail("Refusing a control-plane test target other than acme_control_plane")
    return resolve_control_plane_sqlalchemy_url(
        control_url.render_as_string(hide_password=False),
        assessment_database_url=assessment_url,
        test_database_url=_configured_database_url("TEST_DATABASE_URL"),
    )


@pytest.fixture
def provisioning_session() -> Generator[Session, None, None]:
    engine: Engine = create_engine(_control_plane_database_url())
    assert engine.url.database == "acme_control_plane"
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans: object) -> None:
        nonlocal nested
        if connection.closed:
            return
        if not connection.in_nested_transaction():
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


def _tenant(session: Session, **overrides: object):
    values: dict[str, object] = {
        "created_at": _CREATED_AT,
        "updated_at": _UPDATED_AT,
        "public_id": uuid4(),
        "name": "Northwind",
        "slug": f"northwind-{uuid4().hex[:8]}",
        "status": None,
    }
    values.update(overrides)
    return create_tenant(session, **values)  # type: ignore[arg-type]


def _request(session: Session, tenant_id: int, **overrides: object):
    values: dict[str, object] = {
        "tenant_id": tenant_id,
        "idempotency_key": "create-1",
        "created_at": _CREATED_AT,
        "updated_at": _UPDATED_AT,
        "operation": "create_database",
        "target_revision": None,
        "conclusion": None,
    }
    values.update(overrides)
    return create_provisioning_request(session, **values)  # type: ignore[arg-type]


def test_create_tenant_does_not_start_provisioning(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)

    assert tenant.status is None
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert (
        provisioning_session.scalar(
            select(func.count()).select_from(ProvisioningRequest)
        )
        == 0
    )
    assert provisioning_session.scalars(select(TenantDatabase)).all() == []


def test_create_and_retrieve_provisioning_request(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)
    created = _request(
        provisioning_session,
        tenant.id,
        idempotency_key="migrate-1",
        operation="migrate",
        target_revision="0004_create_user_sessions",
        conclusion="open",
    )

    assert created.id is not None
    assert tenant.status == TenantStatus.REQUESTED.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert get_provisioning_request_by_id(provisioning_session, created.id) is created
    found = get_provisioning_request_by_idempotency_key(
        provisioning_session,
        tenant_id=tenant.id,
        operation="migrate",
        idempotency_key="migrate-1",
    )
    assert found is created
    assert (
        get_provisioning_request_by_idempotency_key(
            provisioning_session,
            tenant_id=tenant.id,
            operation="migrate",
            idempotency_key="missing",
        )
        is None
    )
    assert get_provisioning_request_by_id(provisioning_session, 999_999) is None
    assert provisioning_session.scalars(select(TenantDatabase)).all() == []
    assert provisioning_session.in_transaction()


def test_duplicate_idempotency_key_and_distinct_operations(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)
    _request(provisioning_session, tenant.id, idempotency_key="same")

    with pytest.raises(DuplicateProvisioningRequestError):
        _request(provisioning_session, tenant.id, idempotency_key="same")
    provisioning_session.rollback()

    tenant = _tenant(provisioning_session)
    other = _tenant(provisioning_session, slug=f"other-{uuid4().hex[:8]}")
    _request(provisioning_session, tenant.id, idempotency_key="same")
    migrate = _request(
        provisioning_session,
        tenant.id,
        idempotency_key="same",
        operation="migrate",
        target_revision="0004_create_user_sessions",
    )
    other_request = _request(
        provisioning_session, other.id, idempotency_key="same"
    )

    assert migrate.id != other_request.id
    assert (
        get_provisioning_request_by_idempotency_key(
            provisioning_session,
            tenant_id=tenant.id,
            operation="create_database",
            idempotency_key="same",
        )
        is not None
    )


def test_existing_provisioning_status_is_not_reset_to_requested(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session, status="provisioning")
    _request(provisioning_session, tenant.id, idempotency_key="again")

    assert tenant.status == TenantStatus.PROVISIONING.value
    assert tenant.access_status == AccessStatus.ONBOARD.value


def test_request_constraints_reject_invalid_values(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)

    with pytest.raises(IntegrityError):
        _request(
            provisioning_session,
            tenant.id,
            operation="drop_database",
        )
    provisioning_session.rollback()

    tenant = _tenant(provisioning_session)
    with pytest.raises(IntegrityError):
        _request(
            provisioning_session,
            tenant.id,
            conclusion="active",
        )
    provisioning_session.rollback()

    tenant = _tenant(provisioning_session)
    with pytest.raises(IntegrityError):
        _request(
            provisioning_session,
            tenant.id,
            operation="migrate",
            target_revision=None,
        )
    provisioning_session.rollback()

    tenant = _tenant(provisioning_session)
    with pytest.raises(IntegrityError):
        _request(
            provisioning_session,
            tenant.id,
            operation="create_database",
            target_revision="0004_create_user_sessions",
        )
    provisioning_session.rollback()

    with pytest.raises(IntegrityError):
        _request(provisioning_session, 999_999, idempotency_key="missing-tenant")


def test_record_and_order_attempts(provisioning_session: Session) -> None:
    tenant = _tenant(provisioning_session)
    request = _request(
        provisioning_session,
        tenant.id,
        operation="migrate",
        target_revision="0004_create_user_sessions",
    )
    later = _CREATED_AT + timedelta(hours=2)
    earlier = _CREATED_AT + timedelta(hours=1)
    third = record_provisioning_attempt(
        provisioning_session,
        request_id=request.id,
        attempt_number=3,
        status="started",
        started_at=later,
    )
    first = record_provisioning_attempt(
        provisioning_session,
        request_id=request.id,
        attempt_number=1,
        status="failed",
        started_at=earlier,
        error_code="migration_failed",
    )
    untimed = record_provisioning_attempt(
        provisioning_session,
        request_id=request.id,
        attempt_number=2,
        status="succeeded",
    )

    assert first.target_revision == "0004_create_user_sessions"
    assert untimed.target_revision == "0004_create_user_sessions"
    assert untimed.finished_at is None
    assert [item.id for item in list_provisioning_attempts(provisioning_session, request.id)] == [
        first.id,
        third.id,
        untimed.id,
    ]
    assert list_provisioning_attempts(provisioning_session, 999_999) == []
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert provisioning_session.scalars(select(TenantDatabase)).all() == []


def test_duplicate_attempt_number_and_invalid_attempt_status(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)
    request = _request(provisioning_session, tenant.id)
    record_provisioning_attempt(
        provisioning_session,
        request_id=request.id,
        attempt_number=1,
        status="started",
    )

    with pytest.raises(DuplicateProvisioningAttemptError):
        record_provisioning_attempt(
            provisioning_session,
            request_id=request.id,
            attempt_number=1,
        )
    provisioning_session.rollback()

    tenant = _tenant(provisioning_session)
    request = _request(provisioning_session, tenant.id)
    with pytest.raises(IntegrityError):
        record_provisioning_attempt(
            provisioning_session,
            request_id=request.id,
            attempt_number=1,
            status="open",
        )
    provisioning_session.rollback()

    with pytest.raises(IntegrityError):
        record_provisioning_attempt(
            provisioning_session,
            request_id=999_999,
            attempt_number=1,
        )


def test_provisioning_writes_stay_in_the_caller_transaction(
    provisioning_session: Session,
) -> None:
    tenant = _tenant(provisioning_session)
    request = _request(provisioning_session, tenant.id)
    record_provisioning_attempt(
        provisioning_session,
        request_id=request.id,
        attempt_number=1,
    )
    bind = provisioning_session.get_bind()
    with bind.engine.connect() as other:
        stored = other.execute(
            text(
                "select count(*) from provisioning_requests "
                "where idempotency_key = :key"
            ),
            {"key": "create-1"},
        ).scalar_one()
    assert stored == 0
    assert provisioning_session.in_transaction()
    assert SessionLocal.kw["bind"] is not bind

    provisioning_session.rollback()
    assert get_provisioning_request_by_id(provisioning_session, request.id) is None


def test_provisioning_module_does_not_open_the_assessment_session() -> None:
    source = Path(create_provisioning_request.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    parsed = ast.parse(source)
    imported = {
        node.module
        for node in parsed.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.db.session" not in imported
    assert "SessionLocal" not in source
    assert ".commit(" not in source
