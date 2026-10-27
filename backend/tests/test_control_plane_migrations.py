import ast
import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

import app.control_plane.models  # noqa: F401
from app.control_plane.base import CONTROL_PLANE_VERSION_TABLE, ControlPlaneBase
from app.db.base import Base
from app.models import Employee, SalaryAuditLog, SalaryRecord, UserSession
from control_plane_migrations.url import (
    ControlPlaneMigrationConfigError,
    resolve_control_plane_sqlalchemy_url,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ASSESSMENT_ENV = BACKEND_ROOT / "migrations" / "env.py"
CONTROL_PLANE_ENV = BACKEND_ROOT / "control_plane_migrations" / "env.py"
EXPLICIT_CONTROL_PLANE_URL = "postgresql+psycopg://control:secret@127.0.0.1:5432/control_plane"


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def _configure_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "configure":
            calls.append(node)
    return calls


def _assigned_metadata_name(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "target_metadata"
            for target in node.targets
        ):
            continue
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "metadata"
            and isinstance(value.value, ast.Name)
        ):
            return value.value.id
    return None


def test_control_plane_metadata_is_independent_of_assessment_models() -> None:
    assert ControlPlaneBase is not Base
    assert ControlPlaneBase.metadata is not Base.metadata
    assert set(ControlPlaneBase.metadata.tables) == {
        "tenants",
        "tenant_databases",
        "provisioning_requests",
        "provisioning_attempts",
        "platform_audit_events",
    }
    assert set(Base.metadata.tables).isdisjoint(ControlPlaneBase.metadata.tables)
    assert set(Base.metadata.tables) == {
        Employee.__tablename__,
        SalaryRecord.__tablename__,
        SalaryAuditLog.__tablename__,
        UserSession.__tablename__,
    }
    assert CONTROL_PLANE_VERSION_TABLE != "alembic_version"
    assert "app.db" not in _module_imports(BACKEND_ROOT / "app" / "control_plane" / "base.py")
    assert "app.models" not in _module_imports(
        BACKEND_ROOT / "app" / "control_plane" / "base.py"
    )


def test_control_plane_url_requires_an_explicit_value_and_ignores_assessment_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://assessment:secret@127.0.0.1:5432/acme_salary",
    )
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://assessment:secret@127.0.0.1:5432/acme_test",
    )

    assert resolve_control_plane_sqlalchemy_url(EXPLICIT_CONTROL_PLANE_URL) == (
        EXPLICIT_CONTROL_PLANE_URL
    )
    with pytest.raises(
        ControlPlaneMigrationConfigError, match="DATABASE_URL is not used"
    ):
        resolve_control_plane_sqlalchemy_url(None)
    with pytest.raises(ControlPlaneMigrationConfigError):
        resolve_control_plane_sqlalchemy_url("   ")
    assert "DATABASE_URL" in os.environ


def test_histories_use_separate_configs_metadata_and_version_tables() -> None:
    assessment = Config(str(BACKEND_ROOT / "alembic.ini"))
    control_plane = Config(str(BACKEND_ROOT / "alembic-control-plane.ini"))

    assessment_script = Path(assessment.get_main_option("script_location"))
    control_plane_script = Path(control_plane.get_main_option("script_location"))
    assert assessment_script == (BACKEND_ROOT / "migrations").resolve()
    assert control_plane_script == (BACKEND_ROOT / "control_plane_migrations").resolve()
    assert (control_plane.get_main_option("sqlalchemy.url") or "").strip() == ""

    assessment_heads = list(ScriptDirectory.from_config(assessment).get_heads())
    control_plane_heads = list(ScriptDirectory.from_config(control_plane).get_heads())
    assert assessment_heads == ["0004_create_user_sessions"]
    assert control_plane_heads == ["0001_create_control_plane_tables"]

    assert _assigned_metadata_name(ASSESSMENT_ENV) == "Base"
    assert _assigned_metadata_name(CONTROL_PLANE_ENV) == "ControlPlaneBase"
    assert "app.db.base" in _module_imports(ASSESSMENT_ENV)
    assert "app.models" in _module_imports(ASSESSMENT_ENV)
    assert "app.core.test_database" in _module_imports(ASSESSMENT_ENV)

    control_plane_imports = _module_imports(CONTROL_PLANE_ENV)
    assert "app.control_plane.base" in control_plane_imports
    assert "app.control_plane.models" in control_plane_imports
    assert "control_plane_migrations.url" in control_plane_imports
    assert "app.db.base" not in control_plane_imports
    assert "app.models" not in control_plane_imports
    assert "app.core.test_database" not in control_plane_imports
    assert "app.core.config" not in control_plane_imports
    assert "app.db.session" not in control_plane_imports

    assessment_configures = _configure_calls(ASSESSMENT_ENV)
    control_plane_configures = _configure_calls(CONTROL_PLANE_ENV)
    assert len(assessment_configures) == 2
    assert len(control_plane_configures) == 2
    assert all(
        "version_table" not in {keyword.arg for keyword in call.keywords}
        for call in assessment_configures
    )
    for call in control_plane_configures:
        version_table = next(
            keyword for keyword in call.keywords if keyword.arg == "version_table"
        )
        assert isinstance(version_table.value, ast.Name)
        assert version_table.value.id == "CONTROL_PLANE_VERSION_TABLE"
