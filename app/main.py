from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.db.session import engine, Base, get_db
from app.db.models import User, Event, Booking, UserRole
from app.core.security import get_password_hash, create_access_token
from app.api.routers import auth, events, bookings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Event Booking System with role-based access, concurrency-safe transactions, and asynchronous email processing.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(bookings.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "concurrency_mode": settings.CONCURRENCY_MODE,
        "database": "connected",
        "version": settings.VERSION,
    }


@app.post("/test/reset-benchmark", tags=["Testing & Benchmarking"])
def reset_benchmark_event(
    capacity: int = 100,
    concurrency_mode: str = None,
    db: Session = Depends(get_db),
):
    """
    Resets or initializes a benchmark event with a clean ticket inventory
    and provides a ready-to-use customer JWT for Locust testing.
    """
    if concurrency_mode:
        settings.CONCURRENCY_MODE = concurrency_mode

    # Clean existing benchmark data
    organizer = db.query(User).filter(User.email == "benchmark_organizer@example.com").first()
    if not organizer:
        organizer = User(
            name="Benchmark Organizer",
            email="benchmark_organizer@example.com",
            password_hash=get_password_hash("organizerpass123"),
            role=UserRole.ORGANIZER,
        )
        db.add(organizer)
        db.commit()
        db.refresh(organizer)

    customer = db.query(User).filter(User.email == "benchmark_customer@example.com").first()
    if not customer:
        customer = User(
            name="Benchmark Customer",
            email="benchmark_customer@example.com",
            password_hash=get_password_hash("customerpass123"),
            role=UserRole.CUSTOMER,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # Find or create benchmark event
    event = db.query(Event).filter(Event.title == "Benchmark Stress Event").first()
    if event:
        # Delete existing bookings for this event
        db.query(Booking).filter(Booking.event_id == event.id).delete()
        event.capacity = capacity
        event.available_tickets = capacity
        db.commit()
        db.refresh(event)
    else:
        event = Event(
            title="Benchmark Stress Event",
            description="Event specifically designated for concurrency load testing",
            location="Load Test Arena",
            start_time=datetime.now(timezone.utc) + timedelta(days=30),
            capacity=capacity,
            available_tickets=capacity,
            organizer_id=organizer.id,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

    customer_token = create_access_token(subject=customer.id, role=customer.role.value)

    return {
        "status": "reset_complete",
        "concurrency_mode": settings.CONCURRENCY_MODE,
        "event_id": event.id,
        "capacity": event.capacity,
        "available_tickets": event.available_tickets,
        "customer_token": customer_token,
    }
