import ast
import os
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.control_plane.models import AccessStatus, Tenant, TenantDatabase
from app.control_plane.registry import (
    PUBLIC_ID_UNIQUE_CONSTRAINT,
    SLUG_UNIQUE_CONSTRAINT,
    DuplicateTenantPublicIdError,
    DuplicateTenantSlugError,
    create_tenant,
    get_tenant_by_id,
    get_tenant_by_public_id,
    get_tenant_by_slug,
)
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
def registry_session() -> Generator[Session, None, None]:
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


def _create(session: Session, **overrides: object) -> Tenant:
    values: dict[str, object] = {
        "created_at": _CREATED_AT,
        "updated_at": _UPDATED_AT,
        "public_id": uuid4(),
        "name": "Northwind",
        "slug": "northwind",
        "status": None,
    }
    values.update(overrides)
    return create_tenant(session, **values)  # type: ignore[arg-type]


def test_create_and_retrieve_tenant_by_each_key(registry_session: Session) -> None:
    public_id = UUID("11111111-1111-1111-1111-111111111111")
    created = _create(
        registry_session,
        public_id=public_id,
        name="Northwind",
        slug="northwind",
        status="requested",
    )

    assert created.id is not None
    assert created.access_status == AccessStatus.ONBOARD.value
    assert created.status == "requested"
    assert get_tenant_by_id(registry_session, created.id) is created
    assert get_tenant_by_public_id(registry_session, public_id) is created
    assert get_tenant_by_slug(registry_session, "northwind") is created
    assert registry_session.in_transaction()


def test_new_company_starts_onboard_without_a_provisioning_status(
    registry_session: Session,
) -> None:
    created = create_tenant(
        registry_session,
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    ready = _create(
        registry_session,
        public_id=uuid4(),
        slug="ready-company",
        status="ready",
    )

    assert created.access_status == AccessStatus.ONBOARD.value
    assert created.status is None
    assert ready.status == "ready"
    assert ready.access_status == AccessStatus.ONBOARD.value
    assert "access_status" not in create_tenant.__code__.co_varnames
    assert registry_session.scalars(select(TenantDatabase)).all() == []

    with pytest.raises(IntegrityError):
        _create(
            registry_session,
            public_id=uuid4(),
            slug="not-a-provisioning-status",
            status="onboard",
        )


def test_optional_registry_fields_stay_unset(registry_session: Session) -> None:
    created = create_tenant(
        registry_session,
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )

    assert created.public_id is None
    assert created.name is None
    assert created.slug is None
    assert created.status is None
    assert created.access_status == AccessStatus.ONBOARD.value
    assert (
        registry_session.scalars(select(TenantDatabase)).all() == []
    )


def test_duplicate_public_id_and_slug_follow_unique_constraints(
    registry_session: Session,
) -> None:
    public_id = uuid4()
    _create(registry_session, public_id=public_id, slug="northwind")

    with pytest.raises(DuplicateTenantPublicIdError):
        _create(registry_session, public_id=public_id, slug="other")
    registry_session.rollback()

    _create(registry_session, public_id=uuid4(), slug="northwind")
    with pytest.raises(DuplicateTenantSlugError):
        _create(registry_session, public_id=uuid4(), slug="northwind")


def test_duplicate_names_and_null_unique_keys_are_allowed(
    registry_session: Session,
) -> None:
    first = _create(registry_session, public_id=None, slug=None, name="Shared")
    second = _create(registry_session, public_id=None, slug=None, name="Shared")

    assert first.id != second.id
    assert get_tenant_by_public_id(registry_session, uuid4()) is None
    assert get_tenant_by_slug(registry_session, "missing") is None
    assert get_tenant_by_id(registry_session, 999_999) is None


def test_create_does_not_commit_or_use_the_assessment_session(
    registry_session: Session,
) -> None:
    tenant = _create(registry_session)
    tenant_id = tenant.id
    assert registry_session.in_transaction()
    registry_session.rollback()

    assert get_tenant_by_id(registry_session, tenant_id) is None
    source = ast.parse(
        Path(create_tenant.__code__.co_filename).read_text(encoding="utf-8")
    )
    imported = {
        node.module
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.db.session" not in imported
    assert "app.db" not in imported
    assert SessionLocal.kw["bind"] is not registry_session.get_bind()


def test_postgresql_constraint_names_map_to_service_errors() -> None:
    class _Diag:
        constraint_name = PUBLIC_ID_UNIQUE_CONSTRAINT

    class _Orig(Exception):
        diag = _Diag()

    class _Session:
        def __init__(self) -> None:
            self.committed = False

        def add(self, obj: Tenant) -> None:
            self.added = obj

        def flush(self) -> None:
            raise IntegrityError("insert", {}, _Orig("duplicate"))

        def commit(self) -> None:
            self.committed = True

        def refresh(self, obj: Tenant) -> None:
            raise AssertionError("refresh should not run after a duplicate")

    session = _Session()
    with pytest.raises(DuplicateTenantPublicIdError):
        create_tenant(
            session,  # type: ignore[arg-type]
            created_at=_CREATED_AT,
            updated_at=_UPDATED_AT,
            public_id=uuid4(),
        )
    assert session.committed is False

    _Diag.constraint_name = SLUG_UNIQUE_CONSTRAINT
    with pytest.raises(DuplicateTenantSlugError):
        create_tenant(
            session,  # type: ignore[arg-type]
            created_at=_CREATED_AT,
            updated_at=_UPDATED_AT,
            slug="northwind",
        )


def test_registry_module_does_not_import_the_assessment_session() -> None:
    source = ast.parse(
        Path(create_tenant.__code__.co_filename).read_text(encoding="utf-8")
    )
    imported = {
        node.module
        for node in source.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.db.session" not in imported
    assert "app.control_plane.models" in imported
