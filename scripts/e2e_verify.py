import os
import sys
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("--> [1] Testing Health Check...")
res = client.get("/health")
assert res.status_code == 200, res.text
print("    Health:", res.json())

print("--> [2] Registering Organizer...")
org_reg = client.post(
    "/auth/register",
    json={
        "name": "Sarah Connor",
        "email": f"organizer_{int(datetime.now().timestamp())}@test.com",
        "password": "organizerpass123",
        "role": "ORGANIZER",
    },
)
assert org_reg.status_code == 201, org_reg.text
org_token = org_reg.json()["access_token"]
print("    Organizer registered successfully.")

print("--> [3] Creating Event (Capacity: 10)...")
future_date = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
event_res = client.post(
    "/events",
    headers={"Authorization": f"Bearer {org_token}"},
    json={
        "title": "Cloud Scale Summit 2026",
        "description": "High throughput systems conference",
        "location": "Convention Center Main Hall",
        "start_time": future_date,
        "capacity": 10,
    },
)
assert event_res.status_code == 201, event_res.text
event = event_res.json()
event_id = event["id"]
print(f"    Event created: ID={event_id}, Title='{event['title']}', Capacity={event['capacity']}, Available={event['available_tickets']}")

print("--> [4] Registering Customer...")
cust_reg = client.post(
    "/auth/register",
    json={
        "name": "Alex Mercer",
        "email": f"alex_{int(datetime.now().timestamp())}@test.com",
        "password": "customerpass123",
        "role": "CUSTOMER",
    },
)
assert cust_reg.status_code == 201, cust_reg.text
cust_token = cust_reg.json()["access_token"]
print("    Customer registered successfully.")

print("--> [5] Browsing Events...")
list_res = client.get("/events")
assert list_res.status_code == 200
print(f"    Total active events returned: {len(list_res.json())}")

print("--> [6] Customer Booking 3 Tickets...")
book_res = client.post(
    f"/events/{event_id}/book",
    headers={"Authorization": f"Bearer {cust_token}"},
    json={"quantity": 3},
)
assert book_res.status_code == 201, book_res.text
booking = book_res.json()
print(f"    Booking successful! Booking ID: #{booking['id']}, Tickets: {booking['quantity']}")

print("--> [7] Verifying Remaining Ticket Inventory...")
check_event = client.get(f"/events/{event_id}").json()
assert check_event["available_tickets"] == 7, f"Expected 7 remaining tickets, got {check_event['available_tickets']}"
print(f"    Remaining tickets verified: {check_event['available_tickets']}/10")

print("--> [8] Customer Checking Booking History (/bookings/me)...")
my_bk = client.get("/bookings/me", headers={"Authorization": f"Bearer {cust_token}"})
assert my_bk.status_code == 200
print(f"    Customer has {len(my_bk.json())} bookings.")

print("--> [9] Testing Insufficient Tickets Protection (Attempting to book 8 when 7 remain)...")
over_book = client.post(
    f"/events/{event_id}/book",
    headers={"Authorization": f"Bearer {cust_token}"},
    json={"quantity": 8},
)
assert over_book.status_code == 409, f"Expected 409, got {over_book.status_code}: {over_book.text}"
print("    Expected 409 Conflict received:", over_book.json()["detail"])

print("--> [10] Organizer Updating Event (Triggering Background Task 2)...")
update_res = client.put(
    f"/events/{event_id}",
    headers={"Authorization": f"Bearer {org_token}"},
    json={"location": "Grand Ballroom West", "description": "Updated venue details"},
)
assert update_res.status_code == 200, update_res.text
print(f"    Event updated: New Location='{update_res.json()['location']}'")

print("--> [11] Authorization Check: Customer Attempting to Delete Event...")
bad_del = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {cust_token}"})
assert bad_del.status_code == 403, f"Expected 403, got {bad_del.status_code}"
print("    Expected 403 Forbidden received.")

print("--> [12] Organizer Deleting Event...")
good_del = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {org_token}"})
assert good_del.status_code == 204
print("    Event deleted successfully (204 No Content).")

print("\n========================================================")
print(" ALL END-TO-END VERIFICATION CHECKS PASSED (12/12)!")
print("========================================================\n")
