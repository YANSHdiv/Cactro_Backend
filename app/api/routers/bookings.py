from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Booking, Event, User
from app.schemas.booking import BookingResponse
from app.api.deps import require_customer

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/me", response_model=List[BookingResponse])
def get_my_bookings(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    bookings = (
        db.query(Booking)
        .join(Event, Booking.event_id == Event.id)
        .filter(Booking.customer_id == current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )

    result = []
    for b in bookings:
        result.append(
            BookingResponse(
                id=b.id,
                event_id=b.event_id,
                customer_id=b.customer_id,
                quantity=b.quantity,
                created_at=b.created_at,
                event_title=b.event.title if b.event else None,
                event_location=b.event.location if b.event else None,
                event_start_time=b.event.start_time if b.event else None,
            )
        )
    return result
