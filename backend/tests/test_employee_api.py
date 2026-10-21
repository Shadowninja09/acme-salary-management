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
    assert response.json()["employment_status"] == "ACTIVE"


def test_inactive_employee_is_returned_by_id_and_included_in_list(
    authenticated_client: TestClient,
) -> None:
    active = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)
    inactive = authenticated_client.post(
        "/api/v1/employees",
        json={
            **EMPLOYEE_PAYLOAD,
            "employee_code": "EMP-000002",
            "full_name": "Grace Hopper",
            "employment_status": "INACTIVE",
        },
    )

    assert active.status_code == 201
    assert inactive.status_code == 201
    assert active.json()["employment_status"] == "ACTIVE"
    assert inactive.json()["employment_status"] == "INACTIVE"

    inactive_id = inactive.json()["id"]
    fetched = authenticated_client.get(f"/api/v1/employees/{inactive_id}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == inactive_id
    assert fetched.json()["employee_code"] == "EMP-000002"
    assert fetched.json()["employment_status"] == "INACTIVE"

    listed = authenticated_client.get("/api/v1/employees")

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    statuses = {
        item["employee_code"]: item["employment_status"] for item in body["items"]
    }
    assert statuses == {
        "EMP-000001": "ACTIVE",
        "EMP-000002": "INACTIVE",
    }


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


def _create_listed_employee(
    client: TestClient, *, employee_code: str, **overrides: object
) -> dict[str, object]:
    payload = {**EMPLOYEE_PAYLOAD, "employee_code": employee_code, **overrides}
    response = client.post("/api/v1/employees", json=payload)
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


def test_search_finds_employee_outside_first_page(
    authenticated_client: TestClient,
) -> None:
    for index in range(1, 52):
        _create_listed_employee(
            authenticated_client,
            employee_code=f"EMP-{index:06d}",
            full_name=f"Seed Employee {index:06d}",
        )

    unfiltered = authenticated_client.get(
        "/api/v1/employees", params={"limit": 50, "offset": 0}
    )
    assert unfiltered.status_code == 200
    unfiltered_body = unfiltered.json()
    assert unfiltered_body["total"] == 51
    assert [item["employee_code"] for item in unfiltered_body["items"]] == [
        f"EMP-{index:06d}" for index in range(1, 51)
    ]
    assert "EMP-000051" not in [
        item["employee_code"] for item in unfiltered_body["items"]
    ]

    searched = authenticated_client.get(
        "/api/v1/employees",
        params={"limit": 50, "offset": 0, "q": "EMP-000051"},
    )
    assert searched.status_code == 200
    body = searched.json()
    assert body["total"] == 1
    assert [item["employee_code"] for item in body["items"]] == ["EMP-000051"]


def test_search_total_is_match_count_not_full_dataset(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Ada Lovelace"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000002", full_name="Grace Hopper"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000003", full_name="Ada Byron"
    )

    response = authenticated_client.get(
        "/api/v1/employees", params={"q": "Ada"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["employee_code"] for item in body["items"]] == [
        "EMP-000001",
        "EMP-000003",
    ]


def test_search_is_case_insensitive_substring_across_fields(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000001",
        full_name="Ada Lovelace",
        country="United Kingdom",
        department="Engineering",
        job_title="Analyst",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-AA-9",
        full_name="Other Person",
        country="India",
        department="Finance",
        job_title="Director",
    )

    cases = (
        ("emp-aa", "EMP-AA-9"),
        ("LOVE", "EMP-000001"),
        ("united king", "EMP-000001"),
        ("FINANC", "EMP-AA-9"),
        ("direc", "EMP-AA-9"),
    )
    for query, expected_code in cases:
        response = authenticated_client.get(
            "/api/v1/employees", params={"q": query}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1, query
        assert body["items"][0]["employee_code"] == expected_code, query


def test_omitted_and_empty_q_preserve_unfiltered_list(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000002", full_name="Second"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="First"
    )

    omitted = authenticated_client.get("/api/v1/employees")
    empty = authenticated_client.get("/api/v1/employees", params={"q": ""})
    whitespace = authenticated_client.get(
        "/api/v1/employees", params={"q": "   "}
    )

    assert omitted.status_code == 200
    assert empty.status_code == 200
    assert whitespace.status_code == 200
    expected_codes = ["EMP-000001", "EMP-000002"]
    for response in (omitted, empty, whitespace):
        body = response.json()
        assert body["total"] == 2
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert [item["employee_code"] for item in body["items"]] == expected_codes


def test_search_pagination_uses_filtered_result_set(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Ada One"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000002", full_name="Grace Hopper"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000003", full_name="Ada Two"
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000004", full_name="Ada Three"
    )

    first_page = authenticated_client.get(
        "/api/v1/employees",
        params={"limit": 1, "offset": 0, "q": "Ada"},
    )
    second_page = authenticated_client.get(
        "/api/v1/employees",
        params={"limit": 1, "offset": 1, "q": "Ada"},
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first_body = first_page.json()
    second_body = second_page.json()
    assert first_body["total"] == 3
    assert first_body["items"][0]["employee_code"] == "EMP-000001"
    assert second_body["total"] == 3
    assert second_body["items"][0]["employee_code"] == "EMP-000003"


def test_status_inactive_returns_only_inactive_and_match_total(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Active One"
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000002",
        full_name="Inactive One",
        employment_status="INACTIVE",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000003",
        full_name="Inactive Two",
        employment_status="INACTIVE",
    )

    response = authenticated_client.get(
        "/api/v1/employees", params={"status": "INACTIVE"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["employee_code"] for item in body["items"]] == [
        "EMP-000002",
        "EMP-000003",
    ]
    assert {item["employment_status"] for item in body["items"]} == {"INACTIVE"}


def test_status_active_returns_only_active_and_match_total(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Active One"
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000002",
        full_name="Inactive One",
        employment_status="INACTIVE",
    )
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000003", full_name="Active Two"
    )

    response = authenticated_client.get(
        "/api/v1/employees", params={"status": "ACTIVE"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["employee_code"] for item in body["items"]] == [
        "EMP-000001",
        "EMP-000003",
    ]
    assert {item["employment_status"] for item in body["items"]} == {"ACTIVE"}


def test_omitted_empty_and_all_status_preserve_unfiltered_list(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Active One"
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000002",
        full_name="Inactive One",
        employment_status="INACTIVE",
    )

    omitted = authenticated_client.get("/api/v1/employees")
    empty = authenticated_client.get("/api/v1/employees", params={"status": ""})
    all_status = authenticated_client.get(
        "/api/v1/employees", params={"status": "ALL"}
    )
    whitespace = authenticated_client.get(
        "/api/v1/employees", params={"status": "   "}
    )

    expected_codes = ["EMP-000001", "EMP-000002"]
    for response in (omitted, empty, all_status, whitespace):
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert [item["employee_code"] for item in body["items"]] == expected_codes


def test_invalid_status_returns_422(authenticated_client: TestClient) -> None:
    response = authenticated_client.get(
        "/api/v1/employees", params={"status": "UNKNOWN"}
    )
    assert response.status_code == 422


def test_search_treats_percent_underscore_and_backslash_as_literals(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000001",
        full_name="Ada Lovelace",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000002",
        full_name="Ada 50% Lead",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000003",
        job_title="Team_Lead",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000004",
        department=r"Legal\Ops",
    )

    percent = authenticated_client.get("/api/v1/employees", params={"q": "%"})
    underscore = authenticated_client.get("/api/v1/employees", params={"q": "_"})
    backslash = authenticated_client.get("/api/v1/employees", params={"q": "\\"})

    assert percent.status_code == 200
    assert underscore.status_code == 200
    assert backslash.status_code == 200
    assert [item["employee_code"] for item in percent.json()["items"]] == [
        "EMP-000002"
    ]
    assert percent.json()["total"] == 1
    assert [item["employee_code"] for item in underscore.json()["items"]] == [
        "EMP-000003"
    ]
    assert underscore.json()["total"] == 1
    assert [item["employee_code"] for item in backslash.json()["items"]] == [
        "EMP-000004"
    ]
    assert backslash.json()["total"] == 1


def test_search_and_status_combine_with_and(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-001000",
        full_name="Seed Employee 001000",
        employment_status="INACTIVE",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-010000",
        full_name="Seed Employee 010000",
        employment_status="ACTIVE",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000100",
        full_name="Other Person",
        employment_status="INACTIVE",
    )

    response = authenticated_client.get(
        "/api/v1/employees",
        params={"q": "1000", "status": "INACTIVE"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["employee_code"] for item in body["items"]] == ["EMP-001000"]
    assert body["items"][0]["employment_status"] == "INACTIVE"


def test_status_pagination_uses_filtered_result_set(
    authenticated_client: TestClient,
) -> None:
    _create_listed_employee(
        authenticated_client, employee_code="EMP-000001", full_name="Active"
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000002",
        full_name="Inactive One",
        employment_status="INACTIVE",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000003",
        full_name="Inactive Two",
        employment_status="INACTIVE",
    )
    _create_listed_employee(
        authenticated_client,
        employee_code="EMP-000004",
        full_name="Inactive Three",
        employment_status="INACTIVE",
    )

    first_page = authenticated_client.get(
        "/api/v1/employees",
        params={"limit": 1, "offset": 0, "status": "INACTIVE"},
    )
    second_page = authenticated_client.get(
        "/api/v1/employees",
        params={"limit": 1, "offset": 1, "status": "INACTIVE"},
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    first_body = first_page.json()
    second_body = second_page.json()
    assert first_body["total"] == 3
    assert first_body["items"][0]["employee_code"] == "EMP-000002"
    assert second_body["total"] == 3
    assert second_body["items"][0]["employee_code"] == "EMP-000003"
