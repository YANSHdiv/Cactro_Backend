from datetime import datetime, timezone, timedelta
import concurrent.futures
import pytest
from fastapi import status
from httpx import ASGITransport, Client as HTTPClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Event, Booking, User, UserRole
from app.core.security import get_password_hash, create_access_token
from app.main import app


def get_token(client, email, password, role, name="Test User"):
    res = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    if res.status_code == 201:
        return res.json()["access_token"]
    login_res = client.post("/auth/login", json={"email": email, "password": password})
    return login_res.json()["access_token"]


def test_booking_happy_path_and_role_enforcement(client):
    org_token = get_token(client, "org_bk@test.com", "pass123", "ORGANIZER")
    cust_token = get_token(client, "cust_bk@test.com", "pass123", "CUSTOMER")

    # Organizer creates event with capacity 10
    future_time = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    created = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Music Fest",
            "location": "Park Stage",
            "start_time": future_time,
            "capacity": 10,
        },
    ).json()
    event_id = created["id"]

    # 1. Organizer cannot book tickets -> 403
    org_book = client.post(
        f"/events/{event_id}/book",
        headers={"Authorization": f"Bearer {org_token}"},
        json={"quantity": 2},
    )
    assert org_book.status_code == status.HTTP_403_FORBIDDEN

    # 2. Customer books 3 tickets -> 201 Created
    cust_book = client.post(
        f"/events/{event_id}/book",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"quantity": 3},
    )
    assert cust_book.status_code == status.HTTP_201_CREATED
    b_data = cust_book.json()
    assert b_data["quantity"] == 3
    assert b_data["event_id"] == event_id

    # 3. Check updated event details: available_tickets is now 7
    event_res = client.get(f"/events/{event_id}").json()
    assert event_res["available_tickets"] == 7

    # 4. Check customer's bookings (/bookings/me)
    my_bookings = client.get(
        "/bookings/me",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    assert my_bookings.status_code == status.HTTP_200_OK
    bookings_list = my_bookings.json()
    assert len(bookings_list) >= 1
    assert bookings_list[0]["event_title"] == "Music Fest"


def test_insufficient_tickets_returns_409(client):
    org_token = get_token(client, "org_limit@test.com", "pass123", "ORGANIZER")
    cust_token = get_token(client, "cust_limit@test.com", "pass123", "CUSTOMER")

    future_time = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    created = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Exclusive Workshop",
            "location": "Boardroom",
            "start_time": future_time,
            "capacity": 2,
        },
    ).json()
    event_id = created["id"]

    # Attempt to book 5 tickets when only 2 exist -> 409 Conflict
    book_res = client.post(
        f"/events/{event_id}/book",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"quantity": 5},
    )
    assert book_res.status_code == status.HTTP_409_CONFLICT
    assert "insufficient tickets" in book_res.json()["detail"].lower()


def test_concurrent_booking_overbooking_prevention(client):
    """
    Stress test with real PostgreSQL:
    Capacity is 10 tickets.
    30 concurrent requests attempt to book 1 ticket each.
    Optimized row-level lock MUST ensure exactly 10 tickets are booked,
    0 overselling occurs, and remaining 20 requests receive 409 Conflict.
    """
    settings.CONCURRENCY_MODE = "optimized"

    org_token = get_token(client, "org_concurr@test.com", "pass123", "ORGANIZER")
    cust_token = get_token(client, "cust_concurr@test.com", "pass123", "CUSTOMER")

    future_time = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    created = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "High Demand Concert",
            "location": "Stadium",
            "start_time": future_time,
            "capacity": 10,
        },
    ).json()
    event_id = created["id"]

    status_codes = []

    def book_single_ticket():
        from fastapi.testclient import TestClient
        with TestClient(app) as thread_client:
            r = thread_client.post(
                f"/events/{event_id}/book",
                headers={"Authorization": f"Bearer {cust_token}"},
                json={"quantity": 1},
            )
            return r.status_code

    # Execute 30 concurrent requests across multiple threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(book_single_ticket) for _ in range(30)]
        for f in concurrent.futures.as_completed(futures):
            status_codes.append(f.result())

    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    # Verify results
    assert success_count == 10, f"Expected exactly 10 successes, got {success_count}. Statuses: {status_codes}"
    assert conflict_count == 20, f"Expected 20 conflicts, got {conflict_count}. Statuses: {status_codes}"

    event_check = client.get(f"/events/{event_id}").json()
    assert event_check["available_tickets"] == 0, f"Available tickets must be 0, got {event_check['available_tickets']}"
