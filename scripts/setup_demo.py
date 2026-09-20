import datetime
import time
import httpx

LIVE_URL = "https://event-booking-api-production-a76e.up.railway.app"
client = httpx.Client(base_url=LIVE_URL, timeout=30.0)

ORGANIZER_EMAIL = "demo.organizer@cactro.com"
ORGANIZER_PASSWORD = "OrganizerPass2026!"

# Customer email that receives the real emails in Resend:
CUSTOMER_REAL_EMAIL = "divyanshraj2604@gmail.com"
CUSTOMER_GENERIC_EMAIL = "demo.customer@cactro.com"
CUSTOMER_PASSWORD = "CustomerPass2026!"

print(f"--> Connecting to Live API: {LIVE_URL}\n")


def get_or_create_user(name: str, email: str, password: str, role: str):
    # Try login first with primary password
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    if login_resp.status_code == 200:
        print(f"    User '{email}' logged in successfully.")
        return login_resp.json()["access_token"]

    # Try fallback password if previously registered
    fallback_resp = client.post("/auth/login", json={"email": email, "password": "customerpass123"})
    if fallback_resp.status_code == 200:
        print(f"    User '{email}' logged in successfully with password 'customerpass123'.")
        return fallback_resp.json()["access_token"]

    # Try register
    reg_resp = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    if reg_resp.status_code == 201:
        print(f"    Registered new user '{email}' successfully.")
        return reg_resp.json()["access_token"]

    raise Exception(f"Failed to authenticate/register {email}: {login_resp.text} / {reg_resp.text}")


# 1. Setup Organizer
print("--> [1] Setting up Demo Organizer...")
org_token = get_or_create_user("Demo Organizer", ORGANIZER_EMAIL, ORGANIZER_PASSWORD, "ORGANIZER")

# 2. Setup Customers
print("--> [2] Setting up Demo Customers...")
cust_real_token = get_or_create_user("Demo Customer", CUSTOMER_REAL_EMAIL, CUSTOMER_PASSWORD, "CUSTOMER")
cust_generic_token = get_or_create_user("Demo Customer", CUSTOMER_GENERIC_EMAIL, CUSTOMER_PASSWORD, "CUSTOMER")

# 3. Clean up any prior 'Tech Conference 2026' events created by this organizer
print("--> [3] Cleaning up any existing demo events...")
events_list = client.get("/events").json()
for ev in events_list:
    if ev.get("title") == "Tech Conference 2026" and ev.get("organizer_id"):
        # Attempt to delete with organizer token
        del_res = client.delete(f"/events/{ev['id']}", headers={"Authorization": f"Bearer {org_token}"})
        if del_res.status_code == 204:
            print(f"    Deleted previous demo event #{ev['id']}")

# 4. Perform Single Live Verification Run using a temporary verification event
print("--> [4] Performing single verification of Booking + Email workflow...")
future_temp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).isoformat()
temp_event_res = client.post(
    "/events",
    headers={"Authorization": f"Bearer {org_token}"},
    json={
        "title": "Temp Verification Event",
        "description": "Used only to verify email delivery before recording",
        "location": "Jaipur",
        "start_time": future_temp,
        "capacity": 10,
    },
)
temp_event_res.raise_for_status()
temp_id = temp_event_res.json()["id"]

# Customer books 1 ticket on temp event
book_temp = client.post(
    f"/events/{temp_id}/book",
    headers={"Authorization": f"Bearer {cust_real_token}"},
    json={"quantity": 1},
)
book_temp.raise_for_status()
print(f"    Verified booking on temp event #{temp_id}: {book_temp.status_code} (Background Task 1 dispatched)")

# Organizer updates temp event
time.sleep(2)
update_temp = client.put(
    f"/events/{temp_id}",
    headers={"Authorization": f"Bearer {org_token}"},
    json={"location": "Jaipur - Verified Venue"},
)
update_temp.raise_for_status()
print(f"    Verified event update on temp event #{temp_id}: {update_temp.status_code} (Background Task 2 dispatched)")

# Delete the temp verification event to leave zero residual bookings
time.sleep(2)
client.delete(f"/events/{temp_id}", headers={"Authorization": f"Bearer {org_token}"})
print(f"    Cleaned up temp verification event #{temp_id}.")

# 5. Create THE FINAL PRISTINE DEMO EVENT
print("--> [5] Creating pristine 'Tech Conference 2026' demo event...")
future_demo = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=45)).isoformat()
demo_event_res = client.post(
    "/events",
    headers={"Authorization": f"Bearer {org_token}"},
    json={
        "title": "Tech Conference 2026",
        "description": "Annual Flagship Technology Conference",
        "location": "Jaipur",
        "start_time": future_demo,
        "capacity": 20,
    },
)
demo_event_res.raise_for_status()
demo_event = demo_event_res.json()
demo_event_id = demo_event["id"]
print(f"    DEMO EVENT CREATED!")
print(f"    ID: #{demo_event_id}")
print(f"    Title: {demo_event['title']}")
print(f"    Location: {demo_event['location']}")
print(f"    Capacity: {demo_event['capacity']}")
print(f"    Available Tickets: {demo_event['available_tickets']}")

# 6. Verify Customer has ZERO bookings for this pristine demo event
my_bookings_resp = client.get("/bookings/me", headers={"Authorization": f"Bearer {cust_real_token}"})
my_bookings = my_bookings_resp.json()
has_demo_booking = any(b.get("event_id") == demo_event_id for b in my_bookings)

print("\n========================================================")
print(" DEMO ENVIRONMENT IS READY FOR RECORDING!")
print(f" Demo Event ID: {demo_event_id}")
print(f" Initial Capacity: {demo_event['capacity']}")
print(f" Initial Available Tickets: {demo_event['available_tickets']}")
print(f" Customer Bookings for this event: 0 (verified: {not has_demo_booking})")
print("========================================================")
