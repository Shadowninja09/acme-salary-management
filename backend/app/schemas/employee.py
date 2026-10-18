from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.employee import EmploymentStatus


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=150)
    country: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=100)
    job_title: str = Field(min_length=1, max_length=150)
    employment_status: EmploymentStatus


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    country: str
    department: str
    job_title: str
    employment_status: EmploymentStatus
    created_at: datetime
    updated_at: datetime


class EmployeeList(BaseModel):
    items: list[EmployeeRead]
    total: int
    limit: int
    offset: int
