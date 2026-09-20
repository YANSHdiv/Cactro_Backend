import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class UserRole(str, enum.Enum):
    ORGANIZER = "ORGANIZER"
    CUSTOMER = "CUSTOMER"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, name="user_role_enum", native_enum=False), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    organized_events = relationship("Event", back_populates="organizer", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="customer", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    capacity = Column(Integer, nullable=False)
    available_tickets = Column(Integer, nullable=False)
    organizer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Table constraints
    __table_args__ = (
        CheckConstraint("capacity > 0", name="check_event_capacity_positive"),
        CheckConstraint("available_tickets >= 0", name="check_available_tickets_non_negative"),
        Index("idx_events_organizer_id", "organizer_id"),
    )

    # Relationships
    organizer = relationship("User", back_populates="organized_events")
    bookings = relationship("Booking", back_populates="event", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Table constraints
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_booking_quantity_positive"),
        Index("idx_bookings_event_id", "event_id"),
        Index("idx_bookings_customer_id", "customer_id"),
    )

    # Relationships
    event = relationship("Event", back_populates="bookings")
    customer = relationship("User", back_populates="bookings")
