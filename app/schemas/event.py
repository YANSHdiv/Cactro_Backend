from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EventBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    location: str = Field(..., min_length=2, max_length=200)
    start_time: datetime
    capacity: int = Field(..., gt=0)


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, min_length=2, max_length=200)
    start_time: Optional[datetime] = None
    capacity: Optional[int] = Field(None, gt=0)


class EventResponse(EventBase):
    id: int
    available_tickets: int
    organizer_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
