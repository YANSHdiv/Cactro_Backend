from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BookingCreate(BaseModel):
    quantity: int = Field(..., gt=0, description="Number of tickets to book")


class BookingResponse(BaseModel):
    id: int
    event_id: int
    customer_id: int
    quantity: int
    created_at: datetime
    event_title: Optional[str] = None
    event_location: Optional[str] = None
    event_start_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
