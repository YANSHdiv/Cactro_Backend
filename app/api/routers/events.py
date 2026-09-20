from typing import List
from datetime import datetime, timezone
import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import Event, User, Booking, UserRole
from app.schemas.event import EventCreate, EventUpdate, EventResponse
from app.schemas.booking import BookingCreate, BookingResponse
from app.api.deps import get_current_user, require_organizer, require_customer
from app.services.email_service import EmailService
from app.core.config import settings

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    if payload.capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event capacity must be greater than zero",
        )

    new_event = Event(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        location=payload.location.strip(),
        start_time=payload.start_time,
        capacity=payload.capacity,
        available_tickets=payload.capacity,
        organizer_id=current_user.id,
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event


@router.get("", response_model=List[EventResponse])
def list_events(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    events = db.query(Event).order_by(Event.start_time.asc()).offset(skip).limit(limit).all()
    return events


@router.get("/{event_id}", response_model=EventResponse)
def get_event_details(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )
    return event


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    # Authorization: prevent an organizer from modifying another organizer's event
    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only update events that you created",
        )

    updated_fields = []
    if payload.title is not None:
        event.title = payload.title.strip()
        updated_fields.append("title")
    if payload.description is not None:
        event.description = payload.description.strip() if payload.description else None
        updated_fields.append("description")
    if payload.location is not None:
        event.location = payload.location.strip()
        updated_fields.append("location")
    if payload.start_time is not None:
        event.start_time = payload.start_time
        updated_fields.append("start_time")
    if payload.capacity is not None:
        booked_tickets = event.capacity - event.available_tickets
        if payload.capacity < booked_tickets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce capacity to {payload.capacity}; {booked_tickets} tickets are already booked",
            )
        event.available_tickets = payload.capacity - booked_tickets
        event.capacity = payload.capacity
        updated_fields.append("capacity")

    db.commit()
    db.refresh(event)

    # Find distinct customers who booked this event to notify
    booked_customers_raw = (
        db.query(User.email, User.name)
        .join(Booking, Booking.customer_id == User.id)
        .filter(Booking.event_id == event.id)
        .distinct()
        .all()
    )
    recipients = [{"email": row[0], "name": row[1]} for row in booked_customers_raw]

    # Schedule Background Task 2: Event Update Email (kept outside DB transaction)
    if updated_fields and recipients:
        updated_details = {
            "title": event.title,
            "location": event.location,
            "start_time": str(event.start_time),
            "description": event.description,
        }
        background_tasks.add_task(
            EmailService.send_event_update_notifications,
            recipients=recipients,
            event_title=event.title,
            updated_fields=updated_fields,
            updated_event_details=updated_details,
        )

    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    current_user: User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found",
        )

    # Authorization: prevent an organizer from deleting another organizer's event
    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You can only delete events that you created",
        )

    db.delete(event)
    db.commit()
    return None


@router.post("/{event_id}/book", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def book_tickets(
    event_id: int,
    payload: BookingCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    if payload.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking quantity must be at least 1",
        )

    # Check concurrency mode: naive (baseline LLM) vs optimized (production row locking)
    if settings.CONCURRENCY_MODE == "naive":
        # NAIVE BASELINE IMPLEMENTATION:
        # Intentionally reads without row locking (no SELECT FOR UPDATE).
        # Multiple concurrent requests can read the same available_tickets before committing.
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        # Simulate small application interleaving window under concurrent load
        time.sleep(0.005)

        if event.available_tickets < payload.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient tickets remaining. Requested: {payload.quantity}, Available: {event.available_tickets}",
            )

        event.available_tickets -= payload.quantity
        booking = Booking(
            event_id=event.id,
            customer_id=current_user.id,
            quantity=payload.quantity,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

    else:
        # OPTIMIZED PRODUCTION IMPLEMENTATION:
        # Uses row-level lock (SELECT FOR UPDATE) within an atomic PostgreSQL transaction.
        # Guarantees serialized inventory decrements and prevents overselling.
        event = (
            db.query(Event)
            .filter(Event.id == event_id)
            .with_for_update()
            .first()
        )
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        if event.available_tickets < payload.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient tickets remaining. Requested: {payload.quantity}, Available: {event.available_tickets}",
            )

        event.available_tickets -= payload.quantity
        booking = Booking(
            event_id=event.id,
            customer_id=current_user.id,
            quantity=payload.quantity,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

    # Schedule Background Task 1: Booking confirmation email (AFTER DB commit)
    background_tasks.add_task(
        EmailService.send_booking_confirmation,
        customer_email=current_user.email,
        customer_name=current_user.name,
        event_title=event.title,
        event_location=event.location,
        event_start_time=str(event.start_time),
        quantity=booking.quantity,
        booking_id=booking.id,
    )

    return BookingResponse(
        id=booking.id,
        event_id=booking.event_id,
        customer_id=booking.customer_id,
        quantity=booking.quantity,
        created_at=booking.created_at,
        event_title=event.title,
        event_location=event.location,
        event_start_time=event.start_time,
    )
