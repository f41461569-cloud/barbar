from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Enum, UniqueConstraint
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
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    cargo_id: Mapped[int] = mapped_column(ForeignKey("cargos.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("time_slot_id", "driver_id", name="uq_slot_driver"),
    )
