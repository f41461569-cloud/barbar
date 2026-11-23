from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import TimeSlot, Booking
from app.schemas import BookingCreate

class BookingService:
    @staticmethod
    def create_booking(db: Session, data: BookingCreate) -> Booking:
        slot = (
            db.execute(
                select(TimeSlot)
                .where(TimeSlot.id == data.time_slot_id)
                .with_for_update()
            )
            .scalar_one_or_none()
        )
        if not slot:
            raise ValueError("Time slot not found")

        existing = db.execute(
            select(Booking).where(
                Booking.time_slot_id == data.time_slot_id,
                Booking.status == "confirmed",
            )
        ).scalars().all()
        if len(existing) >= slot.capacity:
            raise ValueError("This time slot is already booked")

        booking = Booking(
            time_slot_id=data.time_slot_id,
            driver_id=data.driver_id,
            cargo_id=data.cargo_id,
            status="confirmed",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
