from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import enum
from app.database import Base


class UserRole(str, enum.Enum):
    DRIVER = "driver"
    SHIPPER = "shipper"
    CARRIER = "carrier"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tehran")


class TimeSlot(Base):
    __tablename__ = "time_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("warehouse_id", "start_time", name="uq_warehouse_slot"),
    )


class Cargo(Base):
    __tablename__ = "cargos"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipper_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    weight_kg: Mapped[float] = mapped_column(Float)
    origin: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="available")


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable: a cargo booking has no warehouse time slot (ADR 005).
    # Annotation stays non-union because SQLAlchemy 2.0.35 cannot parse
    # `Optional[...]` mapped annotations on Python 3.14; `nullable=True` is
    # authoritative here.
    time_slot_id: Mapped[int] = mapped_column(
        ForeignKey("time_slots.id"), nullable=True
    )
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    cargo_id: Mapped[int] = mapped_column(
        ForeignKey("cargos.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("time_slot_id", "driver_id", name="uq_slot_driver"),
        # Database backstop for "at most one confirmed booking per cargo" (ADR 005).
        Index(
            "uq_bookings_cargo_confirmed",
            "cargo_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
            sqlite_where=text("status = 'confirmed'"),
        ),
    )


class DriverDocument(Base):
    """One active license or national-ID row per driver (ADR 006)."""

    __tablename__ = "driver_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(20))
    stored_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    rejection_reason: Mapped[str] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reviewed_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    __table_args__ = (
        UniqueConstraint(
            "driver_id", "doc_type", name="uq_driver_document_type"
        ),
        CheckConstraint(
            "doc_type IN ('license', 'national_id')",
            name="ck_driver_document_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_driver_document_status",
        ),
        Index(
            "ix_driver_documents_status_uploaded",
            "status",
            "uploaded_at",
        ),
    )
