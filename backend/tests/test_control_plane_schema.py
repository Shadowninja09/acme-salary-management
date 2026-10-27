import ast
import importlib.util
from pathlib import Path

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    JSON,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.control_plane.base import CONTROL_PLANE_VERSION_TABLE, ControlPlaneBase
from app.control_plane.models import (
    PLATFORM_AUDIT_OUTCOME_CHECK,
    PROVISIONING_ATTEMPT_STATUS_CHECK,
    PROVISIONING_REQUEST_CONCLUSION_CHECK,
    PROVISIONING_REQUEST_OPERATION_CHECK,
    PROVISIONING_REQUEST_TARGET_REVISION_CHECK,
    TENANT_ACCESS_STATUS_CHECK,
    TENANT_DATABASE_PROVISIONING_STATE_CHECK,
    TENANT_DATABASE_ROUTING_DISPOSITION_CHECK,
    TENANT_STATUS_CHECK,
)
from app.db.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REVISION_PATH = (
    BACKEND_ROOT
    / "control_plane_migrations"
    / "versions"
    / "0001_create_control_plane_tables.py"
)
ASSESSMENT_TABLES = {
    "employees",
    "salary_records",
    "salary_audit_logs",
    "user_sessions",
}
CONTROL_PLANE_TABLES = {
    "tenants",
    "tenant_databases",
    "provisioning_requests",
    "provisioning_attempts",
    "platform_audit_events",
}


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _string_list(node: ast.AST) -> tuple[str, ...] | None:
    if not isinstance(node, ast.List):
        return None
    names: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None
        names.append(element.value)
    return tuple(names)


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _upgrade_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upgrade = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    return [
        node.value
        for node in upgrade.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]


def _migration_shape(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, tuple[str, ...]], list[str]]:
    tables: dict[str, dict[str, object]] = {}
    indexes: dict[str, tuple[str, ...]] = {}
    order: list[str] = []
    for call in _upgrade_calls(path):
        name = _call_name(call.func)
        if name == "create_table":
            table_name = call.args[0]
            assert isinstance(table_name, ast.Constant)
            order.append(table_name.value)
            columns: dict[str, dict[str, object]] = {}
            uniques: set[tuple[str, tuple[str, ...]]] = set()
            checks: set[tuple[str, str]] = set()
            foreign_keys: set[tuple[str, tuple[str, ...], tuple[str, ...], str]] = set()
            for arg in call.args[1:]:
                assert isinstance(arg, ast.Call)
                kind = _call_name(arg.func)
                if kind == "Column":
                    column_name = arg.args[0]
                    assert isinstance(column_name, ast.Constant)
                    type_call = arg.args[1]
                    assert isinstance(type_call, ast.Call)
                    type_name = _call_name(type_call.func)
                    nullable = _keyword(arg, "nullable")
                    assert isinstance(nullable, ast.Constant)
                    server_default = _keyword(arg, "server_default")
                    default_sql = None
                    if server_default is not None:
                        assert isinstance(server_default, ast.Call)
                        assert _call_name(server_default.func) == "text"
                        default_text = server_default.args[0]
                        assert isinstance(default_text, ast.Constant)
                        default_sql = default_text.value
                    timezone = None
                    timezone_node = _keyword(type_call, "timezone")
                    if isinstance(timezone_node, ast.Constant):
                        timezone = timezone_node.value
                    columns[column_name.value] = {
                        "type": type_name,
                        "timezone": timezone,
                        "nullable": nullable.value,
                        "identity": any(
                            isinstance(item, ast.Call) and _call_name(item.func) == "Identity"
                            for item in arg.args[1:]
                        ),
                        "server_default": default_sql,
                    }
                elif kind == "UniqueConstraint":
                    constraint_name = _keyword(arg, "name")
                    assert isinstance(constraint_name, ast.Constant)
                    column_names = tuple(
                        item.value
                        for item in arg.args
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    )
                    uniques.add((constraint_name.value, column_names))
                elif kind == "CheckConstraint":
                    sql_text = arg.args[0]
                    constraint_name = _keyword(arg, "name")
                    assert isinstance(sql_text, ast.Constant)
                    assert isinstance(constraint_name, ast.Constant)
                    checks.add((constraint_name.value, sql_text.value))
                elif kind == "ForeignKeyConstraint":
                    constraint_name = _keyword(arg, "name")
                    ondelete = _keyword(arg, "ondelete")
                    assert isinstance(constraint_name, ast.Constant)
                    assert isinstance(ondelete, ast.Constant)
                    local = _string_list(arg.args[0])
                    remote = _string_list(arg.args[1])
                    assert local is not None and remote is not None
                    foreign_keys.add(
                        (constraint_name.value, local, remote, ondelete.value)
                    )
            tables[table_name.value] = {
                "columns": columns,
                "uniques": uniques,
                "checks": checks,
                "foreign_keys": foreign_keys,
            }
        elif name == "create_index":
            index_name = call.args[0]
            table_name = call.args[1]
            column_names = _string_list(call.args[2])
            assert isinstance(index_name, ast.Constant)
            assert isinstance(table_name, ast.Constant)
            assert column_names is not None
            indexes[index_name.value] = (table_name.value, *column_names)
    return tables, indexes, order


