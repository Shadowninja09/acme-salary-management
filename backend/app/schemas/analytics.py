from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

from app.models.salary import Currency, PayFrequency

_TWO_PLACES = Decimal("0.01")


def serialize_money(value: Decimal) -> str:
    return format(value.quantize(_TWO_PLACES), "f")


class CompensationSalaryGroup(BaseModel):
    currency: Currency
    pay_frequency: PayFrequency
    employee_count: int
    average_salary: Decimal
    minimum_salary: Decimal
    maximum_salary: Decimal

    @field_serializer("average_salary", "minimum_salary", "maximum_salary")
    def serialize_salary_fields(self, value: Decimal) -> str:
        return serialize_money(value)


class CompensationDepartmentGroup(CompensationSalaryGroup):
    department: str


class CompensationCountryGroup(CompensationSalaryGroup):
    country: str


class CompensationAnalyticsRead(BaseModel):
    reporting_date: date = Field(
        description="Reporting date used to select each employee's applicable salary."
    )
    active_employee_count: int = Field(
        description="Employees whose current employment status is ACTIVE."
    )
    active_employees_with_salary: int = Field(
        description="Active employees with a salary effective on or before the reporting date."
    )
    active_employees_without_salary: int = Field(
        description=(
            "Active employees with no applicable salary on the reporting date. "
            "Counted in headcount and excluded from salary statistics."
        )
    )
    salary_summary: list[CompensationSalaryGroup] = Field(
        description=(
            "Salary statistics grouped by currency and pay frequency. "
            "Currencies and pay frequencies are never combined."
        )
    )
    by_department: list[CompensationDepartmentGroup] = Field(
        description="Salary statistics grouped by department, currency, and pay frequency."
    )
    by_country: list[CompensationCountryGroup] = Field(
        description="Salary statistics grouped by country, currency, and pay frequency."
    )
