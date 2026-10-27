import os
from collections.abc import Generator
from datetime import datetime, timezone
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
    ProvisioningAttempt,
    ProvisioningRequest,
    TenantDatabase,
    TenantStatus,
)
from app.control_plane.orchestrator import (
    ProvisioningAttemptAlreadyCompletedError,
    ProvisioningAttemptNotFoundError,
    ProvisioningRequestNotFoundError,
    allocate_provisioning_attempt,
    complete_provisioning_attempt,
    start_provisioning_request,
)
from app.control_plane.provisioning import (
    create_provisioning_request,
    get_provisioning_request_by_idempotency_key,
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
def orchestrator_session() -> Generator[Session, None, None]:
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


def _count_requests(session: Session, tenant_id: int) -> int:
    return session.scalar(
        select(func.count())
        .select_from(ProvisioningRequest)
        .where(ProvisioningRequest.tenant_id == tenant_id)
    ) or 0


def test_first_start_creates_one_request(orchestrator_session: Session) -> None:
    tenant = _tenant(orchestrator_session)
    started = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    assert started.outcome == "created"
    assert started.request.id is not None
    assert started.request.tenant_id == tenant.id
    assert tenant.status == TenantStatus.REQUESTED.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert _count_requests(orchestrator_session, tenant.id) == 1


def test_same_triple_returns_the_existing_row(
    orchestrator_session: Session,
) -> None:
    tenant = _tenant(orchestrator_session)
    first = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    second = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    assert second.outcome == "existing"
    assert second.request is first.request
    assert _count_requests(orchestrator_session, tenant.id) == 1
    assert tenant.access_status == AccessStatus.ONBOARD.value


def test_different_idempotency_key_creates_another_request(
    orchestrator_session: Session,
) -> None:
    tenant = _tenant(orchestrator_session, status="provisioning")
    first = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    second = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-2",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    assert first.outcome == "created"
    assert second.outcome == "created"
    assert second.request.id != first.request.id
    assert tenant.status == TenantStatus.PROVISIONING.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert _count_requests(orchestrator_session, tenant.id) == 2


def test_start_does_not_commit_caller_work(orchestrator_session: Session) -> None:
    tenant = _tenant(orchestrator_session)
    started = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    bind = orchestrator_session.get_bind()
    with bind.engine.connect() as other:
        stored = other.execute(
            text(
                "select count(*) from provisioning_requests "
                "where idempotency_key = :key"
            ),
            {"key": "create-1"},
        ).scalar_one()

    assert stored == 0
    assert orchestrator_session.in_transaction()
    assert SessionLocal.kw["bind"] is not bind
    orchestrator_session.rollback()
    assert (
        get_provisioning_request_by_idempotency_key(
            orchestrator_session,
            tenant_id=tenant.id,
            operation="create_database",
            idempotency_key="create-1",
        )
        is None
    )
    assert started.outcome == "created"


def test_unrelated_integrity_errors_propagate(
    orchestrator_session: Session,
) -> None:
    tenant = _tenant(orchestrator_session)
    kept = create_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="kept",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    with pytest.raises(IntegrityError):
        start_provisioning_request(
            orchestrator_session,
            tenant_id=tenant.id,
            idempotency_key="bad-operation",
            operation="drop_database",
            created_at=_CREATED_AT,
            updated_at=_UPDATED_AT,
        )

    assert orchestrator_session.get(ProvisioningRequest, kept.id) is not None
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert _count_requests(orchestrator_session, tenant.id) == 1


def test_idempotency_race_keeps_unrelated_caller_work(
    orchestrator_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = _tenant(orchestrator_session)
    winner = create_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    tenant.name = "Caller work"
    other = _tenant(orchestrator_session, slug=f"other-{uuid4().hex[:8]}")
    orchestrator_session.flush()

    import app.control_plane.orchestrator as orchestrator

    real_lookup = orchestrator.get_provisioning_request_by_idempotency_key
    calls = {"count": 0}

    def hide_first_lookup(db: Session, **kwargs: object):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return real_lookup(db, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        orchestrator,
        "get_provisioning_request_by_idempotency_key",
        hide_first_lookup,
    )
    rollback_calls = {"count": 0}
    original_rollback = orchestrator_session.rollback

    def spy_rollback() -> None:
        rollback_calls["count"] += 1
        original_rollback()

    monkeypatch.setattr(orchestrator_session, "rollback", spy_rollback)

    started = start_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    assert started.outcome == "existing"
    assert started.request.id == winner.id
    assert calls["count"] == 2
    assert rollback_calls["count"] == 0
    assert tenant.name == "Caller work"
    assert orchestrator_session.get(type(other), other.id) is not None
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert _count_requests(orchestrator_session, tenant.id) == 1


def _migrate_request(session: Session, tenant_id: int):
    return create_provisioning_request(
        session,
        tenant_id=tenant_id,
        idempotency_key="migrate-1",
        operation="migrate",
        target_revision="0004_create_user_sessions",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


def test_first_allocated_attempt_is_number_one(
    orchestrator_session: Session,
) -> None:
    """One session shows the first allocated number. It does not prove locking."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    attempt = allocate_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        status="started",
        started_at=_CREATED_AT,
    )

    assert attempt.attempt_number == 1
    assert attempt.target_revision == "0004_create_user_sessions"
    assert tenant.access_status == AccessStatus.ONBOARD.value


def test_later_allocated_attempts_are_numbered_two_then_three(
    orchestrator_session: Session,
) -> None:
    """Sequential calls in one session receive 2, then 3.

    This does not prove that concurrent sessions serialize on the row lock.
    """
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    allocate_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        status="started",
    )
    second = allocate_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        status="failed",
    )
    third = allocate_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        status="succeeded",
    )

    assert second.attempt_number == 2
    assert third.attempt_number == 3
    assert second.target_revision == "0004_create_user_sessions"
    assert third.target_revision == "0004_create_user_sessions"


def test_missing_request_raises_provisioning_request_not_found(
    orchestrator_session: Session,
) -> None:
    with pytest.raises(ProvisioningRequestNotFoundError):
        allocate_provisioning_attempt(
            orchestrator_session,
            request_id=999_999,
            status="started",
        )

    assert orchestrator_session.get(ProvisioningRequest, 999_999) is None
    assert (
        orchestrator_session.scalar(
            select(func.count())
            .select_from(ProvisioningAttempt)
            .where(ProvisioningAttempt.request_id == 999_999)
        )
        == 0
    )


def test_allocate_attempt_does_not_commit_caller_work(
    orchestrator_session: Session,
) -> None:
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    allocate_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        status="started",
    )
    bind = orchestrator_session.get_bind()
    with bind.engine.connect() as other:
        stored = other.execute(
            text(
                "select count(*) from provisioning_attempts "
                "where request_id = :request_id"
            ),
            {"request_id": request.id},
        ).scalar_one()

    assert stored == 0
    assert orchestrator_session.in_transaction()
    assert SessionLocal.kw["bind"] is not bind


def test_attempt_constraint_error_propagates_without_session_rollback(
    orchestrator_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    tenant.name = "Caller work"
    orchestrator_session.flush()
    rollback_calls = {"count": 0}
    original_rollback = orchestrator_session.rollback

    def spy_rollback() -> None:
        rollback_calls["count"] += 1
        original_rollback()

    monkeypatch.setattr(orchestrator_session, "rollback", spy_rollback)

    with pytest.raises(IntegrityError):
        allocate_provisioning_attempt(
            orchestrator_session,
            request_id=request.id,
            status="open",
        )

    assert rollback_calls["count"] == 0


def _started_attempt(session: Session, request_id: int) -> ProvisioningAttempt:
    return record_provisioning_attempt(
        session,
        request_id=request_id,
        attempt_number=1,
        status="started",
        alembic_revision_before="0003_create_salary_audit_logs",
        started_at=_CREATED_AT,
    )


def _routing_row(session: Session, tenant_id: int) -> TenantDatabase:
    row = TenantDatabase(
        tenant_id=tenant_id,
        provisioning_state="migrated",
        routing_disposition="in_service",
        schema_revision="0004_create_user_sessions",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    session.add(row)
    session.flush()
    return row


def test_one_session_completes_started_attempt_without_proving_locking(
    orchestrator_session: Session,
) -> None:
    """One session records a successful completion. It does not prove locking."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    attempt = _started_attempt(orchestrator_session, request.id)
    finished_at = datetime(2026, 10, 27, 13, 0, tzinfo=timezone.utc)

    completed = complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=attempt.attempt_number,
        outcome="succeeded",
        finished_at=finished_at,
        alembic_revision_after="0004_create_user_sessions",
    )

    assert completed.status == "succeeded"
    assert completed.finished_at == finished_at
    assert completed.alembic_revision_after == "0004_create_user_sessions"
    assert completed.target_revision == "0004_create_user_sessions"
    assert completed.alembic_revision_before == "0003_create_salary_audit_logs"
    assert completed.started_at == _CREATED_AT
    assert tenant.status == TenantStatus.REQUESTED.value
    assert tenant.status != TenantStatus.READY.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert tenant.updated_at == _UPDATED_AT
    assert request.conclusion is None


def test_one_session_failure_sets_tenant_status_and_preserves_access(
    orchestrator_session: Session,
) -> None:
    """One session records a failure. It does not prove locking or isolation."""
    tenant = _tenant(orchestrator_session)
    request = create_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    attempt = _started_attempt(orchestrator_session, request.id)
    finished_at = datetime(2026, 10, 27, 13, 0, tzinfo=timezone.utc)

    completed = complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=1,
        outcome="failed",
        finished_at=finished_at,
        error_code="database_create_failed",
    )

    assert completed.status == "failed"
    assert completed.error_code == "database_create_failed"
    assert completed.finished_at == finished_at
    assert tenant.status == TenantStatus.FAILED.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert tenant.updated_at == _UPDATED_AT
    assert request.conclusion is None


def test_one_session_repeat_completion_preserves_the_first_outcome(
    orchestrator_session: Session,
) -> None:
    """A second completion raises. This session does not prove concurrent locking."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    _started_attempt(orchestrator_session, request.id)
    finished_at = datetime(2026, 10, 27, 13, 0, tzinfo=timezone.utc)
    complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=1,
        outcome="succeeded",
        finished_at=finished_at,
        alembic_revision_after="0004_create_user_sessions",
    )

    with pytest.raises(ProvisioningAttemptAlreadyCompletedError):
        complete_provisioning_attempt(
            orchestrator_session,
            request_id=request.id,
            attempt_number=1,
            outcome="succeeded",
            finished_at=datetime(2026, 10, 27, 14, 0, tzinfo=timezone.utc),
            alembic_revision_after="other",
        )

    stored = orchestrator_session.scalar(
        select(ProvisioningAttempt).where(
            ProvisioningAttempt.request_id == request.id,
            ProvisioningAttempt.attempt_number == 1,
        )
    )
    assert stored is not None
    assert stored.status == "succeeded"
    assert stored.finished_at == finished_at
    assert stored.alembic_revision_after == "0004_create_user_sessions"
    assert tenant.status == TenantStatus.REQUESTED.value


def test_one_session_missing_attempt_raises_not_found(
    orchestrator_session: Session,
) -> None:
    """A missing attempt raises. This session does not prove concurrent locking."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)

    with pytest.raises(ProvisioningAttemptNotFoundError):
        complete_provisioning_attempt(
            orchestrator_session,
            request_id=request.id,
            attempt_number=99,
            outcome="failed",
            finished_at=_UPDATED_AT,
        )

    assert tenant.status == TenantStatus.REQUESTED.value


def test_one_session_failed_migrate_updates_existing_routing_row(
    orchestrator_session: Session,
) -> None:
    """One session updates an existing routing row. It does not prove locking."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    routing = _routing_row(orchestrator_session, tenant.id)
    _started_attempt(orchestrator_session, request.id)

    complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=1,
        outcome="failed",
        finished_at=_UPDATED_AT,
        error_code="migration_failed",
    )

    assert routing.provisioning_state == "failed"
    assert routing.schema_revision == "0004_create_user_sessions"
    assert routing.routing_disposition == "in_service"
    assert routing.updated_at == _UPDATED_AT
    assert tenant.status == TenantStatus.FAILED.value
    assert tenant.access_status == AccessStatus.ONBOARD.value
    assert (
        orchestrator_session.scalar(
            select(func.count())
            .select_from(TenantDatabase)
            .where(TenantDatabase.tenant_id == tenant.id)
        )
        == 1
    )


def test_one_session_failed_migrate_without_routing_does_not_insert_one(
    orchestrator_session: Session,
) -> None:
    """One session does not create a routing row. It does not prove isolation."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    _started_attempt(orchestrator_session, request.id)

    complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=1,
        outcome="failed",
        finished_at=_UPDATED_AT,
    )

    assert (
        orchestrator_session.scalar(
            select(func.count())
            .select_from(TenantDatabase)
            .where(TenantDatabase.tenant_id == tenant.id)
        )
        == 0
    )
    assert tenant.status == TenantStatus.FAILED.value


