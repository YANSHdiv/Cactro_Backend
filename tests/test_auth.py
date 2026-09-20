import pytest
from fastapi import status


def test_register_organizer_and_customer(client):
    # 1. Register Organizer
    org_res = client.post(
        "/auth/register",
        json={
            "name": "Tech Corp",
            "email": "organizer@techcorp.com",
            "password": "securepassword123",
            "role": "ORGANIZER",
        },
    )
    assert org_res.status_code == status.HTTP_201_CREATED
    data = org_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # 2. Register Customer
    cust_res = client.post(
        "/auth/register",
        json={
            "name": "Alice Smith",
            "email": "alice@example.com",
            "password": "alicepassword123",
            "role": "CUSTOMER",
        },
    )
    assert cust_res.status_code == status.HTTP_201_CREATED
    assert "access_token" in cust_res.json()


def test_register_duplicate_email_fails(client):
    client.post(
        "/auth/register",
        json={
            "name": "First User",
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "CUSTOMER",
        },
    )
    res = client.post(
        "/auth/register",
        json={
            "name": "Second User",
            "email": "duplicate@example.com",
            "password": "password456",
            "role": "CUSTOMER",
        },
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in res.json()["detail"].lower()


def test_login_success_and_failure(client):
    client.post(
        "/auth/register",
        json={
            "name": "Bob Jones",
            "email": "bob@example.com",
            "password": "correctpassword",
            "role": "CUSTOMER",
        },
    )

    # Valid login
    login_res = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "correctpassword"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    assert "access_token" in login_res.json()

    # Invalid password
    bad_login = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "wrongpassword"},
    )
    assert bad_login.status_code == status.HTTP_401_UNAUTHORIZED
