# Event Booking System - 3–4 Minute Demo Walkthrough & Script

This guide outlines a crisp, professional 3–4 minute walkthrough for a Loom recording or live technical evaluation. It uses Swagger UI (`/docs`) and terminal commands to demonstrate all core functionality, role-based access, concurrency safety, asynchronous emails, and empirical performance gains.

---

## Live Production Endpoints
- **Live Base URL**: `https://event-booking-api-production-a76e.up.railway.app`
- **Swagger / OpenAPI UI**: [https://event-booking-api-production-a76e.up.railway.app/docs](https://event-booking-api-production-a76e.up.railway.app/docs)
- **Health Check**: [https://event-booking-api-production-a76e.up.railway.app/health](https://event-booking-api-production-a76e.up.railway.app/health)

---

## Demo Checklist & Timeline (Total: ~3.5 minutes)

| Timestamp | Phase | Action / Endpoint | Key Talking Point |
| :---: | :---: | :---: | :---: |
| **0:00 - 0:30** | **Architecture Overview** | Open `/docs` in browser | FastAPI, PostgreSQL row-level locks, JWT auth, Resend email worker |
| **0:30 - 1:00** | **Organizer Flow** | `POST /auth/register`<br>`POST /events` | Role enforcement, event creation with capacity constraint |
| **1:00 - 1:40** | **Customer Flow & Email** | `POST /auth/register`<br>`GET /events`<br>`POST /events/{id}/book` | Role-based authorization, inventory decrement, **Background Task 1 (Booking Email)** |
| **1:40 - 2:10** | **Organizer Update & Fan-out** | `PUT /events/{id}` | Capacity protection, **Background Task 2 (Deduplicated Fan-out Email)** |
| **2:10 - 2:50** | **Baseline Concurrency Breakdown** | Terminal / `PERFORMANCE.md` | Show naive check-then-act bug, +324% oversell, throughput collapse |
| **2:50 - 3:30** | **Optimized Concurrency & Results** | Terminal / `PERFORMANCE.md` | Explain `SELECT FOR UPDATE`, connection pooling, 0 oversold tickets |

---

## Detailed Step-by-Step Execution & Script

### Step 1: System Intro (0:00 - 0:30)
**Action**: Navigate to `http://localhost:8000/docs` (or your deployed URL).
> **Spoken Script**:
> *"Hi everyone, today I'm demonstrating our high-concurrency Event Booking System backend. Built with Python, FastAPI, SQLAlchemy, and PostgreSQL, it features strict role-based access control between Event Organizers and Customers, concurrency-safe ticket reservations using row-level database locking, and asynchronous background email delivery powered by the Resend API."*

---

### Step 2: Organizer Authentication & Event Creation (0:30 - 1:00)
**Action**:
1. In Swagger, open `POST /auth/register`.
2. Click **Try it out** and execute:
```json
{
  "name": "Sarah Connor",
  "email": "organizer@techconf.org",
  "password": "organizerSecret2026",
  "role": "ORGANIZER"
}
```
3. Copy the returned `access_token` and click **Authorize** at the top of Swagger. Paste the token.
4. Open `POST /events` and execute:
```json
{
  "title": "Global AI & Cloud Summit 2026",
  "description": "Premier tech summit covering generative systems and distributed scale.",
  "location": "Moscone Center, San Francisco, CA",
  "start_time": "2026-11-15T09:00:00Z",
  "capacity": 50
}
```
> **Spoken Script**:
> *"First, we register an Organizer and authenticate via JWT. The organizer creates a new event with a finite capacity of 50 tickets. Notice that `available_tickets` is automatically initialized to 50, and only organizers are permitted to create events."*

---

### Step 3: Customer Registration, Event Browsing & Booking (1:00 - 1:40)
**Action**:
1. Register a customer via `POST /auth/register`:
```json
{
  "name": "Alex Mercer",
  "email": "alex.customer@gmail.com",
  "password": "customerSecret2026",
  "role": "CUSTOMER"
}
```
2. Click **Authorize** with Alex's customer token.
3. Call `GET /events` to browse upcoming events.
4. Call `POST /events/1/book` with:
```json
{
  "quantity": 2
}
```
5. Call `GET /bookings/me` to view Alex's reservations.
6. Open your terminal or email inbox/logs to show the real email dispatch confirmation:
   `[EMAIL SERVICE] Successfully sent email to divyanshraj2604@gmail.com. Response: {'id': '01a0bdc3-8c82-76b9-a893-32f7ef993353'}`
> **Spoken Script**:
> *"Now we switch to a Customer role. Customers can browse public events and reserve tickets. When Alex books 2 tickets, our booking transaction atomically decrements available tickets from 50 to 48. Notice that right after the database transaction commits, FastAPI BackgroundTasks automatically triggers our first asynchronous task: dispatching a real booking confirmation email via the Resend API (Message ID: 01a0bdc3-8c82-76b9-a893-32f7ef993353)—completely decoupled from the HTTP response."*

---

### Step 4: Event Update & Customer Notification Fan-Out (1:40 - 2:10)
**Action**:
1. Switch back to Sarah (the organizer).
2. Call `PUT /events/1` to update venue and schedule:
```json
{
  "location": "Moscone West, Grand Ballroom",
  "start_time": "2026-11-15T10:00:00Z"
}
```
3. Show terminal log showing Background Task 2 fan-out:
   `[EMAIL SERVICE] Successfully sent email to divyanshraj2604@gmail.com. Response: {'id': '01a0bdc3-993a-7313-8b78-6766a87d609f'}`
   `[EMAIL SERVICE] Finished sending updates to 1 customer(s). Sent: 1`
> **Spoken Script**:
> *"When the organizer updates event details, our second background task kicks in: it queries all distinct customers who reserved tickets for this event and fans out personalized update notifications with the modified details (Message ID: 01a0bdc3-993a-7313-8b78-6766a87d609f), deduplicating recipients to prevent spam."*

---

### Step 5: Baseline Concurrency Breakdown (2:10 - 2:50)
**Action**: Switch to your terminal or display `PERFORMANCE.md`.
> **Spoken Script**:
> *"Now let's examine the core engineering challenge: concurrency. In our baseline implementation, we simulated the standard LLM-generated read-check-update pattern. When we ran a real Locust stress test targeting a 50-capacity event across 10 to 200 concurrent users, the naive approach failed catastrophically.
> Under 50 concurrent users, it sold 212 tickets for a 50-ticket event—a 324% oversell rate. At 100 users, throughput collapsed from 182 req/s down to 70 req/s, and p95 latency reached nearly 1 second because threads blocked each other without safe synchronization."*

---

### Step 6: The Optimization & Measured Delta (2:50 - 3:30)
**Action**: Show the `SELECT FOR UPDATE` code snippet in `app/api/routers/events.py` and the before/after comparison table in `PERFORMANCE.md`.
> **Spoken Script**:
> *"To fix this, we implemented PostgreSQL row-level locking via SQLAlchemy's `with_for_update()`, enforced database-level check constraints, tuned connection pooling to 25 connections with 15 overflow, and ensured email execution remains strictly outside transaction locks.
> We then re-ran the exact same Locust scenario. The result: across all concurrency tiers from 10 to 200 users, exactly 50 tickets were booked with zero overselling. At 100 concurrent users, throughput jumped by +90.5% compared to the baseline, from 70.8 to 134.9 requests per second, and 1,215 requests were successfully processed with sub-second tail latencies.
> Everything is fully tested, Dockerized, and ready for production."*

---

## Quick cURL Commands for Quick Terminal Testing

### 1. Register Organizer
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"Sarah Connor","email":"organizer@example.com","password":"password123","role":"ORGANIZER"}'
```

### 2. Create Event (Replace `<ORG_TOKEN>`)
```bash
curl -X POST "http://localhost:8000/events" \
  -H "Authorization: Bearer <ORG_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Summer Tech Fest","location":"Auditorium A","start_time":"2026-10-01T10:00:00Z","capacity":50}'
```

### 3. Register Customer & Book Ticket (Replace `<CUST_TOKEN>`)
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","email":"john@example.com","password":"password123","role":"CUSTOMER"}'

curl -X POST "http://localhost:8000/events/1/book" \
  -H "Authorization: Bearer <CUST_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"quantity":2}'
```