def _load_revision():
    spec = importlib.util.spec_from_file_location(
        "control_plane_revision_0001", REVISION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_control_plane_metadata_has_only_proposed_tables() -> None:
    assert set(ControlPlaneBase.metadata.tables) == CONTROL_PLANE_TABLES
    assert CONTROL_PLANE_VERSION_TABLE not in ControlPlaneBase.metadata.tables
    assert CONTROL_PLANE_VERSION_TABLE != "alembic_version"
    assert set(Base.metadata.tables).isdisjoint(CONTROL_PLANE_TABLES)
    assert ASSESSMENT_TABLES.isdisjoint(ControlPlaneBase.metadata.tables)

    column_names = {
        column.name
        for table in ControlPlaneBase.metadata.tables.values()
        for column in table.columns
    }
    assert column_names.isdisjoint(
        {
            "employment_status",
            "password_hash",
            "token_hash",
            "grace_until",
            "actor_user_id",
            "user_id",
        }
    )

    models_source = (BACKEND_ROOT / "app" / "control_plane" / "models.py").read_text(
        encoding="utf-8"
    )
    models_imports = {
        node.module
        for node in ast.walk(ast.parse(models_source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.db.base" not in models_imports
    assert "app.models" not in models_imports
    assert "app.db.session" not in models_imports
    assert "app.core.config" not in models_imports


def test_control_plane_columns_constraints_and_indexes_follow_the_proposal() -> None:
    metadata = ControlPlaneBase.metadata
    tenants = metadata.tables["tenants"]
    tenant_databases = metadata.tables["tenant_databases"]
    requests = metadata.tables["provisioning_requests"]
    attempts = metadata.tables["provisioning_attempts"]
    events = metadata.tables["platform_audit_events"]

    assert isinstance(tenants.c.public_id.type, Uuid)
    assert tenants.c.public_id.nullable is True
    assert tenants.c.name.nullable is True
    assert tenants.c.slug.nullable is True
    assert tenants.c.status.nullable is True
    assert str(tenants.c.access_status.server_default.arg) == "'onboard'"
    assert tenants.c.access_status.nullable is False
    assert tenants.c.created_at.nullable is False
    assert tenants.c.created_at.server_default is None
    assert tenants.c.updated_at.server_default is None
    status_index = next(index for index in tenants.indexes if index.name == "ix_tenants_status")
    assert [column.name for column in status_index.columns] == ["status"]
    assert not any(
        "access_status" in {column.name for column in index.columns}
        for index in tenants.indexes
    )

    for table in metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.ondelete == "RESTRICT"
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True

    assert {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in tenant_databases.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {
        ("uq_tenant_databases_tenant_id", ("tenant_id",)),
        (
            "uq_tenant_databases_instance_ref_database_name",
            ("instance_ref", "database_name"),
        ),
    }
    assert {
        (constraint.name, str(constraint.sqltext))
        for constraint in requests.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        ("ck_provisioning_requests_operation", PROVISIONING_REQUEST_OPERATION_CHECK),
        (
            "ck_provisioning_requests_conclusion",
            PROVISIONING_REQUEST_CONCLUSION_CHECK,
        ),
        (
            "ck_provisioning_requests_target_revision",
            PROVISIONING_REQUEST_TARGET_REVISION_CHECK,
        ),
    }
    attempt_index = next(
        index
        for index in attempts.indexes
        if index.name == "ix_provisioning_attempts_request_id_started_at"
    )
    assert [column.name for column in attempt_index.columns] == [
        "request_id",
        "started_at",
    ]
    assert {
        index.name: [column.name for column in index.columns]
        for index in events.indexes
    } == {
        "ix_platform_audit_events_target_tenant_id_created_at": [
            "target_tenant_id",
            "created_at",
        ],
        "ix_platform_audit_events_actor_ref_created_at": ["actor_ref", "created_at"],
    }
    assert events.c.actor_ref.nullable is True
    assert events.c.target_tenant_id.nullable is True
    assert isinstance(events.c.detail.type, JSON)
    assert events.c.detail.nullable is True
    assert attempts.c.error_code.nullable is True
    assert attempts.c.attempt_number.nullable is False
    assert isinstance(attempts.c.attempt_number.type, BigInteger)
    assert attempts.c.attempt_number.identity is None
    assert requests.c.idempotency_key.nullable is False
    assert tenant_databases.c.tenant_id.nullable is False
    assert tenant_databases.c.secret_ref.nullable is True
    assert tenant_databases.c.migration_secret_ref.nullable is True
    assert tenant_databases.c.schema_revision.nullable is True

    check_text = {
        tenants: {TENANT_STATUS_CHECK, TENANT_ACCESS_STATUS_CHECK},
        tenant_databases: {
            TENANT_DATABASE_PROVISIONING_STATE_CHECK,
            TENANT_DATABASE_ROUTING_DISPOSITION_CHECK,
        },
        attempts: {PROVISIONING_ATTEMPT_STATUS_CHECK},
        events: {PLATFORM_AUDIT_OUTCOME_CHECK},
    }
    for table, expected in check_text.items():
        assert {
            str(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        } == expected

    rendered = "\n".join(
        str(CreateTable(table).compile(dialect=postgresql.dialect()))
        for table in metadata.tables.values()
    )
    assert "VARCHAR" not in rendered
    assert "DEFAULT 'onboard'" in rendered
    for name in ASSESSMENT_TABLES:
        assert name not in rendered


def test_initial_migration_matches_metadata_and_does_not_use_assessment_database() -> None:
    revision = _load_revision()
    assert revision.revision == "0001_create_control_plane_tables"
    assert revision.down_revision is None
    source = REVISION_PATH.read_text(encoding="utf-8")
    assert "acme_salary" not in source
    assert "acme_test" not in source
    assert "alembic_sqlalchemy_url" not in source
    assert "get_settings" not in source
    assert "os.environ" not in source
    assert CONTROL_PLANE_VERSION_TABLE not in source
    for name in ASSESSMENT_TABLES:
        assert name not in source

    migrated, indexes, order = _migration_shape(REVISION_PATH)
    assert order == [
        "tenants",
        "tenant_databases",
        "provisioning_requests",
        "provisioning_attempts",
        "platform_audit_events",
    ]
    assert set(migrated) == set(ControlPlaneBase.metadata.tables)

    downgrade = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade"
    )
    dropped = []
    for node in downgrade.body:
        assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        assert _call_name(node.value.func) == "drop_table"
        table_name = node.value.args[0]
        assert isinstance(table_name, ast.Constant)
        dropped.append(table_name.value)
    assert dropped == list(reversed(order))

    for table_name, table in ControlPlaneBase.metadata.tables.items():
        migrated_columns = migrated[table_name]["columns"]
        assert set(migrated_columns) == set(table.columns.keys())
        for column in table.columns:
            migrated_column = migrated_columns[column.name]
            assert migrated_column["nullable"] is column.nullable
            assert migrated_column["identity"] is (column.identity is not None)
            if column.identity is not None or column.server_default is None:
                assert migrated_column["server_default"] is None
            else:
                assert migrated_column["server_default"] == str(
                    column.server_default.arg
                )
            expected_type = {
                BigInteger: "BigInteger",
                Uuid: "Uuid",
                Text: "Text",
                DateTime: "DateTime",
                JSON: "JSON",
            }[type(column.type)]
            assert migrated_column["type"] == expected_type
            if isinstance(column.type, DateTime):
                assert migrated_column["timezone"] is True

        assert migrated[table_name]["uniques"] == {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert migrated[table_name]["checks"] == {
            (constraint.name, str(constraint.sqltext))
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        }
        assert migrated[table_name]["foreign_keys"] == {
            (
                constraint.name,
                tuple(column.name for column in constraint.columns),
                tuple(element.target_fullname for element in constraint.elements),
                constraint.elements[0].ondelete,
            )
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }

    assert indexes == {
        index.name: (index.table.name, *(column.name for column in index.columns))
        for table in ControlPlaneBase.metadata.tables.values()
        for index in table.indexes
        if isinstance(index, Index)
    }
