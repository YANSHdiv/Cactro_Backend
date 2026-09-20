from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status


def get_token(client, email, password, role, name="Test User"):
    res = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    if res.status_code == 201:
        return res.json()["access_token"]
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    return login_res.json()["access_token"]


def test_event_creation_and_authorization(client):
    org_token = get_token(client, "org1@test.com", "pass123", "ORGANIZER", "Org One")
    cust_token = get_token(client, "cust1@test.com", "pass123", "CUSTOMER", "Cust One")

    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    # 1. Organizer can create event
    create_res = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Cloud Summit 2026",
            "description": "Annual cloud computing conference",
            "location": "Convention Center Hall A",
            "start_time": future_time,
            "capacity": 100,
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    data = create_res.json()
    assert data["title"] == "Cloud Summit 2026"
    assert data["capacity"] == 100
    assert data["available_tickets"] == 100
    event_id = data["id"]

    # 2. Customer CANNOT create event -> 403
    cust_create_res = client.post(
        "/events",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={
            "title": "Customer Event",
            "location": "Nowhere",
            "start_time": future_time,
            "capacity": 50,
        },
    )
    assert cust_create_res.status_code == status.HTTP_403_FORBIDDEN


def test_event_capacity_validation(client):
    org_token = get_token(client, "org_val@test.com", "pass123", "ORGANIZER")
    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    res = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Zero Capacity Event",
            "location": "Online",
            "start_time": future_time,
            "capacity": 0,
        },
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or res.status_code == status.HTTP_400_BAD_REQUEST


def test_event_update_authorization(client):
    org1_token = get_token(client, "org_a@test.com", "pass123", "ORGANIZER", "Org A")
    org2_token = get_token(client, "org_b@test.com", "pass123", "ORGANIZER", "Org B")

    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()

    # Org 1 creates event
    created = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org1_token}"},
        json={
            "title": "Org A Conference",
            "location": "Room 101",
            "start_time": future_time,
            "capacity": 50,
        },
    ).json()
    event_id = created["id"]

    # Org 2 attempts to update Org 1's event -> 403 Forbidden
    hack_res = client.put(
        f"/events/{event_id}",
        headers={"Authorization": f"Bearer {org2_token}"},
        json={"title": "Hacked Title"},
    )
    assert hack_res.status_code == status.HTTP_403_FORBIDDEN

    # Org 1 updates their own event -> 200 OK
    update_res = client.put(
        f"/events/{event_id}",
        headers={"Authorization": f"Bearer {org1_token}"},
        json={"title": "Updated Conference Title", "location": "Room 202"},
    )
    assert update_res.status_code == status.HTTP_200_OK
    assert update_res.json()["title"] == "Updated Conference Title"
    assert update_res.json()["location"] == "Room 202"


def test_event_deletion_authorization(client):
    org1_token = get_token(client, "org_del1@test.com", "pass123", "ORGANIZER")
    org2_token = get_token(client, "org_del2@test.com", "pass123", "ORGANIZER")

    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    created = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org1_token}"},
        json={
            "title": "To Be Deleted",
            "location": "Room 303",
            "start_time": future_time,
            "capacity": 20,
        },
    ).json()
    event_id = created["id"]

    # Org 2 cannot delete Org 1's event
    bad_del = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {org2_token}"})
    assert bad_del.status_code == status.HTTP_403_FORBIDDEN

    # Org 1 can delete their own event
    good_del = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {org1_token}"})
    assert good_del.status_code == status.HTTP_204_NO_CONTENT

    # Verification: event no longer exists
    get_res = client.get(f"/events/{event_id}")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND
