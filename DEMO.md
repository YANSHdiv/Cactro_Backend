# 3–4 Minute Demo Video Guide: Event Booking System

This document provides the exact step-by-step script, credentials, and Swagger endpoints for recording your 3–4 minute Loom walkthrough video.

---

## 1. Quick Reference & Credentials

- **Live Swagger / OpenAPI UI**: [https://event-booking-api-production-a76e.up.railway.app/docs](https://event-booking-api-production-a76e.up.railway.app/docs)
- **Live Health Check**: [https://event-booking-api-production-a76e.up.railway.app/health](https://event-booking-api-production-a76e.up.railway.app/health)

### Prepared Demo Accounts
| Role | Email | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Organizer** | `demo.organizer@cactro.com` | `OrganizerPass2026!` | Owns Demo Event #8 |
| **Customer** | `divyanshraj2604@gmail.com` | `customerpass123` | Delivers real emails to your Gmail inbox |
| **Customer (Generic)** | `demo.customer@cactro.com` | `CustomerPass2026!` | Alternative generic customer account |

### Prepared Demo Event
- **Event ID**: `8`
- **Title**: `Tech Conference 2026`
- **Location**: `Jaipur`
- **Capacity**: `20`
- **Initial Available Tickets**: `20`
- **Current Bookings**: `0` (Ready for you to book during recording!)

---

## 2. Step-by-Step Recording Sequence (Total: ~3.5 minutes)

### Step A: System Intro & Architecture (0:00 - 0:30)
**Action**: Open Swagger UI at `https://event-booking-api-production-a76e.up.railway.app/docs`.
> **What to Say**:
> *"Hi everyone, today I'm demonstrating our high-concurrency Event Booking System backend deployed live on Railway with PostgreSQL. It features strict role-based access control, concurrency-safe reservations via PostgreSQL row-level locking (`SELECT FOR UPDATE`), and asynchronous background email notifications powered by the Resend REST API."*

---

### Step B: Customer Login & Booking (0:30 - 1:15)
**Action**:
1. In Swagger UI, expand `POST /auth/login`. Click **Try it out** and execute:
```json
{
  "email": "divyanshraj2604@gmail.com",
  "password": "customerpass123"
}
```
2. Copy the returned `access_token`. Click the **Authorize 🔓** button at the top right of Swagger, paste the token, and click **Authorize**.
3. Scroll to `POST /events/{event_id}/book`. Click **Try it out**:
   - `event_id`: `8`
   - Request Body:
```json
{
  "quantity": 4
}
```
4. Click **Execute**. Show the `201 Created` response.
5. (Optional quick check): Expand `GET /events/8`, click **Execute** → show `available_tickets` decremented from 20 to 16!
> **What to Say**:
> *"First, we log in as a Customer. We book 4 tickets for Event #8, 'Tech Conference 2026'. The booking succeeds immediately with HTTP 201, and our database atomically decrements the remaining tickets from 20 to 16. Notice that right after the transaction commits, FastAPI BackgroundTasks dispatches a real booking confirmation email outside the database transaction."*

---

### Step C: Show Real Booking Confirmation Email (1:15 - 1:45)
**Action**: Switch tabs to your Gmail inbox (`divyanshraj2604@gmail.com`).
Show the new email from `onboarding@resend.dev`:
- **Subject**: `Booking Confirmation: Tech Conference 2026 (Booking #...)`
- **Content**: Shows Booking ID, event title, venue (Jaipur), and 4 tickets reserved.
> **What to Say**:
> *"Here in my real inbox, the booking confirmation email has already arrived. It includes the booking ID, venue in Jaipur, date, and 4 reserved tickets. Because email delivery runs asynchronously in the background, external API latency never holds database locks or delays customer responses."*

---

### Step D: Organizer Login & Event Update (1:45 - 2:30)
**Action**:
1. Click **Authorize** in Swagger, click **Logout**.
2. Go back to `POST /auth/login`, click **Try it out**, and execute:
```json
{
  "email": "demo.organizer@cactro.com",
  "password": "OrganizerPass2026!"
}
```
3. Copy the organizer's `access_token`. Click **Authorize**, paste it, and click **Authorize**.
4. Scroll to `PUT /events/{event_id}`. Click **Try it out**:
   - `event_id`: `8`
   - Request Body:
```json
{
  "location": "Jaipur Exhibition & Convention Centre (JECC)"
}
```
5. Click **Execute**. Show `200 OK` with updated location.
> **What to Say**:
> *"Now we switch to our Organizer account. As the creator of this event, the organizer updates the venue to the Jaipur Exhibition Centre. In the background, our second task queries all distinct customers who booked this event and fans out update emails."*

---

### Step E: Show Event-Update Email (2:30 - 2:50)
**Action**: Switch back to your Gmail inbox and refresh.
Show the second email:
- **Subject**: `Important Update: Your Event 'Tech Conference 2026' Has Been Updated`
- **Content**: Shows updated location: `Jaipur Exhibition & Convention Centre (JECC)`.
> **What to Say**:
> *"Refreshing my inbox, we see the real event update email delivered to the customer, informing them of the updated venue without duplicating emails across multiple tickets."*

---

### Step F: Code Walkthrough & SELECT FOR UPDATE (2:50 - 3:20)
**Action**: Show VS Code / IDE highlighting [`app/api/routers/events.py`](file:///c:/Users/div18/Desktop/Cactro_Backend/app/api/routers/events.py#L184-L210) (Lines 187–210):
```python
event = (
    db.query(Event)
    .filter(Event.id == event_id)
    .with_for_update()
    .first()
)
if event.available_tickets < payload.quantity:
    raise HTTPException(status_code=409, detail="Insufficient tickets remaining")

event.available_tickets -= payload.quantity
booking = Booking(event_id=event.id, customer_id=current_user.id, quantity=payload.quantity)
db.add(booking)
db.commit()
```
> **What to Say**:
> *"Here is the core concurrency implementation in `events.py`. Instead of the naive in-memory check-then-act pattern, we acquire a row-level lock using SQLAlchemy's `with_for_update()` within an atomic PostgreSQL transaction. This serializes inventory decrements and prevents overselling."*

---

### Step G: Performance Results (Baseline vs. Optimized) (3:20 - 3:50)
**Action**: Show the Comparison Table in [`README.md`](file:///c:/Users/div18/Desktop/Cactro_Backend/README.md) or [`PERFORMANCE.md`](file:///c:/Users/div18/Desktop/Cactro_Backend/PERFORMANCE.md):
- **Baseline**: 212 tickets booked for 50-ticket event (+324% oversell) at 50 users. At 100 users, throughput collapsed by 61.2% down to 70.8 RPS.
- **Optimized**: **0 oversold tickets across all concurrency tiers (10, 25, 50, 100, 200 users)**, and sustained **134.9 RPS (+90.5%)** at 100 concurrent users.
> **What to Say**:
> *"Finally, here are our real Locust benchmark results on a 50-capacity event. The naive baseline collapsed at 100 concurrent users and oversold by up to 324%. Our optimized row-level locking implementation guaranteed zero overselling across all tiers and maintained 134.9 requests per second at 100 users—a 90.5% throughput improvement under contention. Thank you!"*
