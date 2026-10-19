from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.salaries import router as salaries_router

app = FastAPI(title="ACME Employee Salary Management System")
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(salaries_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
