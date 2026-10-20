"""Seed the local acme_salary database with synthetic employees and salaries.

Uses DATABASE_URL from application settings (not Alembic's TEST_DATABASE_URL
override). Refuses to run against acme_test or any database other than
acme_salary. Does not run migrations or touch user sessions.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.employee import Employee, EmploymentStatus
from app.models.salary import PayFrequency
from app.schemas.employee import EmployeeCreate
from app.schemas.salary import SalaryCreate
from app.services.country_currency import permitted_currencies_for_country
from app.services.employee import create_employee
from app.services.salary import create_salary

DEFAULT_COUNT = 1000
BATCH_SIZE = 50
GENERATION_SEED = 20261019
ALLOWED_DATABASE_NAME = "acme_salary"
FORBIDDEN_TEST_DATABASE_NAME = "acme_test"

COUNTRIES = (
    "India",
    "United Kingdom",
    "United States",
    "Germany",
    "Canada",
    "Australia",
)
DEPARTMENTS = (
    "Engineering",
    "Finance",
    "Human Resources",
    "Sales",
    "Operations",
    "Legal",
)
JOB_TITLES = (
    "Analyst",
    "Software Engineer",
    "Manager",
    "Specialist",
    "Coordinator",
    "Director",
)
FREQUENCIES = tuple(PayFrequency)


class SeedTargetError(Exception):
    pass


class SeedBatchError(Exception):
    def __init__(
        self,
        cause: BaseException,
        *,
        created_employees: int,
        skipped_employees: int,
        created_salaries: int,
    ) -> None:
        super().__init__(type(cause).__name__)
        self.cause = cause
        self.created_employees = created_employees
        self.skipped_employees = skipped_employees
        self.created_salaries = created_salaries


def database_name_from_url(url: str) -> str:
    path = unquote(urlsplit(url).path or "")
    return path.lstrip("/").split("/")[0]


def _connection_identity(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    port = str(parsed.port or "")
    return (host, port, database_name_from_url(url))


def assert_safe_seed_target(
    database_url: str,
    test_database_url: str | None,
) -> None:
    if not database_url.strip():
        raise SeedTargetError("DATABASE_URL is not configured")

    name = database_name_from_url(database_url)
    if name == FORBIDDEN_TEST_DATABASE_NAME:
        raise SeedTargetError("Refusing to seed the test database")
    if name != ALLOWED_DATABASE_NAME:
        raise SeedTargetError(
            "Refusing to seed an unexpected database; "
            f"expected {ALLOWED_DATABASE_NAME}"
        )

    test_url = (test_database_url or "").strip()
    if not test_url:
        return
    if database_url.strip() == test_url:
        raise SeedTargetError(
            "Refusing to seed because DATABASE_URL matches TEST_DATABASE_URL"
        )
    if _connection_identity(database_url) == _connection_identity(test_url):
        raise SeedTargetError(
            "Refusing to seed because DATABASE_URL targets the same database "
            "as TEST_DATABASE_URL"
        )


def employee_code_for(index: int) -> str:
    return f"EMP-{index:06d}"


def _rng_for(index: int) -> random.Random:
    return random.Random(GENERATION_SEED + index)


def build_employee(index: int) -> EmployeeCreate:
    rng = _rng_for(index)
    return EmployeeCreate(
        employee_code=employee_code_for(index),
        full_name=f"Seed Employee {index:06d}",
        country=COUNTRIES[index % len(COUNTRIES)],
        department=DEPARTMENTS[(index // 2) % len(DEPARTMENTS)],
        job_title=JOB_TITLES[(index // 3) % len(JOB_TITLES)],
        employment_status=(
            EmploymentStatus.INACTIVE
            if rng.randrange(10) == 0
            else EmploymentStatus.ACTIVE
        ),
    )


def _amount_for(rng: random.Random, frequency: PayFrequency) -> Decimal:
    if frequency is PayFrequency.MONTHLY:
        major = rng.randint(4_000, 25_000)
    else:
        major = rng.randint(48_000, 180_000)
    cents = rng.randint(0, 99)
    return Decimal(major) + (Decimal(cents) / Decimal(100))


def build_salaries(employee_id: int, index: int, country: str) -> list[SalaryCreate]:
    remainder = index % 10
    if remainder == 0:
        return []
    if remainder <= 3:
        count = 1
    elif remainder <= 6:
        count = 2
    else:
        count = 3

    permitted = permitted_currencies_for_country(country)
    if not permitted:
        raise ValueError(f"No salary currency policy for country {country!r}")

    rng = _rng_for(index)
    payloads: list[SalaryCreate] = []
    seen_dates: set[date] = set()
    for offset in range(count):
        if remainder >= 8 and offset == count - 1:
            effective_from = date(2027, 4, 15) + timedelta(days=index % 30)
        else:
            effective_from = date(2023, 1, 15) + timedelta(days=180 * offset)
        while effective_from in seen_dates:
            effective_from += timedelta(days=1)
        seen_dates.add(effective_from)
        frequency = FREQUENCIES[(index + offset) % len(FREQUENCIES)]
        payloads.append(
            SalaryCreate(
                employee_id=employee_id,
                amount=_amount_for(rng, frequency),
                currency=permitted[(index + offset) % len(permitted)],
                pay_frequency=frequency,
                effective_from=effective_from,
            )
        )
    return payloads


def _existing_employee_id(db: Session, employee_code: str) -> int | None:
    return db.scalar(
        select(Employee.id).where(Employee.employee_code == employee_code)
    )


def seed_employees(db: Session, count: int) -> tuple[int, int, int]:
    created_employees = 0
    skipped_employees = 0
    created_salaries = 0

    for batch_start in range(1, count + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE - 1, count)
        batch_employees = 0
        batch_salaries = 0
        batch_skipped = 0
        try:
            for index in range(batch_start, batch_end + 1):
                code = employee_code_for(index)
                if _existing_employee_id(db, code) is not None:
                    batch_skipped += 1
                    continue
                employee = create_employee(db, build_employee(index))
                salaries = build_salaries(employee.id, index, employee.country)
                for payload in salaries:
                    create_salary(db, payload)
                batch_employees += 1
                batch_salaries += len(salaries)
            db.commit()
        except Exception as exc:
            db.rollback()
            raise SeedBatchError(
                exc,
                created_employees=created_employees,
                skipped_employees=skipped_employees,
                created_salaries=created_salaries,
            ) from exc
        created_employees += batch_employees
        skipped_employees += batch_skipped
        created_salaries += batch_salaries

    return created_employees, skipped_employees, created_salaries


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insert deterministic synthetic employees and salary records into "
            "the local acme_salary database using existing create services "
            "(including salary CREATE audit rows). Skips employee codes that "
            "already exist. Does not run migrations, delete data, or write "
            "sessions. Refuses acme_test and any database other than acme_salary."
        )
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        metavar="N",
        help=f"number of employees to seed (default: {DEFAULT_COUNT})",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count must be a positive integer")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    try:
        assert_safe_seed_target(
            settings.database_url,
            os.environ.get("TEST_DATABASE_URL"),
        )
    except SeedTargetError as exc:
        print(f"Seed aborted: {exc}", file=sys.stderr)
        return 1

    from app.db.session import SessionLocal, engine

    db = SessionLocal()
    try:
        created_employees, skipped_employees, created_salaries = seed_employees(
            db, args.count
        )
    except SeedBatchError as exc:
        print(
                f"Seed failed: {type(exc.cause).__name__}: {exc.cause}",
                file=sys.stderr,
            )
        print(
            "Committed before failure: "
            f"employees created={exc.created_employees}, "
            f"employees skipped={exc.skipped_employees}, "
            f"salaries created={exc.created_salaries}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Seed failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
        engine.dispose()

    print(
        "Seed complete: "
        f"employees created={created_employees}, "
        f"employees skipped={skipped_employees}, "
        f"salaries created={created_salaries}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
