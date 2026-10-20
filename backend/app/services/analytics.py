from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmploymentStatus
from app.models.salary import SalaryRecord
from app.schemas.analytics import (
    CompensationAnalyticsRead,
    CompensationCountryGroup,
    CompensationDepartmentGroup,
    CompensationSalaryGroup,
)

_TWO_PLACES = Decimal("0.01")


def _as_money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_TWO_PLACES)


def _applicable_salaries(reporting_date: date):
    ranked = (
        select(
            SalaryRecord.employee_id,
            SalaryRecord.amount,
            SalaryRecord.currency,
            SalaryRecord.pay_frequency,
            func.row_number()
            .over(
                partition_by=SalaryRecord.employee_id,
                order_by=(
                    SalaryRecord.effective_from.desc(),
                    SalaryRecord.id.desc(),
                ),
            )
            .label("row_number"),
        ).where(SalaryRecord.effective_from <= reporting_date)
    ).subquery()
    return (
        select(
            ranked.c.employee_id,
            ranked.c.amount,
            ranked.c.currency,
            ranked.c.pay_frequency,
        ).where(ranked.c.row_number == 1)
    ).subquery()


def _salary_group_select(
    applicable,
    extra_columns: tuple[Any, ...],
    extra_group: tuple[Any, ...],
) -> Select[Any]:
    return (
        select(
            *extra_columns,
            applicable.c.currency,
            applicable.c.pay_frequency,
            func.count().label("employee_count"),
            func.round(func.avg(applicable.c.amount), 2).label("average_salary"),
            func.min(applicable.c.amount).label("minimum_salary"),
            func.max(applicable.c.amount).label("maximum_salary"),
        )
        .select_from(applicable)
        .join(Employee, Employee.id == applicable.c.employee_id)
        .where(Employee.employment_status == EmploymentStatus.ACTIVE.value)
        .group_by(*extra_group, applicable.c.currency, applicable.c.pay_frequency)
        .order_by(*extra_group, applicable.c.currency, applicable.c.pay_frequency)
    )


def _salary_group_from_row(row: Any) -> CompensationSalaryGroup:
    return CompensationSalaryGroup(
        currency=row.currency,
        pay_frequency=row.pay_frequency,
        employee_count=int(row.employee_count),
        average_salary=_as_money(row.average_salary),
        minimum_salary=_as_money(row.minimum_salary),
        maximum_salary=_as_money(row.maximum_salary),
    )


def compensation_analytics(
    db: Session, reporting_date: date
) -> CompensationAnalyticsRead:
    applicable = _applicable_salaries(reporting_date)
    counts = db.execute(
        select(
            func.count().label("active_employee_count"),
            func.count(applicable.c.employee_id).label("active_employees_with_salary"),
        )
        .select_from(Employee)
        .outerjoin(applicable, applicable.c.employee_id == Employee.id)
        .where(Employee.employment_status == EmploymentStatus.ACTIVE.value)
    ).one()
    active_employee_count = int(counts.active_employee_count)
    active_employees_with_salary = int(counts.active_employees_with_salary)

    salary_summary = [
        _salary_group_from_row(row)
        for row in db.execute(_salary_group_select(applicable, (), ())).all()
    ]
    by_department = [
        CompensationDepartmentGroup(
            department=row.department,
            **_salary_group_from_row(row).model_dump(),
        )
        for row in db.execute(
            _salary_group_select(
                applicable,
                (Employee.department,),
                (Employee.department,),
            )
        ).all()
    ]
    by_country = [
        CompensationCountryGroup(
            country=row.country,
            **_salary_group_from_row(row).model_dump(),
        )
        for row in db.execute(
            _salary_group_select(
                applicable,
                (Employee.country,),
                (Employee.country,),
            )
        ).all()
    ]

    return CompensationAnalyticsRead(
        reporting_date=reporting_date,
        active_employee_count=active_employee_count,
        active_employees_with_salary=active_employees_with_salary,
        active_employees_without_salary=(
            active_employee_count - active_employees_with_salary
        ),
        salary_summary=salary_summary,
        by_department=by_department,
        by_country=by_country,
    )
