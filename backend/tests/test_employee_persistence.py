import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Employee, EmploymentStatus


def _employee(**overrides: object) -> Employee:
    values = {
        "employee_code": "EMP-000001",
        "full_name": "Ada Lovelace",
        "country": "United Kingdom",
        "department": "Engineering",
        "job_title": "Analyst",
        "employment_status": EmploymentStatus.ACTIVE.value,
    }
    values.update(overrides)
    return Employee(**values)


def test_insert_and_read_employee(db_session: Session) -> None:
    employee = _employee()
    db_session.add(employee)
    db_session.flush()
    db_session.refresh(employee)

    stored = db_session.get(Employee, employee.id)

    assert stored is not None
    assert stored.employee_code == "EMP-000001"
    assert stored.full_name == "Ada Lovelace"
    assert stored.country == "United Kingdom"
    assert stored.department == "Engineering"
    assert stored.job_title == "Analyst"
    assert stored.employment_status == EmploymentStatus.ACTIVE.value
    assert stored.id is not None


def test_duplicate_employee_code_is_rejected(db_session: Session) -> None:
    db_session.add(_employee())
    db_session.flush()

    db_session.add(_employee(full_name="Grace Hopper"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_employment_status_is_rejected(db_session: Session) -> None:
    db_session.add(_employee(employment_status="UNKNOWN"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_required_full_name_is_rejected(db_session: Session) -> None:
    statement = insert(Employee.__table__).values(
        employee_code="EMP-000002",
        country="India",
        department="Finance",
        job_title="Accountant",
        employment_status=EmploymentStatus.ACTIVE.value,
    )
    with pytest.raises(IntegrityError):
        db_session.execute(statement)
        db_session.flush()


def test_timestamps_are_initialized_by_the_database(db_session: Session) -> None:
    employee = _employee(employee_code="EMP-000003")
    db_session.add(employee)
    db_session.flush()
    db_session.refresh(employee)

    assert employee.created_at is not None
    assert employee.updated_at is not None
    assert employee.created_at.tzinfo is not None
    assert employee.updated_at.tzinfo is not None
    assert employee.created_at == employee.updated_at
