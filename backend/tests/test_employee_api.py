from fastapi.testclient import TestClient

EMPLOYEE_PAYLOAD = {
    "employee_code": "EMP-000001",
    "full_name": "Ada Lovelace",
    "country": "United Kingdom",
    "department": "Engineering",
    "job_title": "Analyst",
    "employment_status": "ACTIVE",
}


def test_create_employee(authenticated_client: TestClient) -> None:
    response = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["employee_code"] == "EMP-000001"
    assert body["full_name"] == "Ada Lovelace"
    assert body["country"] == "United Kingdom"
    assert body["department"] == "Engineering"
    assert body["job_title"] == "Analyst"
    assert body["employment_status"] == "ACTIVE"
    assert body["id"] is not None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None


def test_duplicate_employee_code_returns_409(authenticated_client: TestClient) -> None:
    first = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)
    assert first.status_code == 201

    duplicate = authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "full_name": "Grace Hopper"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Employee code already exists"


def test_create_succeeds_after_duplicate_employee_code_conflict(
    authenticated_client: TestClient,
) -> None:
    first = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)
    assert first.status_code == 201

    duplicate = authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "full_name": "Grace Hopper"},
    )
    assert duplicate.status_code == 409

    recovered = authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "employee_code": "EMP-000002", "full_name": "Grace Hopper"},
    )
    assert recovered.status_code == 201
    assert recovered.json()["employee_code"] == "EMP-000002"


def test_invalid_employment_status_returns_422(authenticated_client: TestClient) -> None:
    response = authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "employment_status": "UNKNOWN"},
    )

    assert response.status_code == 422


def test_missing_required_field_returns_422(authenticated_client: TestClient) -> None:
    payload = {k: v for k, v in EMPLOYEE_PAYLOAD.items() if k != "full_name"}
    response = authenticated_client.post("/api/v1/employees", json=payload)

    assert response.status_code == 422


def test_list_limit_above_maximum_returns_422(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/employees", params={"limit": 101})

    assert response.status_code == 422


def test_get_employee_by_id(authenticated_client: TestClient) -> None:
    created = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)
    employee_id = created.json()["id"]

    response = authenticated_client.get(f"/api/v1/employees/{employee_id}")

    assert response.status_code == 200
    assert response.json()["id"] == employee_id
    assert response.json()["employee_code"] == "EMP-000001"


def test_get_missing_employee_returns_404(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/employees/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found"


def test_list_employees_pagination_order_and_count(authenticated_client: TestClient) -> None:
    authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "employee_code": "EMP-000002", "full_name": "Second"},
    )
    authenticated_client.post(
        "/api/v1/employees",
        json={**EMPLOYEE_PAYLOAD, "employee_code": "EMP-000001", "full_name": "First"},
    )

    first_page = authenticated_client.get("/api/v1/employees", params={"limit": 1, "offset": 0})
    second_page = authenticated_client.get("/api/v1/employees", params={"limit": 1, "offset": 1})
    default_page = authenticated_client.get("/api/v1/employees")

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert default_page.status_code == 200

    first_body = first_page.json()
    second_body = second_page.json()
    default_body = default_page.json()

    assert first_body["total"] == 2
    assert first_body["limit"] == 1
    assert first_body["offset"] == 0
    assert first_body["items"][0]["employee_code"] == "EMP-000001"

    assert second_body["total"] == 2
    assert second_body["limit"] == 1
    assert second_body["offset"] == 1
    assert second_body["items"][0]["employee_code"] == "EMP-000002"

    assert default_body["total"] == 2
    assert default_body["limit"] == 50
    assert default_body["offset"] == 0
    assert [item["employee_code"] for item in default_body["items"]] == [
        "EMP-000001",
        "EMP-000002",
    ]
