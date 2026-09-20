import os
import sys
import time
import datetime
import httpx

LIVE_URL = os.getenv("LIVE_API_URL", "https://event-booking-api-production-a76e.up.railway.app")


def verify_real_emails(customer_target_email: str):
    print(f"========================================================")
    print(f" LIVE REAL EMAIL VERIFICATION WORKFLOW")
    print(f" Target Public API: {LIVE_URL}")
    print(f" Customer Target Email: {customer_target_email}")
    print(f"========================================================\n")

    client = httpx.Client(base_url=LIVE_URL, timeout=30.0)

    # 1. Register Organizer
    org_email = f"organizer_{int(datetime.datetime.now().timestamp())}@test.com"
    print(f"--> [1] Registering Event Organizer ({org_email})...")
    r = client.post(
        "/auth/register",
        json={
            "name": "Live Organizer",
            "email": org_email,
            "password": "organizerpass123",
            "role": "ORGANIZER",
        },
    )
    r.raise_for_status()
    org_token = r.json()["access_token"]

    # 2. Create Event
    event_start = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)).isoformat()
    print("--> [2] Creating Event 'Tech Disruption Summit 2026'...")
    r = client.post(
        "/events",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Tech Disruption Summit 2026",
            "description": "Exclusive invitation-only keynote",
            "location": "Moscone Center, Hall D",
            "start_time": event_start,
            "capacity": 25,
        },
    )
    r.raise_for_status()
    event_id = r.json()["id"]
    print(f"    Event created with ID: #{event_id}")

    # 3. Register Customer with REAL target email
    print(f"--> [3] Registering Customer with real inbox: {customer_target_email}...")
    cust_res = client.post(
        "/auth/register",
        json={
            "name": "Verified Customer",
            "email": customer_target_email,
            "password": "customerpass123",
            "role": "CUSTOMER",
        },
    )
    if cust_res.status_code == 201:
        cust_token = cust_res.json()["access_token"]
    else:
        # Try login if already registered
        login_res = client.post(
            "/auth/login",
            json={"email": customer_target_email, "password": "customerpass123"},
        )
        login_res.raise_for_status()
        cust_token = login_res.json()["access_token"]

    # 4. Trigger Background Task 1: Book Ticket
    print(f"--> [4] Booking 2 tickets (Triggering Background Task 1: Booking Confirmation Email)...")
    book_res = client.post(
        f"/events/{event_id}/book",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"quantity": 2},
    )
    book_res.raise_for_status()
    booking_id = book_res.json()["id"]
    print(f"    Booking confirmed! Booking ID: #{booking_id}. HTTP response returned immediately.")
    print("    Check your inbox for the Booking Confirmation Email.\n")

    time.sleep(3)

    # 5. Trigger Background Task 2: Organizer Updates Event
    print("--> [5] Organizer updating event venue and title (Triggering Background Task 2: Update Notification Fan-Out)...")
    update_res = client.put(
        f"/events/{event_id}",
        headers={"Authorization": f"Bearer {org_token}"},
        json={
            "title": "Tech Disruption Summit 2026 (VENUE UPDATE)",
            "location": "Moscone Center, Grand Ballroom West",
        },
    )
    update_res.raise_for_status()
    print("    Event updated successfully! HTTP response returned immediately.")
    print("    Check your inbox for the Event Update Notification Email.\n")

    print("========================================================")
    print(" Email tasks dispatched asynchronously via Resend API!")
    print(" Inspect server logs or your recipient inbox to confirm.")
    print("========================================================")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_live_emails <recipient_email>")
        sys.exit(1)
    verify_real_emails(sys.argv[1])
