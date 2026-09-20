import os
import sys
import datetime
import httpx

LIVE_URL = os.getenv("LIVE_API_URL", "https://event-booking-api-production-a76e.up.railway.app")
client = httpx.Client(base_url=LIVE_URL, timeout=20.0)

print(f"Targeting Deployed API: {LIVE_URL}\n")

print("--> [1] Testing /health endpoint...")
r = client.get("/health")
assert r.status_code == 200, r.text
print("    Response:", r.json())

print("--> [2] Testing /docs endpoint...")
r = client.get("/docs")
assert r.status_code == 200, r.text
print("    Docs status code: 200 OK")

print("--> [3] Registering Organizer...")
org_email = f"prod_org_{int(datetime.datetime.now().timestamp())}@test.com"
r = client.post(
    "/auth/register",
    json={
        "name": "Sarah Connor",
        "email": org_email,
        "password": "securepassword123",
        "role": "ORGANIZER",
    },
)
assert r.status_code == 201, r.text
org_token = r.json()["access_token"]
print(f"    Registered Organizer ({org_email}) successfully.")

print("--> [4] Creating Event (Capacity: 20)...")
future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).isoformat()
r = client.post(
    "/events",
    headers={"Authorization": f"Bearer {org_token}"},
    json={
        "title": "Production Tech Summit",
        "description": "Annual cloud summit",
        "location": "Main Arena",
        "start_time": future,
        "capacity": 20,
    },
)
assert r.status_code == 201, r.text
event = r.json()
event_id = event["id"]
print(f"    Event created: ID={event_id}, Title='{event['title']}', Capacity={event['capacity']}, Available={event['available_tickets']}")

print("--> [5] Registering Customer...")
cust_email = f"prod_cust_{int(datetime.datetime.now().timestamp())}@test.com"
r = client.post(
    "/auth/register",
    json={
        "name": "Alex Mercer",
        "email": cust_email,
        "password": "customerpass123",
        "role": "CUSTOMER",
    },
)
assert r.status_code == 201, r.text
cust_token = r.json()["access_token"]
print(f"    Registered Customer ({cust_email}) successfully.")

print("--> [6] Browsing Events (/events)...")
r = client.get("/events")
assert r.status_code == 200
print(f"    Active events found: {len(r.json())}")

print("--> [7] Customer Booking 4 Tickets...")
r = client.post(
    f"/events/{event_id}/book",
    headers={"Authorization": f"Bearer {cust_token}"},
    json={"quantity": 4},
)
assert r.status_code == 201, r.text
booking = r.json()
print(f"    Booking created: ID=#{booking['id']}, Quantity={booking['quantity']}")

print("--> [8] Verifying Available Tickets Decrement...")
r = client.get(f"/events/{event_id}")
assert r.status_code == 200
avail = r.json()["available_tickets"]
assert avail == 16, f"Expected 16, got {avail}"
print(f"    Remaining tickets verified: {avail}/20")

print("--> [9] Customer Checking Bookings (/bookings/me)...")
r = client.get("/bookings/me", headers={"Authorization": f"Bearer {cust_token}"})
assert r.status_code == 200
assert len(r.json()) >= 1
print(f"    Customer has {len(r.json())} bookings.")

print("--> [10] Insufficient Tickets Protection (Attempting to book 25 tickets)...")
r = client.post(
    f"/events/{event_id}/book",
    headers={"Authorization": f"Bearer {cust_token}"},
    json={"quantity": 25},
)
assert r.status_code == 409
print(f"    Expected 409 Conflict received: {r.json()['detail']}")

print("--> [11] Organizer Updating Event Details (PUT /events/{id})...")
r = client.put(
    f"/events/{event_id}",
    headers={"Authorization": f"Bearer {org_token}"},
    json={"location": "Updated Hall C, 2nd Floor"},
)
assert r.status_code == 200
print(f"    Event updated: New Location='{r.json()['location']}'")

print("--> [12] Authorization Protection: Customer Attempting to Delete Event...")
r = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {cust_token}"})
assert r.status_code == 403
print("    Expected 403 Forbidden received.")

print("--> [13] Organizer Deleting Event...")
r = client.delete(f"/events/{event_id}", headers={"Authorization": f"Bearer {org_token}"})
assert r.status_code == 204
print("    Event deleted successfully (204 No Content).")

print("\n========================================================")
print(" ALL LIVE DEPLOYED API CHECKS PASSED SUCCESSFULLY (13/13)!")
print("========================================================\n")