def test_one_session_non_migrate_failure_preserves_routing_metadata(
    orchestrator_session: Session,
) -> None:
    """One session leaves routing metadata unchanged for a non-migrate failure."""
    tenant = _tenant(orchestrator_session)
    request = create_provisioning_request(
        orchestrator_session,
        tenant_id=tenant.id,
        idempotency_key="create-1",
        operation="create_database",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    routing = _routing_row(orchestrator_session, tenant.id)
    _started_attempt(orchestrator_session, request.id)

    complete_provisioning_attempt(
        orchestrator_session,
        request_id=request.id,
        attempt_number=1,
        outcome="failed",
        finished_at=_UPDATED_AT,
        error_code="database_create_failed",
    )

    assert routing.provisioning_state == "migrated"
    assert routing.schema_revision == "0004_create_user_sessions"
    assert routing.routing_disposition == "in_service"
    assert tenant.status == TenantStatus.FAILED.value
    assert tenant.access_status == AccessStatus.ONBOARD.value


def test_one_session_completion_integrity_error_does_not_roll_back(
    orchestrator_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An integrity error propagates. This session does not prove isolation."""
    tenant = _tenant(orchestrator_session)
    request = _migrate_request(orchestrator_session, tenant.id)
    _started_attempt(orchestrator_session, request.id)
    rollback_calls = {"count": 0}
    original_rollback = orchestrator_session.rollback

    def spy_rollback() -> None:
        rollback_calls["count"] += 1
        original_rollback()

    def fail_flush(session: Session, flush_context: object, instances: object) -> None:
        raise IntegrityError("UPDATE", {}, Exception("check"))

    monkeypatch.setattr(orchestrator_session, "rollback", spy_rollback)
    event.listen(orchestrator_session, "before_flush", fail_flush)
    try:
        with pytest.raises(IntegrityError):
            complete_provisioning_attempt(
                orchestrator_session,
                request_id=request.id,
                attempt_number=1,
                outcome="succeeded",
                finished_at=_UPDATED_AT,
            )
        assert rollback_calls["count"] == 0
    finally:
        event.remove(orchestrator_session, "before_flush", fail_flush)
