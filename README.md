# Event Booking System API

A high-performance, role-based backend API for managing and booking finite-capacity events under high concurrency. Built with Python, FastAPI, PostgreSQL, and SQLAlchemy, the system guarantees zero ticket overselling using PostgreSQL row-level locking (`SELECT FOR UPDATE`), features asynchronous email notifications via the Resend REST API, and includes reproducible Locust stress benchmarks comparing the naive baseline against the optimized production implementation.

---

## 1. Overview
The Event Booking System is designed to solve real-world ticketing challenges:
- Handling sharp bursts of concurrent ticket booking requests for finite-capacity venues.
- Ensuring strict role-based access control (Organizers vs. Customers).
- Decoupling user-facing HTTP request/response latency from slow external network calls (email delivery) using asynchronous background tasks.
- Providing transparent, empirical performance benchmarking to demonstrate system degradation and measurable optimization gains.

---

## 2. Features
- **Role-Based Access Control (RBAC)**: Distinct permissions for `ORGANIZER` and `CUSTOMER` roles.
- **Concurrency-Safe Reservations**: Mathematical guarantee against overselling using atomic transactions and row-level locking.
- **Event Lifecycle Management**: Full CRUD operations for organizers with ownership validation (organizers cannot modify or delete each other's events).
- **Asynchronous Email Processing**:
  - **Background Task 1**: Instant booking confirmation email to customer with booking ID, date, time, and venue.
  - **Background Task 2**: Deduplicated event update notifications fanned out to all customers who reserved tickets for a modified event.
- **Automated Test Suite**: 10 comprehensive integration and concurrency tests running against PostgreSQL.
- **Reproducible Stress Testing**: Automated Locust benchmarking suite measuring latency, throughput (RPS), error rates, and inventory integrity across 10, 25, 50, 100, and 200 concurrent users.

---

## 3. Tech Stack
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) (ASGI, Python 3.12)
- **Database**: [PostgreSQL 16](https://www.postgresql.org/)
- **ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/)
- **Driver**: `psycopg2-binary`
- **Authentication**: JWT (JSON Web Tokens via PyJWT) with `bcrypt` password hashing
- **Validation**: Pydantic v2
- **Background Tasks**: FastAPI `BackgroundTasks`
- **Email Service**: [Resend](https://resend.com/) REST API (`httpx`)
- **Stress & Load Testing**: [Locust](https://locust.io/)
- **Containerization**: Docker & Docker Compose

---

## 4. Architecture

```
                                  +-----------------------+
                                  |    HTTP Client /      |
                                  |  Locust / Swagger UI  |
                                  +-----------+-----------+
                                              |
                                              | Bearer JWT / JSON
                                              v
                              +---------------+---------------+
                              |     FastAPI Application       |
                              |  (Routers: Auth, Events, Book)|
                              +-------+---------------+-------+
                                      |               |
             +------------------------+               +------------------------+
             |                                                                 |
             v (Atomic DB Transaction)                                         v (Non-blocking)
  +----------+----------+                                           +----------+----------+
  | PostgreSQL 16 DB    |                                           | FastAPI             |
  | - SELECT FOR UPDATE |                                           | BackgroundTasks     |
  | - Row-level Locking |                                           +----------+----------+
  | - Check Constraints |                                                      |
  +---------------------+                                                      v (Async HTTPS)
                                                                    +----------+----------+
                                                                    | Resend Email API    |
                                                                    | - Confirmation Mail |
                                                                    | - Update Fan-Out    |
                                                                    +---------------------+
```

---

## 5. Database Schema & Relationships

### Entity Relationship
- **`users`** `1 ────< 0..N` **`events`** (An Organizer creates multiple Events)
- **`users`** `1 ────< 0..N` **`bookings`** (A Customer creates multiple Bookings)
- **`events`** `1 ────< 0..N` **`bookings`** (An Event has multiple Bookings)

### Data Models
1. **`users`**
   - `id`: Integer (Primary Key, autoincrement)
   - `name`: VARCHAR(100), NOT NULL
   - `email`: VARCHAR(255), UNIQUE, NOT NULL, INDEXED
   - `password_hash`: VARCHAR(255), NOT NULL
   - `role`: VARCHAR(20) (`ORGANIZER` | `CUSTOMER`), NOT NULL
   - `created_at`: TIMESTAMP WITH TIME ZONE, DEFAULT NOW()

2. **`events`**
   - `id`: Integer (Primary Key, autoincrement)
   - `title`: VARCHAR(200), NOT NULL
   - `description`: TEXT, NULLABLE
   - `location`: VARCHAR(200), NOT NULL
   - `start_time`: TIMESTAMP WITH TIME ZONE, NOT NULL
   - `capacity`: INTEGER, NOT NULL (`CHECK (capacity > 0)`)
   - `available_tickets`: INTEGER, NOT NULL (`CHECK (available_tickets >= 0)`)
   - `organizer_id`: INTEGER (FK -> `users.id` ON DELETE CASCADE), INDEXED
   - `created_at`: TIMESTAMP WITH TIME ZONE, DEFAULT NOW()
   - `updated_at`: TIMESTAMP WITH TIME ZONE, DEFAULT NOW()

3. **`bookings`**
   - `id`: Integer (Primary Key, autoincrement)
   - `event_id`: INTEGER (FK -> `events.id` ON DELETE CASCADE), INDEXED
   - `customer_id`: INTEGER (FK -> `users.id` ON DELETE CASCADE), INDEXED
   - `quantity`: INTEGER, NOT NULL (`CHECK (quantity > 0)`)
   - `created_at`: TIMESTAMP WITH TIME ZONE, DEFAULT NOW()

### Database Constraints & Indexes
- **Indexes**:
  - `idx_events_organizer_id` on `events(organizer_id)`
  - `idx_bookings_event_id` on `bookings(event_id)`
  - `idx_bookings_customer_id` on `bookings(customer_id)`
- **Constraints**:
  - `check_event_capacity_positive`: `capacity > 0`
  - `check_available_tickets_non_negative`: `available_tickets >= 0`
  - `check_booking_quantity_positive`: `quantity > 0`

---

## 6. Authentication & Authorization

### Authentication Flow (JWT)
1. User registers via `POST /auth/register` specifying role (`ORGANIZER` or `CUSTOMER`).
2. Password is salted and hashed using `bcrypt`.
3. User logs in via `POST /auth/login` and receives a signed JWT access token (`HS256`).
4. Subsequent requests pass the token in the `Authorization: Bearer <TOKEN>` header.
5. `get_current_user` decodes the token, validates expiration, and retrieves the active user record.

### Role Authorization Matrix

| Endpoint | Method | Allowed Role | Notes |
| :--- | :---: | :---: | :--- |
| `/auth/register` | `POST` | Public | Supports `ORGANIZER` and `CUSTOMER` |
| `/auth/login` | `POST` | Public | Returns Bearer JWT access token |
| `/events` | `GET` | Public / All | Browse upcoming events |
| `/events/{id}` | `GET` | Public / All | View specific event details |
| `/events` | `POST` | `ORGANIZER` | Creates event; capacity must be > 0 |
| `/events/{id}` | `PUT` | `ORGANIZER` | Only the creator organizer can update |
| `/events/{id}` | `DELETE` | `ORGANIZER` | Only the creator organizer can delete |
| `/events/{id}/book` | `POST` | `CUSTOMER` | Concurrency-safe ticket reservation |
| `/bookings/me` | `GET` | `CUSTOMER` | Customer's reservation history |

---

## 7. Booking Concurrency: Race Conditions & Prevention

### The Race Condition (Baseline / Naive Flow)
Under high load, multiple concurrent threads execute the standard read-check-update pattern simultaneously:
1. Thread A reads `available_tickets = 5`.
2. Thread B reads `available_tickets = 5`.
3. Thread A checks `5 >= 1`, decrements to 4, and commits.
4. Thread B checks `5 >= 1`, decrements to 4, and commits.
5. Both tickets were sold, but inventory only decremented once. Over thousands of requests, tickets are heavily oversold.

### The Solution: Row-Level Locking (`SELECT FOR UPDATE`)
In the optimized implementation, the reservation runs within an explicit PostgreSQL transaction:
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
- **PostgreSQL Row Lock**: `SELECT FOR UPDATE` locks the targeted event row in exclusive mode.
- **Serialization**: Concurrent requests attempting to book the same event queue up deterministically at the database row level.
- **Immediate Rejection**: As soon as `available_tickets < quantity`, requests are rejected with `409 Conflict`.
- **Zero Overselling**: Mathematically guarantees that sold tickets never exceed venue capacity.

---

## 8. Background Tasks & Email Processing

Email sending is handled asynchronously via FastAPI `BackgroundTasks`:
- **Task 1 (Booking Confirmation)**: Dispatched immediately after the booking transaction commits. Contains Booking ID, event title, venue, start time, and ticket quantity.
- **Task 2 (Event Update Fan-out)**: When an organizer updates an event (`PUT /events/{id}`), the system queries distinct customers who booked that event (`SELECT DISTINCT customer_id FROM bookings WHERE event_id = :id`) and sends individual update notices. Duplicate recipients are eliminated.
- **Transaction Isolation**: All email processing occurs **after and outside** the database transaction. If the Resend API experiences high latency or downtime, it never holds database locks or blocks the HTTP response.

### Email Configuration
Configure using `.env` variables:
```bash
RESEND_API_KEY=re_your_api_key_here
FROM_EMAIL=onboarding@resend.dev
```
If `RESEND_API_KEY` is missing or unconfigured, the system logs an explicit warning rather than failing or silently pretending delivery occurred.

---

## 9. API Endpoints Reference

| Category | Method | Path | Description |
| :--- | :---: | :--- | :--- |
| **Auth** | `POST` | `/auth/register` | Register a new user (`ORGANIZER` or `CUSTOMER`) |
| **Auth** | `POST` | `/auth/login` | Authenticate and obtain JWT access token |
| **Events** | `GET` | `/events` | List all scheduled events |
| **Events** | `POST` | `/events` | Create a new event (`ORGANIZER` only) |
| **Events** | `GET` | `/events/{id}` | Get event details by ID |
| **Events** | `PUT` | `/events/{id}` | Update event details (`ORGANIZER` owner only) |
| **Events** | `DELETE` | `/events/{id}` | Delete event (`ORGANIZER` owner only) |
| **Bookings** | `POST` | `/events/{id}/book` | Book tickets for an event (`CUSTOMER` only) |
| **Bookings** | `GET` | `/bookings/me` | List bookings of logged-in customer |
| **Health** | `GET` | `/health` | Application and database health check |
| **Testing** | `POST` | `/test/reset-benchmark` | Reset benchmark event state for reproducible Locust runs |

---

## 10. Local Setup & Running

### Prerequisites
- Python 3.12+
- Docker & Docker Compose

### 1. Clone & Environment Setup
```bash
git clone <repository_url>
cd Cactro_Backend
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Start PostgreSQL Database
```bash
docker compose up -d
```
*Starts PostgreSQL 16 on port `5433` (isolated container `event-booking-db`).*

### 3. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 4. Run the Application
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger documentation is available at: `http://127.0.0.1:8000/docs`.

---

## 11. Automated Testing

Run the full pytest suite (10 automated integration tests covering authentication, authorization, CRUD, insufficient tickets, and multi-threaded concurrency):
```bash
python -m pytest -v
```

---

## 12. Performance Benchmarking & Stress Analysis

### Benchmark Methodology
Stress testing was performed using Locust targeting a single finite-capacity event (50 tickets) under rapid request rates to evaluate concurrent contention. Tests were executed across 5 concurrency tiers: **10, 25, 50, 100, and 200 concurrent users**.

### Real Empirical Measurements

#### A. Baseline (Naive LLM Implementation)
*Git Commit: `d846333 baseline implementation`*

| Users | Total Requests | RPS | Avg Latency (ms) | p95 Latency (ms) | Tickets Booked | Capacity | Oversold | Integrity |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 1,310 | 144.7 | 31.8 | 57.0 | **110** | 50 | **+60 (+120%)** | ❌ FAILED |
| **25** | 1,649 | 182.4 | 96.8 | 160.0 | **164** | 50 | **+114 (+228%)** | ❌ FAILED |
| **50** | 1,501 | 166.1 | 248.6 | 480.0 | **212** | 50 | **+162 (+324%)** | ❌ FAILED |
| **100** | 143 | 70.8 | 579.8 | 900.0 | **154** | 50 | **+104 (+208%)** | ❌ FAILED |
| **200** | 95 | 64.3 | 629.9 | 1,300.0 | **108** | 50 | **+58 (+116%)** | ❌ FAILED |

**Baseline Bottleneck Analysis**:
- **Catastrophic Overselling**: At 50 concurrent users, the naive system sold 212 tickets for a 50-capacity event (+324% oversold).
- **Breaking Point**: At 100 concurrent users, throughput collapsed by **61.2%** (from 182.4 to 70.8 req/s), while average latency jumped to 579.8ms and p95 approached 1 second due to uncoordinated concurrent state mutations and severe request queueing.

---

#### B. Optimized Implementation
*Git Commit: `a3de856 optimize: apply PostgreSQL row-level locking (SELECT FOR UPDATE) and connection pool tuning`*

| Users | Total Requests | RPS | Avg Latency (ms) | p95 Latency (ms) | Tickets Booked | Capacity | Oversold | Integrity |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 1,361 | 150.8 | 30.3 | 49.0 | **50** | 50 | **0 (0%)** | ✅ PASSED |
| **25** | 1,412 | 156.5 | 117.1 | 170.0 | **50** | 50 | **0 (0%)** | ✅ PASSED |
| **50** | 1,330 | 147.2 | 282.1 | 400.0 | **50** | 50 | **0 (0%)** | ✅ PASSED |
| **100** | 1,215 | 134.9 | 641.1 | 850.0 | **50** | 50 | **0 (0%)** | ✅ PASSED |
| **200** | 114 | 72.4 | 818.2 | 1,500.0 | **50** | 50 | **0 (0%)** | ✅ PASSED |

---

### Before vs. After Comparison Table

| Metric | Baseline (100 Users) | Optimized (100 Users) | Delta / Impact |
| :--- | :---: | :---: | :--- |
| **Data Integrity** | 154 / 50 Booked (Oversold by 104) | **50 / 50 Booked (0 Oversold)** | **100% Protection against Overselling** |
| **Throughput (RPS)** | 70.8 req/s | **134.9 req/s** | **+90.5% sustained throughput** |
| **Total Requests Handled** | 143 requests | **1,215 requests** | **+749.7% requests processed** |
| **p95 Latency** | 900.0 ms | **850.0 ms** | **-5.6% lower tail latency** |
| **Crash / Starvation Rate** | High pool timeout rate | **0 unhandled errors** | **Stable connection management** |

---

## 13. Deployment

The production deployment package is completely containerized and ready for 1-click cloud deployment on platforms like Render, Railway, or Fly.io:
- **`Dockerfile`**: Multi-stage, minimal Python 3.12 slim image with libpq and PostgreSQL build tools.
- **`render.yaml`**: Full Render Blueprint defining both the web service and the managed PostgreSQL database.
- **`Procfile`**: Standard ASGI process definition.

### Production Environment Variables
| Variable | Description | Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://user:pass@host:5432/dbname` |
| `JWT_SECRET` | Secret key for HS256 JWT tokens | `generate_secure_random_hex_key` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `CONCURRENCY_MODE` | Booking transaction mode | `optimized` |
| `RESEND_API_KEY` | Resend API key for real emails | `re_abc123...` |
| `FROM_EMAIL` | Verified sender email | `onboarding@resend.dev` |

---

## 14. Design Decisions & Trade-offs

1. **FastAPI BackgroundTasks vs. Celery/Redis**:
   - *Decision*: Used FastAPI's in-process `BackgroundTasks` for asynchronous email delivery.
   - *Trade-off*: Avoids complex queue infrastructure (Redis, RabbitMQ, Celery workers) for this assignment while keeping HTTP responses snappy (<50ms).
   - *Production Scale*: At massive enterprise scale (millions of users), an out-of-process durable queue (e.g., Celery with Redis, SQS, or Kafka) would be introduced to guarantee message persistence across container restarts and provide retry/dead-letter capabilities.
2. **PostgreSQL Row-Level Locking (`SELECT FOR UPDATE`) vs. Optimistic Locking**:
   - *Decision*: Used pessimistic row-level locking (`with_for_update`).
   - *Trade-off*: Slightly reduced raw concurrency at moderate loads due to serialization, but mathematically eliminates overselling and avoids wasted retries under high contention.
3. **Database-Level Check Constraints**:
   - *Decision*: Added `CHECK (available_tickets >= 0)` directly to the database table definition.
   - *Rationale*: Acts as an unbreakable defense-in-depth safety net, guaranteeing that even in the presence of application bugs, PostgreSQL will reject any transaction attempting to decrement tickets below zero.
