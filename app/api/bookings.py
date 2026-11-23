from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import BookingCreate, BookingResponse
from app.services.booking_service import BookingService

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

@router.post("/", response_model=BookingResponse)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    try:
        booking = BookingService.create_booking(db, data)
        return booking
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
